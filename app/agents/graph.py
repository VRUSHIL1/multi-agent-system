from __future__ import annotations

import logging

from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.executor_agent import ExecutorAgent
from app.agents.orchestrator_agent import OrchestratorAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.state import AgentState

logger = logging.getLogger(__name__)

_memory = MemorySaver()


def route_from_orchestrator(state: AgentState) -> str:
    """Route based on orchestrator decision."""
    route = state.get("route", "planner")
    if route == "direct":
        return "end"  # Direct answers handled in orchestrator
    if route == "tool":
        return "executor"
    return "planner"


def should_continue_planner(state: AgentState) -> str:
    """Routing after planner: proceed to executor if a task was planned, else end."""
    current_task = state.get("current_task")
    if current_task:
        return "executor"
    return "end"


def should_continue_executor(state: AgentState) -> str:
    """Routing after executor: check if we came from orchestrator or planner."""
    route = state.get("route", "planner")
    if route == "tool":
        return "end"
    return "planner"


def build_agent_graph(
    llm: ChatGoogleGenerativeAI,
    tools: list[BaseTool],
) -> CompiledStateGraph:
    """
    Build and compile the Orchestrator-driven LangGraph with dynamic planning loop.

    Graph flow:
        START → orchestrator (decide route) → [direct/tool/planner] → executor → planner → ... → END

    Args:
        llm:   The ChatGoogleGenerativeAI instance shared by all agents.
        tools: The list of LangChain tools available to the Executor.

    Returns:
        A compiled LangGraph application (CompiledGraph).
    """
    orchestrator = OrchestratorAgent(llm=llm, tools=tools)
    planner = PlannerAgent(llm=llm, tools=tools)
    executor = ExecutorAgent(llm=llm, tools=tools)

    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("orchestrator", orchestrator.run)
    graph.add_node("planner", planner.run)
    graph.add_node("executor", executor.run)

    # Define edges
    graph.add_edge(START, "orchestrator")

    # Route from orchestrator
    graph.add_conditional_edges(
        "orchestrator",
        route_from_orchestrator,
        {
            "end": END,  # Direct answers handled in orchestrator
            "executor": "executor",
            "planner": "planner",
        },
    )

    # Conditional routing: after planner, execute if a task was planned
    graph.add_conditional_edges(
        "planner",
        should_continue_planner,
        {
            "executor": "executor",
            "end": END,
        },
    )

    # After executor, check if single tool or loop back to planner
    graph.add_conditional_edges(
        "executor",
        should_continue_executor,
        {
            "end": END,
            "planner": "planner",
        },
    )

    logger.info(
        "🕸️  Agent graph compiled: START → orchestrator → [direct/tool/planner] → executor → planner → ... → END"
    )
    return graph.compile(checkpointer=_memory)
