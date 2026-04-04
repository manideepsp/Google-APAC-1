from app.adk.workflow_agents import plan_tasks_with_adk
def planning_agent(state: dict):
    goal = state.get("goal", "")
    research = state.get("research", {})

    insights = research.get("insights", "")
    titles = research.get("titles", [])

    tasks = plan_tasks_with_adk(goal=goal, titles=titles, insights=insights)

    state["tasks"] = tasks
    return state