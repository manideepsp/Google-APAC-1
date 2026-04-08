from app.adk.workflow_agents import execute_tasks_with_adk


def execution_agent(state: dict):
    tasks = state.get("tasks", [])
    user_id = state.get("user_id")
    channel_id = state.get("channel_id")
    run_id = state.get("run_id")
    goal_params = state.get("goal_params", {})

    if not tasks:
        return state

    execute_tasks_with_adk(
        tasks=tasks,
        user_id=user_id,
        channel_id=channel_id,
        run_id=run_id,
        goal_params=goal_params,
    )

    return state