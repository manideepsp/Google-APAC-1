from app.agents.execution_agent import execution_agent
from app.agents.planning_agent import planning_agent
from app.agents.research_agent import research_agent


def run_goal_workflow_adk(state: dict) -> dict:
    """Execute the goal workflow sequentially with ADK-backed agents."""
    next_state = dict(state)
    next_state = research_agent(next_state)
    next_state = planning_agent(next_state)
    next_state = execution_agent(next_state)
    return next_state
