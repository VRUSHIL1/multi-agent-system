from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agents import AgentState
from app.prompts import PLANNER_DYNAMIC_PROMPT

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_ITERATIONS: int = 20  # sanity cap — prevent infinite loops


class PlannerAgent:
    """
    Dynamic Planner node that generates ONE task at a time based on current results.
    After each executor task, Planner decides what (if anything) to do next.
    """

    def __init__(self, llm: ChatGoogleGenerativeAI, tools: list[BaseTool]) -> None:
        self.llm = llm
        self.tools = tools
        self.tool_map: dict[str, BaseTool] = {t.name: t for t in tools}

    async def run(self, state: AgentState) -> dict:
        # ----------------------------------------------------------------
        # 1. Extract latest user message
        # ----------------------------------------------------------------
        user_message = self._extract_user_message(state)

        if not user_message:
            logger.warning("⚠️  Planner | no user message found in state")
            return {"current_task": None}

        # ----------------------------------------------------------------
        # 2. Get accumulated results so far
        # ----------------------------------------------------------------
        results_so_far = state.get("results", [])
        iteration = len(results_so_far)  # How many tasks have we completed?

        logger.info(
            "🗂️  Planner | iteration %d | analysing: %s",
            iteration,
            user_message[:100],
        )

        # ----------------------------------------------------------------
        # 3. Safety check: prevent infinite loops
        # ----------------------------------------------------------------
        if iteration >= MAX_ITERATIONS:
            logger.warning(
                "⚠️  Planner | reached max iterations (%d) — ending loop",
                MAX_ITERATIONS,
            )
            return {"current_task": None}

        # ----------------------------------------------------------------
        # 4. Build prompt with current context
        # ----------------------------------------------------------------
        tool_list = "\n".join(
            f"- {tool.name}: {tool.description}" for tool in self.tools
        )

        # Format results context for the prompt
        results_context = self._format_results_context(results_so_far)

        prompt = PLANNER_DYNAMIC_PROMPT.format(
            user_message=user_message,
            tool_list=tool_list,
            iteration=iteration,
            results_context=results_context,
        )

        # ----------------------------------------------------------------
        # 5. Call LLM to decide next task
        # ----------------------------------------------------------------
        response = await self.llm.ainvoke(
            [
                SystemMessage(content=prompt),
                HumanMessage(content=user_message),
            ]
        )

        raw_response = (
            response.content
            if isinstance(response.content, str)
            else str(response.content)
        )

        logger.info("📋 Planner | LLM response:\n%s", raw_response[:300])

        # ----------------------------------------------------------------
        # 6. Check for DONE first (priority over task parsing)
        # ----------------------------------------------------------------
        if self._is_done(raw_response):
            logger.info("✅ Planner | user request complete — ending loop")
            return {"current_task": None}

        # ----------------------------------------------------------------
        # 7. Try to parse next task
        # ----------------------------------------------------------------
        next_task = self._parse_next_task(raw_response)

        if next_task:
            logger.info(
                "📋 Planner | next task: tool=%s | desc=%s",
                next_task.get("tool"),
                next_task.get("description", "")[:100],
            )
            return {"current_task": next_task}

        # ----------------------------------------------------------------
        # 8. Failed to parse task or detect completion
        # ----------------------------------------------------------------
        logger.warning(
            "⚠️  Planner | failed to extract task or detect completion — ending"
        )
        return {"current_task": None}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_user_message(state: AgentState) -> str:
        """Return the content of the most recent HumanMessage in state."""
        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, HumanMessage):
                return msg.content if isinstance(msg.content, str) else str(msg.content)
        return ""

    @staticmethod
    def _format_results_context(results: list[str]) -> str:
        """Format accumulated results for inclusion in the prompt."""
        if not results:
            return "No results yet."

        lines = ["Results so far:"]
        for i, result in enumerate(results, 1):
            # Truncate long results for brevity
            truncated = result[:200] + ("..." if len(result) > 200 else "")
            lines.append(f"{i}. {truncated}")

        return "\n".join(lines)

    @staticmethod
    def _is_done(response: str) -> bool:
        """Check if the LLM responded with DONE/FINISH/COMPLETE."""
        text = response.strip().upper()
        done_keywords = ["DONE", "FINISHED", "COMPLETE", "END", "NO MORE", "NONE"]
        return any(keyword in text for keyword in done_keywords)

    def _parse_next_task(self, text: str) -> dict[str, Any] | None:
        """
        Extract the next task from LLM response.
        Expects either:
        - JSON: {"tool": "...", "args": {...}, "description": "..."}
        - Structured: "TASK: tool_name\nARGS: {...}\nDESC: ..."
        """
        # Try JSON extraction first
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                task = json.loads(match.group())
                if isinstance(task, dict) and "tool" in task:
                    tool_name = task.get("tool", "").strip()
                    if tool_name in self.tool_map:
                        return {
                            "tool": tool_name,
                            "args": task.get("args", {}),
                            "description": task.get(
                                "description", f"Execute {tool_name}"
                            ),
                        }
            except json.JSONDecodeError:
                pass

        # Fallback: try simple "tool_name: description" format
        lines = text.strip().split("\n")
        for line in lines:
            match = re.search(r"^(?:TASK)?\s*:\s*(\w+)\s*(.*)$", line)
            if match:
                tool_name = match.group(1).strip()
                if tool_name in self.tool_map:
                    return {
                        "tool": tool_name,
                        "args": {},
                        "description": match.group(2).strip() or f"Execute {tool_name}",
                    }

        return None
