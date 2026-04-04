from app.db.sqlite import get_active_tasks_by_user


def sqlite_read_tool(user_id: str) -> dict:
    """Read active tasks for a given user from SQLite."""
    tasks = get_active_tasks_by_user(user_id)
    return {
        "user_id": user_id,
        "tasks": tasks,
        "count": len(tasks),
    }
