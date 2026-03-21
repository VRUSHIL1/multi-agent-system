from __future__ import annotations

import logging

from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.executor_agent import ExecutorAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.state import AgentState

logger = logging.getLogger(__name__)

_memory = MemorySaver()


def build_agent_graph(
    llm: ChatGoogleGenerativeAI,
    tools: list[BaseTool],
) -> StateGraph:
    """
    Build and compile the Planner → Executor LangGraph.

    Graph flow:
        START → planner → executor → END

    Args:
        llm:   The ChatGoogleGenerativeAI instance shared by both agents.
        tools: The list of LangChain tools available to the Executor.

    Returns:
        A compiled LangGraph application (CompiledGraph).
    """
    planner = PlannerAgent(llm=llm, tools=tools)
    executor = ExecutorAgent(llm=llm, tools=tools)

    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("planner", planner.run)
    graph.add_node("executor", executor.run)

    # Define edges
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", END)

    logger.info("🕸️  Agent graph compiled: START → planner → executor → END")
    return graph.compile(checkpointer=_memory)
