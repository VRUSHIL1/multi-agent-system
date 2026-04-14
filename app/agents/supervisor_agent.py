"""
supervisor.py — Production-ready Supervisor Agent
==================================================
Role: Combine all task results into a single, coherent final response.

Responsibilities:
  1. Assert the agent is initialised before use
  2. Build initial LangGraph state from user message + optional context
  3. Invoke the LangGraph pipeline (Orchestrator → Planner → Executor)
  4. Aggregate all results via a final LLM call
  5. Return a clean string — or a safe fallback on any failure
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph.state import CompiledStateGraph

from app.agents import build_agent_graph
from app.agents import AgentState
from app.common import settings
from app.prompts import AGGREGATION_PROMPT
from app.tools import get_langchain_tools, get_mcp_langchain_tools

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_FALLBACK_RESPONSE = "I couldn't process your request. Please try again."

AGGREGATION_TIMEOUT_SECONDS = 30.0

# ---------------------------------------------------------------------------
# Supervisor
# ---------------------------------------------------------------------------


class SupervisorAgent:
    """
    Orchestrates the full agent pipeline and produces the final response.

    Lifecycle::

        supervisor = SupervisorAgent()
        await supervisor.initialize()
        reply = await supervisor.generate_response(message, session_id)
    """

    def __init__(self, *, model_name: str | None = None) -> None:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured.")

        self.model_name: str = model_name or settings.gemini_model
        self.tools: list[BaseTool] = []
        self.agent: CompiledStateGraph | None = None

        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=settings.gemini_api_key,
            temperature=0.5,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Load tools and compile the LangGraph graph. Call once before use."""
        local_tools = get_langchain_tools()
        mcp_tools = await get_mcp_langchain_tools()
        self.tools = [*local_tools, *mcp_tools]

        logger.info(
            "🧰 Supervisor | tools loaded | local=%d mcp=%d total=%d",
            len(local_tools),
            len(mcp_tools),
            len(self.tools),
        )

        self.agent = build_agent_graph(llm=self.llm, tools=self.tools)
        logger.info("✅ Supervisor | graph compiled | model=%s", self.model_name)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def generate_response(
        self,
        message: str,
        session_id: int,
        summary: str = "",
        memory_context: str = "",
    ) -> str:
        """
        Run the full pipeline and return a final response string.

        Args:
            message:        Latest user message.
            session_id:     LangGraph thread ID for checkpointing.
            summary:        Optional prior-conversation summary.
            memory_context: Optional long-term memory snippets.

        Returns:
            Aggregated reply string, or DEFAULT_FALLBACK_RESPONSE on failure.
        """
        self._assert_initialized()

        logger.info("🎯 Supervisor | session=%s | %.120s", session_id, message)

        # 1. Build state
        initial_state = self._build_initial_state(message, summary, memory_context)

        # 2. Run LangGraph
        try:
            assert self.agent is not None
            graph_result: dict[str, Any] = await self.agent.ainvoke(
                initial_state,
                config={"configurable": {"thread_id": str(session_id)}},
            )
        except Exception:
            logger.exception("💥 Supervisor | LangGraph invocation failed")
            return DEFAULT_FALLBACK_RESPONSE

        results: list[str] = graph_result.get("results", [])
        logger.info("✅ Supervisor | graph done | results=%d", len(results))

        # 3. Guard: nothing produced
        if not results:
            logger.warning("⚠️  Supervisor | no results — returning fallback")
            return DEFAULT_FALLBACK_RESPONSE

        # 4. Aggregate
        return await self._aggregate(message, results)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _assert_initialized(self) -> None:
        if self.agent is None:
            raise RuntimeError(
                "SupervisorAgent not initialised. "
                "Call `await supervisor.initialize()` first."
            )

    @staticmethod
    def _build_initial_state(
        message: str,
        summary: str,
        memory_context: str,
    ) -> AgentState:
        """Construct the initial LangGraph state."""
        messages: list[BaseMessage] = []

        if summary:
            messages.append(
                HumanMessage(content=f"Previous conversation summary:\n{summary}")
            )
        if memory_context:
            messages.append(
                HumanMessage(content=f"Relevant memories:\n{memory_context}")
            )

        messages.append(HumanMessage(content=message))

        return AgentState(
            messages=messages,
            route="",
            current_task=None,
            results=[],
            response="",
        )

    async def _aggregate(self, user_query: str, results: list[str]) -> str:
        """Synthesise all task results into one final reply."""
        logger.info("🧠 Supervisor | aggregating %d result(s)", len(results))

        task_results_text = "\n\n".join(
            f"Result {i + 1}:\n{r}" for i, r in enumerate(results)
        )
        prompt = AGGREGATION_PROMPT.format(
            user_query=user_query,
            task_results=task_results_text,
        )

        try:
            response = await asyncio.wait_for(
                self.llm.ainvoke(
                    [
                        SystemMessage(content=prompt),
                        HumanMessage(content=user_query),
                    ]
                ),
                timeout=AGGREGATION_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.error("⏱️  Supervisor | aggregation timed out")
            return DEFAULT_FALLBACK_RESPONSE
        except Exception:
            logger.exception("💥 Supervisor | aggregation LLM call failed")
            return DEFAULT_FALLBACK_RESPONSE

        return self._extract_text(response.content)

    @staticmethod
    def _extract_text(content: Any) -> str:
        """Normalise LLM response content to a plain string."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(
                block.get("text", "") for block in content if isinstance(block, dict)
            )
        return str(content)
