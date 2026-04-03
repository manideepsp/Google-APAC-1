from langgraph.graph import StateGraph
from app.agents.research_agent import research_agent

def build_graph():
    builder = StateGraph(dict)

    builder.add_node("research", research_agent)

    builder.set_entry_point("research")
    builder.set_finish_point("research")

    return builder.compile()