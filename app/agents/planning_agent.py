from app.adk.workflow_agents import plan_tasks_with_adk
from app.db.alloydb import fetch_related_generation_tasks, record_generation_tasks


def planning_agent(state: dict):
    goal = state.get("goal", "")
    research = state.get("research", {})
    user_id = state.get("user_id")
    channel_id = state.get("channel_id")
    run_id = state.get("run_id")
    goal_params = state.get("goal_params", {})

    insights = research.get("insights", "")
    titles = research.get("titles", [])

    related_tasks = fetch_related_generation_tasks(
        user_id=user_id,
        channel_id=channel_id,
        goal_text=goal,
        goal_params=goal_params,
        research=research,
    )

    tasks = plan_tasks_with_adk(
        goal=goal,
        titles=titles,
        insights=insights,
        related_tasks=related_tasks,
    )

    memory_result = record_generation_tasks(
        user_id=user_id,
        run_id=run_id,
        channel_id=channel_id,
        goal_text=goal,
        goal_params=goal_params,
        tasks=tasks,
        research=research,
        metadata={
            "source": "planning_generation",
            "related_task_count": len(related_tasks),
        },
    )

    state["related_tasks"] = related_tasks
    state["alloydb_memory"] = memory_result
    state["generation_number"] = memory_result.get("generation_number")
    state["tasks"] = tasks
    return state