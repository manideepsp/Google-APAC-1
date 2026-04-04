from app.db.sqlite import get_active_tasks_by_user
from app.services.sheets_sync import sync_tasks_to_sheets


def sheets_sync_tool(user_id: str) -> dict:
    """Sync active tasks for a user from SQLite to Sheets via gRPC-backed client."""
    sync_tasks_to_sheets(user_id=user_id)
    active_count = len(get_active_tasks_by_user(user_id))
    return {
        "user_id": user_id,
        "active_task_count": active_count,
        "synced": True,
    }
