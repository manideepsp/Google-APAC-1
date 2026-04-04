from app.db.sqlite import get_active_tasks
from app.services.sheets_client import clear_tasks, add_task


def sync_tasks_to_sheets():
    tasks = get_active_tasks()

    # Clear sheet first so it mirrors active DB tasks.
    clear_tasks()

    for task in tasks:
        add_task(
            task=task["task"],
            status=task["status"],
            priority=task["priority"],
            day=task["day"],
        )
