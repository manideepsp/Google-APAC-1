from app.services.sheets_client import add_task


def execution_agent(state: dict):
    tasks = state.get("tasks", [])

    for task in tasks:
        try:
            add_task(
                task=task.get("task", ""),
                status="Pending",
                priority=task.get("priority", "Medium"),
                day=task.get("day", "Day 1")
            )
        except Exception as e:
            print(f"Error adding task: {e}")

    return state