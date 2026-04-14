from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.agents.state import AgentState
from app.prompts.orchestrator_prompt import DIRECT_ANSWER_SYSTEM, ROUTING_SYSTEM

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class OrchestratorConfig:
    """Centralised knobs — override via env vars or dependency injection."""

    # LLM call limits
    LLM_TIMEOUT_SECONDS: float = 20.0
    MAX_RETRIES: int = 3
    RETRY_WAIT_MIN: float = 1.0
    RETRY_WAIT_MAX: float = 8.0

    # Context window management
    MAX_HISTORY_MESSAGES: int = 10  # rolling window kept per call
    MAX_INPUT_CHARS: int = 8_000  # hard cap on raw user message

    # Guard rails
    INJECTION_PATTERNS: list[str] = [
        r"ignore\s+(all\s+|previous\s+)?instructions",
        r"disregard\s+(all\s+|your\s+)?",
        r"you\s+are\s+now\s+",
        r"jailbreak",
        r"act\s+as\s+(?:an?\s+)?(?:evil|unrestricted|dan)",
    ]


# ---------------------------------------------------------------------------
# Result contract
# ---------------------------------------------------------------------------


@dataclass
class OrchestratorResult:
    """Uniform return type regardless of which route was taken."""

    response: str  # final text to send to the user
    route: Literal["direct", "tool", "planner", "error"]
    trace_id: str
    tool_name: str | None = None  # populated only for route="tool"
    tool_args: dict = field(default_factory=dict)
    partial: bool = False  # True when a timeout forced early exit
    error: str | None = None  # human-readable error reason if any
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0

    def to_state_patch(self) -> dict:
        """Convert to the dict shape that LangGraph state expects."""
        patch: dict = {"route": self.route}
        if self.route == "direct":
            patch["response"] = self.response
            patch["results"] = [self.response]
        elif self.route == "tool":
            patch["current_task"] = {
                "tool": self.tool_name,
                "args": self.tool_args,
                "description": f"Execute {self.tool_name}",
            }
        # planner / error: downstream nodes read state themselves
        return patch


# ---------------------------------------------------------------------------
# Structured routing decision (replaces brittle JSON regex)
# ---------------------------------------------------------------------------


