from __future__ import annotations

from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """Shared state passed between Planner and Executor nodes."""

    # Full conversation history — add_messages reducer appends new messages
    messages: Annotated[list[BaseMessage], add_messages]

    # Step-by-step plan produced by the Planner
    plan: list[str]

    # Final synthesized response produced by the Executor
    response: str
