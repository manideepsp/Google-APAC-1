import sqlite3
import uuid
from datetime import datetime

DB_PATH = "tasks.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS tasks (
        uuid TEXT PRIMARY KEY,
        task TEXT,
        priority TEXT,
        day TEXT,
        status TEXT,
        live INTEGER,
        created_at TEXT,
        updated_at TEXT,
        parent_uuid TEXT
    )
    """
    )

    conn.commit()
    conn.close()


def insert_task(task, priority, day, parent_uuid=None):
    conn = get_connection()
    cursor = conn.cursor()

    task_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    cursor.execute(
        """
    INSERT INTO tasks (uuid, task, priority, day, status, live, created_at, updated_at, parent_uuid)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            task_id,
            task,
            priority,
            day,
            "TODO",
            1,
            now,
            now,
            parent_uuid,
        ),
    )

    conn.commit()
    conn.close()

    return task_id


def get_active_tasks():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
    SELECT uuid, task, priority, day, status
    FROM tasks
    WHERE live = 1 AND status != 'COMPLETED'
    ORDER BY day, created_at
    """
    )

    rows = cursor.fetchall()
    conn.close()

    tasks = []
    for row in rows:
        tasks.append(
            {
                "uuid": row[0],
                "task": row[1],
                "priority": row[2],
                "day": row[3],
                "status": row[4],
            }
        )

    return tasks


def soft_delete_task(task_uuid):
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.utcnow().isoformat()

    cursor.execute(
        """
    UPDATE tasks
    SET live = 0, updated_at = ?
    WHERE uuid = ?
    """,
        (now, task_uuid),
    )

    conn.commit()
    conn.close()


def update_task_status(task_uuid, status):
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.utcnow().isoformat()

    cursor.execute(
        """
    UPDATE tasks
    SET status = ?, updated_at = ?
    WHERE uuid = ?
    """,
        (status, now, task_uuid),
    )

    conn.commit()
    conn.close()


def replace_tasks(new_tasks):
    """Replace all active tasks with a new active set."""
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.utcnow().isoformat()

    cursor.execute(
        """
    UPDATE tasks
    SET live = 0, updated_at = ?
    WHERE live = 1
    """,
        (now,),
    )

    for task in new_tasks:
        cursor.execute(
            """
        INSERT INTO tasks (uuid, task, priority, day, status, live, created_at, updated_at, parent_uuid)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                str(uuid.uuid4()),
                task.get("task", ""),
                task.get("priority", "Medium"),
                task.get("day", "Day 1"),
                "TODO",
                1,
                now,
                now,
                None,
            ),
        )

    conn.commit()
    conn.close()
