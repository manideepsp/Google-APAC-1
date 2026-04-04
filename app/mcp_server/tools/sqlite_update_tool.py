from app.db.sqlite import set_task_live, update_task_status

_ALLOWED_STATUS = {"TODO", "IN_PROGRESS", "COMPLETED", "OUT_OF_SCOPE"}


def sqlite_update_tool(
    user_id: str,
    task_uuid: str,
    status: str | None = None,
    live: bool | None = None,
) -> dict:
    """Update task lifecycle fields for a user-owned task in SQLite."""
    if status is not None:
        if status not in _ALLOWED_STATUS:
            raise ValueError(f"Invalid status: {status}")
        update_task_status(task_uuid, status, user_id=user_id)

    if live is not None:
        set_task_live(task_uuid, live, user_id=user_id)

    return {
        "user_id": user_id,
        "uuid": task_uuid,
        "status": status,
        "live": live,
        "updated": True,
    }
