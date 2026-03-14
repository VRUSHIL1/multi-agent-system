from __future__ import annotations

import logging

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agents.graph import build_agent_graph
from app.common.settings import settings
from app.tools import get_langchain_tools

logger = logging.getLogger(__name__)


class GeminiAgent:
    def __init__(self, *, model_name: str | None = None) -> None:
        if not settings.gemini_api_key:
            raise RuntimeError("Gemini API key not configured")

        self.model_name = model_name or settings.gemini_model

        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=settings.gemini_api_key,
            temperature=0.7,
        )

        self.tools = get_langchain_tools()

        # Planner → Executor LangGraph pipeline
        self.agent = build_agent_graph(llm=self.llm, tools=self.tools)

    async def generate_response(self, message: str, session_id: int) -> str:
        logger.info("📩 User message | session=%s | message=%s", session_id, message)

        result = await self.agent.ainvoke(
            {"messages": [{"role": "user", "content": message}]},
            config={"configurable": {"thread_id": str(session_id)}},
        )

        # Log full agent reasoning chain
        for msg in result["messages"]:
            if isinstance(msg, HumanMessage):
                continue  # already logged above

            if isinstance(msg, AIMessage):
                if msg.content:
                    text = msg.content
                    if isinstance(text, list):
                        text = " ".join(
                            p.get("text", "") for p in text if isinstance(p, dict)
                        )
                    logger.info("🧠 AI thinking: %s", text[:500])

                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        logger.info(
                            "🔧 Tool call: %s | args: %s",
                            tc.get("name", "unknown"),
                            tc.get("args", {}),
                        )

            elif isinstance(msg, ToolMessage):
                logger.info(
                    "📦 Tool result [%s]: %s",
                    msg.name,
                    str(msg.content)[:500],
                )

        # Prefer the dedicated `response` field set by the executor;
        # fall back to the last AI message content for safety
        content: str = result.get("response", "")
        if not content:
            last = result["messages"][-1].content
            content = (
                " ".join(p.get("text", "") for p in last if isinstance(p, dict))
                if isinstance(last, list)
                else str(last)
            )

        logger.info("✅ Final response | session=%s | length=%d", session_id, len(content))
        return content
