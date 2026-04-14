from __future__ import annotations

from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """Shared state passed between Orchestrator, Planner and Executor nodes."""

    # Full conversation history — add_messages reducer appends new messages
    messages: Annotated[list[BaseMessage], add_messages]

    # Routing decision from orchestrator: "direct", "tool", or "planner"
    route: str

    # Current task being generated/executed by Planner
    current_task: dict | None

    # Results from each executed task (accumulated)
    results: list[str]

    # Final synthesized response produced by the Supervisor
    response: str
