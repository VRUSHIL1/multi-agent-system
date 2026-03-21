from __future__ import annotations

import logging

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agents.graph import build_agent_graph
from app.common.settings import settings
from app.tools import get_langchain_tools, get_mcp_langchain_tools

logger = logging.getLogger(__name__)


class GeminiAgent:
    """Main LLM agent using Gemini + LangGraph."""

    def __init__(self, *, model_name: str | None = None) -> None:
        if not settings.gemini_api_key:
            raise RuntimeError("Gemini API key not configured")

        self.model_name = model_name or settings.gemini_model

        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=settings.gemini_api_key,
            temperature=0.5,
        )

        self.tools = []
        self.agent = None

    async def initialize(self) -> None:
        """Initialize tools and build the agent graph."""

        local_tools = get_langchain_tools()
        mcp_tools = await get_mcp_langchain_tools()

        self.tools = [*local_tools, *mcp_tools]

        logger.info(
            "🧰 Tools loaded | local=%d | mcp=%d",
            len(local_tools),
            len(mcp_tools),
        )

        self.agent = build_agent_graph(
            llm=self.llm,
            tools=self.tools,
        )

        logger.info("🕸️ Agent graph initialized")

    async def generate_response(
        self,
        message: str,
        session_id: int,
        summary: str = "",
        memory_context: str = "",
    ) -> str:

        if not self.agent:
            raise RuntimeError("Agent not initialized. Call initialize() first.")

        logger.info(
            "📩 User message | session=%s | message=%s",
            session_id,
            message,
        )

        messages = []

        if summary:
            messages.append(
                HumanMessage(
                    content=f"Previous conversation summary:\n{summary}"
                )
            )

        if memory_context:
            messages.append(
                HumanMessage(
                    content=f"Relevant memories:\n{memory_context}"
                )
            )

        messages.append(HumanMessage(content=message))

        result = await self.agent.ainvoke(
            {"messages": messages},
            config={"configurable": {"thread_id": str(session_id)}},
        )

        # Log agent reasoning
        for msg in result["messages"]:

            if isinstance(msg, HumanMessage):
                continue

            if isinstance(msg, AIMessage):

                if msg.content:
                    text = msg.content

                    if isinstance(text, list):
                        text = " ".join(
                            part.get("text", "")
                            for part in text
                            if isinstance(part, dict)
                        )

                    logger.info("🧠 AI thinking: %s", text[:500])

                if msg.tool_calls:
                    for call in msg.tool_calls:
                        logger.info(
                            "🔧 Tool call: %s | args=%s",
                            call.get("name"),
                            call.get("args"),
                        )

            elif isinstance(msg, ToolMessage):
                logger.info(
                    "📦 Tool result [%s]: %s",
                    msg.name,
                    str(msg.content)[:500],
                )

        # Final response
        response = result.get("response")

        if not response:
            last = result["messages"][-1].content

            if isinstance(last, list):
                response = " ".join(
                    part.get("text", "")
                    for part in last
                    if isinstance(part, dict)
                )
            else:
                response = str(last)

        logger.info(
            "✅ Final response | session=%s | length=%d",
            session_id,
            len(response),
        )

        return response