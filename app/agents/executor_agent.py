from __future__ import annotations

import logging

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agents.state import AgentState
from app.prompts.executor_prompt import EXECUTOR_PROMPT

logger = logging.getLogger(__name__)


class ExecutorAgent:
    """
    Executor node in the LangGraph pipeline.

    Receives the plan from `state["plan"]`, binds tools to the LLM,
    runs an agentic loop until all steps are completed, and writes the
    final answer into `state["response"]` and appends it to `state["messages"]`.
    """

    def __init__(self, llm: ChatGoogleGenerativeAI, tools: list[BaseTool]) -> None:
        self.llm = llm
        self.tools = tools
        # Map tool name → callable for easy dispatch
        self.tool_map: dict[str, BaseTool] = {t.name: t for t in tools}
        # Bind tools to the LLM so it knows how to call them
        self.llm_with_tools = llm.bind_tools(tools)

    async def run(self, state: AgentState) -> dict:
        plan = state.get("plan", [])
        plan_text = "\n".join(f"{i + 1}. {step}" for i, step in enumerate(plan))
        logger.info("⚙️  Executor | executing plan:\n%s", plan_text)

        system_prompt = EXECUTOR_PROMPT.format(plan=plan_text)

        # Start the conversation with the system prompt + original user messages
        conversation = [SystemMessage(content=system_prompt)] + list(state["messages"])

        # Agentic tool-calling loop
        while True:
            response = await self.llm_with_tools.ainvoke(conversation)
            conversation.append(response)

            # Log AI reasoning
            if response.content:
                text = response.content
                if isinstance(text, list):
                    text = " ".join(p.get("text", "") for p in text if isinstance(p, dict))
                logger.info("🧠 Executor thinking: %s", str(text)[:500])

            # If no tool calls → final answer reached
            if not getattr(response, "tool_calls", None):
                break

            # Execute each tool call and append results
            for tc in response.tool_calls:
                tool_name = tc.get("name", "")
                tool_args = tc.get("args", {})
                tool_id = tc.get("id", tool_name)

                logger.info("🔧 Executor | tool call: %s | args: %s", tool_name, tool_args)

                tool = self.tool_map.get(tool_name)
                if tool is None:
                    result = f"Tool '{tool_name}' not found."
                    logger.warning("⚠️  Executor | unknown tool: %s", tool_name)
                else:
                    try:
                        result = tool.run(tool_args)
                    except Exception as exc:
                        result = f"Tool '{tool_name}' failed: {exc}"
                        logger.error("❌ Executor | tool error: %s", exc)

                logger.info("📦 Executor | tool result [%s]: %s", tool_name, str(result)[:400])
                conversation.append(
                    ToolMessage(content=str(result), tool_call_id=tool_id, name=tool_name)
                )

        # Extract final text content from last AI message
        final_content = response.content
        if isinstance(final_content, list):
            final_content = " ".join(
                p.get("text", "") for p in final_content if isinstance(p, dict)
            )

        final_content = str(final_content)
        logger.info("✅ Executor | final response length=%d", len(final_content))

        return {
            "response": final_content,
            "messages": [AIMessage(content=final_content)],
        }
