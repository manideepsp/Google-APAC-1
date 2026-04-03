from langgraph.graph import StateGraph

from app.agents.research_agent import research_agent
from app.agents.planning_agent import planning_agent
from app.agents.execution_agent import execution_agent


def build_graph():
    builder = StateGraph(dict)

    # Nodes
    builder.add_node("research", research_agent)
    builder.add_node("planning", planning_agent)
    builder.add_node("execution", execution_agent)

    # Flow
    builder.set_entry_point("research")

    builder.add_edge("research", "planning")
    builder.add_edge("planning", "execution")

    builder.set_finish_point("execution")

    return builder.compile()