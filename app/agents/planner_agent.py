from __future__ import annotations

import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agents.state import AgentState
from app.prompts.planner_prompt import PLANNER_PROMPT

logger = logging.getLogger(__name__)


class PlannerAgent:
    """
    Planner node in the LangGraph pipeline.

    Reads the latest user message from state, asks the LLM to produce
    a numbered step-by-step plan, and stores the plan back in state.
    """

    def __init__(self, llm: ChatGoogleGenerativeAI) -> None:
        self.llm = llm

    async def run(self, state: AgentState) -> dict:
        # Extract the most recent human message
        user_message = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                user_message = msg.content if isinstance(msg.content, str) else str(msg.content)
                break

        logger.info("🗂️  Planner | analysing: %s", user_message[:200])

        prompt = PLANNER_PROMPT.format(user_message=user_message)

        response = await self.llm.ainvoke(
            [
                SystemMessage(content=prompt),
                HumanMessage(content=user_message),
            ]
        )

        raw_plan = response.content if isinstance(response.content, str) else str(response.content)
        logger.info("📋 Planner | raw plan:\n%s", raw_plan)

        # Parse numbered lines → list of steps
        steps = self._parse_plan(raw_plan)
        logger.info("📋 Planner | parsed %d step(s): %s", len(steps), steps)

        return {"plan": steps}

    @staticmethod
    def _parse_plan(text: str) -> list[str]:
        """Extract numbered plan steps from LLM output."""
        lines = text.strip().splitlines()
        steps: list[str] = []
        for line in lines:
            # Match lines like "1. Do something" or "1) Do something"
            match = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
            if match:
                steps.append(match.group(1).strip())
        # Fallback: return entire text as a single step
        if not steps:
            stripped = text.strip()
            if stripped:
                steps = [stripped]
        return steps
