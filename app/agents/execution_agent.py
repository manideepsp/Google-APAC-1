from app.db.sqlite import insert_task
from app.services.sheets_sync import sync_tasks_to_sheets


def execution_agent(state: dict):
    tasks = state.get("tasks", [])

    for task in tasks:
        try:
            insert_task(
                task=task.get("task", ""),
                priority=task.get("priority", "Medium"),
                day=task.get("day", "Day 1")
            )

        except Exception as e:
            print(f"Error inserting task in DB: {e}")

    try:
        sync_tasks_to_sheets()
    except Exception as e:
        print(f"Error syncing tasks to sheets: {e}")

    return state