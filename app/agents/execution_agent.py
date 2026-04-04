from app.adk.workflow_agents import execute_tasks_with_adk


def execution_agent(state: dict):
    tasks = state.get("tasks", [])
    user_id = state.get("user_id")

    if not tasks:
        return state

    execute_tasks_with_adk(tasks=tasks, user_id=user_id)

    return state