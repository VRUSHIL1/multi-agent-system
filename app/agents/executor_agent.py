from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agents import AgentState

logger = logging.getLogger(__name__)

# Constants
MAX_RETRIES: int = 2
TOOL_TIMEOUT_SECONDS: int = 30


class ExecutorAgent:
    """
    Production-grade Executor Agent.
    """

    def __init__(self, llm: ChatGoogleGenerativeAI, tools: list[BaseTool]) -> None:
        self.llm = llm
        self.tools = tools
        self.tool_map: dict[str, BaseTool] = {t.name: t for t in tools}

    # Public entry point

    async def run(self, state: AgentState) -> dict[str, Any]:
        """Execute the current task and return an updated state slice."""

        # 1. Get current task from state
        current_task = state.get("current_task")

        if not current_task:
            raise ValueError("Executor called with no current_task in state")

        # 2. Parse structured task
        tool_name, tool_args, task_description = self._parse_task(current_task)

        logger.info(
            "⚙️  Executor | executing task | tool=%s | desc=%s",
            tool_name,
            task_description,
        )

        # 3. Strict tool resolution
        tool = self.tool_map.get(tool_name)

        if tool is None:
            error_msg = (
                f"No registered tool matches '{tool_name}'. "
                f"Available tools: {list(self.tool_map.keys())}"
            )
            logger.error("❌ Executor | %s", error_msg)
            return self._build_response(state, error_msg)

        logger.info("🔒 Executor | locked tool: %s", tool.name)

        # 4. Replace placeholders in tool args with actual results
        tool_args = self._inject_results_into_args(tool_args, state.get("results", []))

        logger.info("📥 Executor | tool_args: %s", tool_args)

        # 5. Execute tool with retry + timeout
        result_str = await self._execute_with_retry(tool, tool_args)

        logger.info(
            "📦 Executor | result [%s]: %s",
            tool.name,
            result_str[:300],
        )

        return self._build_response(state, result_str)

    # Private helpers

    def _parse_task(self, task: Any) -> tuple[str, dict[str, Any], str]:
        """
        Parse a task into ``(tool_name, tool_args, description)``
        """
        if isinstance(task, dict):
            tool_name: str = task.get("tool", "").strip()
            tool_args: dict[str, Any] = task.get("args", {}) or {}
            description: str = task.get("description", tool_name)

            if not tool_name:
                raise ValueError(f"Task dict is missing required 'tool' key: {task}")

            return tool_name, tool_args, description

        if isinstance(task, str):
            # Legacy: "tool_name: free-text description"
            parts = task.split(":", maxsplit=1)
            tool_name = parts[0].strip()
            description = parts[1].strip() if len(parts) > 1 else tool_name
            return tool_name, {}, description

        raise TypeError(
            f"Unsupported task type: {type(task).__name__}. Expected dict or str."
        )

    async def _execute_with_retry(
        self,
        tool: BaseTool,
        tool_args: dict[str, Any],
    ) -> str:
        """
        Invoke ``tool`` with ``tool_args``, retrying up to ``MAX_RETRIES`` times.
        Each attempt is subject to ``TOOL_TIMEOUT_SECONDS``.
        """
        last_error: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(
                    "🔧 Executor | calling %s | attempt %d/%d",
                    tool.name,
                    attempt,
                    MAX_RETRIES,
                )

                result = await asyncio.wait_for(
                    tool.ainvoke(tool_args),
                    timeout=TOOL_TIMEOUT_SECONDS,
                )
                return str(result)

            except asyncio.TimeoutError as exc:
                last_error = exc
                logger.error(
                    "⏱️  Executor | tool '%s' timed out after %ds (attempt %d)",
                    tool.name,
                    TOOL_TIMEOUT_SECONDS,
                    attempt,
                )

            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.error(
                    "❌ Executor | tool '%s' raised on attempt %d: %s",
                    tool.name,
                    attempt,
                    exc,
                )

        return f"Tool '{tool.name}' failed after {MAX_RETRIES} attempts: {last_error}"

    @staticmethod
    def _inject_results_into_args(
        args: dict[str, Any], results: list[str]
    ) -> dict[str, Any]:
        """
        Replace placeholders in tool arguments with actual task results.
        Supports patterns like {step_1.result}, {step_2.result}, {tool_output:1}, etc.
        """
        import re

        def replace_placeholder(match):
            index_str = match.group(1)
            try:
                index = int(index_str) - 1  # Convert to 0-based index
                if 0 <= index < len(results):
                    return results[index]
            except (ValueError, IndexError):
                pass
            return match.group(0)  # Return original if can't replace

        # Recursively replace in all string values
        def process_value(value: Any) -> Any:
            if isinstance(value, str):
                return re.sub(
                    r"\{(?:step_|tool_output:)(\d+)(?:\.result)?\}",
                    replace_placeholder,
                    value,
                )
            elif isinstance(value, dict):
                return {k: process_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [process_value(v) for v in value]
            return value

        result = process_value(args)
        # Ensure we always return a dict
        return result if isinstance(result, dict) else args

    def _build_response(
        self,
        state: AgentState,
        result: str,
    ) -> dict[str, Any]:
        """Return an immutable state update slice."""
        updated_results = [*state.get("results", []), result]

        logger.info(
            "✅ Executor | task complete | result_length=%d",
            len(result),
        )

        return {
            "results": updated_results,
            "messages": [AIMessage(content=result)],
            "current_task": None,  # Clear task after execution
        }