class RoutingDecision(BaseModel):
    decision: Literal["DIRECT", "TOOL", "PLANNER"] = Field(
        description="Routing decision"
    )
    reasoning: str = Field(description="One-sentence explanation")
    tool: str | None = Field(default=None, description="Tool name if decision=TOOL")
    args: dict = Field(
        default_factory=dict, description="Tool arguments if decision=TOOL"
    )


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class OrchestratorAgent:
    """
    Production orchestrator — entry point for all agent requests.

    Usage
    -----
    orchestrator = OrchestratorAgent(llm=llm, tools=tools)
    result: OrchestratorResult = await orchestrator.run(state)
    state_patch = result.to_state_patch()   # feed to LangGraph
    """

    def __init__(
        self,
        llm: ChatGoogleGenerativeAI,
        tools: list[BaseTool],
        config: OrchestratorConfig | None = None,
    ) -> None:
        self.llm = llm
        self.tools = tools
        self.tool_map: dict[str, BaseTool] = {t.name: t for t in tools}
        self.config = config or OrchestratorConfig()

        # Structured output variant — eliminates JSON regex parsing
        self._routing_llm = llm.with_structured_output(RoutingDecision)

        # Compile injection patterns once
        self._injection_re = re.compile("|".join(self.config.INJECTION_PATTERNS), re.I)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self, state: AgentState) -> dict:
        """
        Full production pipeline:
          guard → context → route → (answer | delegate) → log → return

        Returns dict for LangGraph state update.
        """
        trace_id = str(uuid.uuid4())
        t_start = time.monotonic()
        result = OrchestratorResult(response="", route="error", trace_id=trace_id)

        try:
            # ── 1. Extract & validate user message ──────────────────────
            user_message = self._extract_user_message(state)
            guard_error = self._guard_rails(user_message)
            if guard_error:
                result.response = guard_error
                result.route = "direct"
                return result.to_state_patch()

            logger.info("🧭 [%s] Orchestrator | input: %.120s", trace_id, user_message)

            # ── 2. Build trimmed context ─────────────────────────────────
            history_summary = self._build_history_summary(state)
            tool_list = self._build_tool_list()

            # ── 3. Routing decision via structured LLM call ──────────────
            routing_system = ROUTING_SYSTEM.format(
                tool_list=tool_list,
                history_summary=history_summary,
            )
            decision: RoutingDecision = await self._invoke_routing(
                routing_system, user_message, trace_id
            )

            logger.info(
                "🧭 [%s] decision=%s tool=%s | %s",
                trace_id,
                decision.decision,
                decision.tool,
                decision.reasoning[:120],
            )

            # ── 4. Handle each route ─────────────────────────────────────
            if decision.decision == "DIRECT":
                answer, in_tok, out_tok = await self._generate_direct_answer(
                    user_message, history_summary, trace_id
                )
                result.response = answer
                result.route = "direct"
                result.input_tokens = in_tok
                result.output_tokens = out_tok

            elif decision.decision == "TOOL":
                tool_name = decision.tool or ""
                if not tool_name or tool_name not in self.tool_map:
                    logger.warning(
                        "⚠️  [%s] Unknown tool '%s' → falling back to planner",
                        trace_id,
                        tool_name,
                    )
                    result.route = "planner"
                else:
                    validated_args = self._validate_tool_args(
                        tool_name, decision.args, trace_id
                    )
                    result.route = "tool"
                    result.tool_name = tool_name
                    result.tool_args = validated_args
                    result.response = f"Executing tool: {tool_name}"

            else:  # PLANNER
                result.route = "planner"
                result.response = ""

        except asyncio.TimeoutError:
            logger.error(
                "⏱️  [%s] Orchestrator timed out — returning planner fallback", trace_id
            )
            result.route = "planner"
            result.partial = True
            result.error = "timeout"

        except Exception as exc:  # noqa: BLE001
            logger.exception("💥 [%s] Orchestrator unhandled error: %s", trace_id, exc)
            result.route = "error"
            result.error = str(exc)
            result.response = "I encountered an unexpected error. Please try again."

        finally:
            result.latency_ms = round((time.monotonic() - t_start) * 1000, 1)
            self._emit_trace(trace_id, result)

        return result.to_state_patch()

    # ------------------------------------------------------------------
    # Guard rails
    # ------------------------------------------------------------------

    def _guard_rails(self, message: str) -> str | None:
        """
        Return an error string if the message should be blocked,
        or None if it is safe to proceed.
        """
        if not message or not message.strip():
            return "I didn't receive a message. Please try again."

        if len(message) > self.config.MAX_INPUT_CHARS:
            return (
                f"Your message is too long ({len(message):,} characters). "
                f"Please keep it under {self.config.MAX_INPUT_CHARS:,} characters."
            )

        if self._injection_re.search(message):
            logger.warning("🚨 Prompt injection attempt detected and blocked.")
            return "I'm not able to process that request."

        return None

    # ------------------------------------------------------------------
    # Context builder
    # ------------------------------------------------------------------

    def _extract_user_message(self, state: AgentState) -> str:
        """Return the most recent HumanMessage content."""
        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, HumanMessage):
                return msg.content if isinstance(msg.content, str) else str(msg.content)
        return ""

    def _build_history_summary(self, state: AgentState) -> str:
        """
        Return a trimmed, human-readable conversation history.
        Keeps only the last MAX_HISTORY_MESSAGES messages.
        """
        messages = state.get("messages", [])
        recent = messages[-self.config.MAX_HISTORY_MESSAGES :]
        lines: list[str] = []
        for msg in recent:
            if isinstance(msg, HumanMessage):
                lines.append(f"User: {str(msg.content)[:300]}")
            elif isinstance(msg, AIMessage):
                lines.append(f"Assistant: {str(msg.content)[:300]}")
        return "\n".join(lines) if lines else "No prior conversation."

    def _build_tool_list(self) -> str:
        """Render tool names + descriptions for the routing prompt."""
        return (
            "\n".join(f"- {t.name}: {t.description}" for t in self.tools)
            or "No tools available."
        )

    # ------------------------------------------------------------------
    # LLM calls — with retry + timeout
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception_type((asyncio.TimeoutError, Exception)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=8),
        reraise=True,
    )
    async def _invoke_routing(
        self, system: str, user_message: str, trace_id: str
    ) -> RoutingDecision:
        """Call the structured routing LLM with timeout + retry."""
        logger.debug("🔁 [%s] Routing LLM call", trace_id)
        result = await asyncio.wait_for(
            self._routing_llm.ainvoke(
                [
                    SystemMessage(content=system),
                    HumanMessage(content=user_message),
                ]
            ),
            timeout=self.config.LLM_TIMEOUT_SECONDS,
        )
        # Ensure we return a RoutingDecision instance
        if isinstance(result, RoutingDecision):
            return result
        # Fallback if structured output fails
        return RoutingDecision(
            decision="PLANNER",
            reasoning="Fallback to planner due to parsing error",
        )

    @retry(
        retry=retry_if_exception_type((asyncio.TimeoutError, Exception)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=8),
        reraise=True,
    )
    async def _generate_direct_answer(
        self, user_message: str, history: str, trace_id: str
    ) -> tuple[str, int, int]:
        """
        Generate a direct answer. Returns (text, input_tokens, output_tokens).
        Token counts come from the LLM usage metadata when available.
        """
        logger.debug("🔁 [%s] Direct answer LLM call", trace_id)
        system_prompt = DIRECT_ANSWER_SYSTEM + (
            f"\n\nConversation so far:\n{history}" if history else ""
        )
        response = await asyncio.wait_for(
            self.llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_message),
                ]
            ),
            timeout=self.config.LLM_TIMEOUT_SECONDS,
        )
        text = (
            response.content
            if isinstance(response.content, str)
            else str(response.content)
        )

        # Extract token usage if the provider returns it
        usage = getattr(response, "usage_metadata", None) or {}
        in_tok = usage.get("input_tokens", 0)
        out_tok = usage.get("output_tokens", 0)

        return text, in_tok, out_tok

    # ------------------------------------------------------------------
    # Tool argument validation
    # ------------------------------------------------------------------

    def _validate_tool_args(self, tool_name: str, args: dict, trace_id: str) -> dict:
        """
        Validate that args conform to the tool's expected schema.
        Falls back to raw args if schema introspection is unavailable.
        """
        tool = self.tool_map[tool_name]
        schema = getattr(tool, "args_schema", None)
        if schema is None:
            return args  # no schema — pass through

        try:
            validated = schema(**args)
            return validated.dict()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "⚠️  [%s] Tool arg validation failed for '%s': %s — using raw args",
                trace_id,
                tool_name,
                exc,
            )
            return args

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def _emit_trace(self, trace_id: str, result: OrchestratorResult) -> None:
        """Emit a structured JSON trace line for log aggregation pipelines."""
        logger.info(
            json.dumps(
                {
                    "event": "orchestrator_trace",
                    "trace_id": trace_id,
                    "route": result.route,
                    "tool": result.tool_name,
                    "latency_ms": result.latency_ms,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "partial": result.partial,
                    "error": result.error,
                }
            )
        )
