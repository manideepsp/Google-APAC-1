import logging

from app.db.sqlite import get_active_tasks_by_user
from app.services.sheets_client import clear_tasks, add_task


LOGGER = logging.getLogger(__name__)


def sync_tasks_to_sheets(user_id=None):
    tasks = get_active_tasks_by_user(user_id)

    # Clear sheet first so it mirrors active DB tasks.
    try:
        clear_tasks()
    except Exception as exc:
        LOGGER.warning("Sheets clear failed for user %s: %s", user_id, exc)
        return

    for task in tasks:
        try:
            add_task(
                task=task["task"],
                status=task["status"],
                priority=task["priority"],
                day=task["day"],
            )
        except Exception as exc:
            LOGGER.warning("Sheets add failed for user %s task %s: %s", user_id, task.get("uuid"), exc)
