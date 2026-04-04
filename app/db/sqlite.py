import sqlite3
import uuid
from datetime import datetime, timezone

DB_PATH = "tasks.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def _table_columns(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def _is_expired(timestamp_iso):
    if not timestamp_iso:
        return True

    try:
        return datetime.fromisoformat(timestamp_iso) <= datetime.now(timezone.utc)
    except Exception:
        return True


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

    columns = _table_columns(cursor, "tasks")
    if "user_id" not in columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN user_id TEXT")

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS users (
        uuid TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT,
        updated_at TEXT
    )
    """
    )

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS sessions (
        token_hash TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        created_at TEXT,
        expires_at TEXT
    )
    """
    )

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS password_resets (
        token_hash TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        used INTEGER DEFAULT 0,
        created_at TEXT,
        expires_at TEXT
    )
    """
    )

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_live ON tasks(user_id, live, status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_updated_at ON tasks(updated_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_password_resets_user_id ON password_resets(user_id)")

    conn.commit()
    conn.close()


def insert_task(task, priority, day, parent_uuid=None, user_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    task_id = str(uuid.uuid4())
    now = _utc_now_iso()

    cursor.execute(
        """
    INSERT INTO tasks (uuid, task, priority, day, status, live, created_at, updated_at, parent_uuid, user_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            user_id,
        ),
    )

    conn.commit()
    conn.close()

    return task_id


def get_active_tasks():
    return get_active_tasks_by_user(None)


def get_active_tasks_by_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    if user_id:
        cursor.execute(
            """
        SELECT uuid, task, priority, day, status, live
        FROM tasks
        WHERE user_id = ? AND live = 1 AND status != 'COMPLETED'
        ORDER BY day, created_at
        """,
            (user_id,),
        )
    else:
        cursor.execute(
            """
        SELECT uuid, task, priority, day, status, live
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
                "live": row[5],
            }
        )

    return tasks


def get_all_tasks():
    return get_all_tasks_by_user(None)


def get_all_tasks_by_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    if user_id:
        cursor.execute(
            """
        SELECT uuid, task, priority, day, status, live, created_at, updated_at, parent_uuid, user_id
        FROM tasks
        WHERE user_id = ?
        ORDER BY updated_at DESC, created_at DESC
        """,
            (user_id,),
        )
    else:
        cursor.execute(
            """
        SELECT uuid, task, priority, day, status, live, created_at, updated_at, parent_uuid, user_id
        FROM tasks
        ORDER BY updated_at DESC, created_at DESC
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
                "live": row[5],
                "created_at": row[6],
                "updated_at": row[7],
                "parent_uuid": row[8],
                "user_id": row[9],
            }
        )

    return tasks


def soft_delete_task(task_uuid, user_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    now = _utc_now_iso()

    if user_id:
        cursor.execute(
            """
        UPDATE tasks
        SET live = 0, updated_at = ?
        WHERE uuid = ? AND user_id = ?
        """,
            (now, task_uuid, user_id),
        )
    else:
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


def update_task_status(task_uuid, status, user_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    now = _utc_now_iso()

    if user_id:
        cursor.execute(
            """
        UPDATE tasks
        SET status = ?, updated_at = ?
        WHERE uuid = ? AND user_id = ?
        """,
            (status, now, task_uuid, user_id),
        )
    else:
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


def set_task_live(task_uuid, live, user_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    now = _utc_now_iso()

    if user_id:
        cursor.execute(
            """
        UPDATE tasks
        SET live = ?, updated_at = ?
        WHERE uuid = ? AND user_id = ?
        """,
            (1 if live else 0, now, task_uuid, user_id),
        )
    else:
        cursor.execute(
            """
        UPDATE tasks
        SET live = ?, updated_at = ?
        WHERE uuid = ?
        """,
            (1 if live else 0, now, task_uuid),
        )

    conn.commit()
    conn.close()


def replace_tasks(new_tasks, user_id=None):
    """Replace all active tasks with a new active set."""
    conn = get_connection()
    cursor = conn.cursor()

    now = _utc_now_iso()

    if user_id:
        cursor.execute(
            """
        UPDATE tasks
        SET live = 0, updated_at = ?
        WHERE live = 1 AND user_id = ?
        """,
            (now, user_id),
        )
    else:
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
        INSERT INTO tasks (uuid, task, priority, day, status, live, created_at, updated_at, parent_uuid, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                user_id,
            ),
        )

    conn.commit()
    conn.close()


def create_user(email, password_hash):
    conn = get_connection()
    cursor = conn.cursor()
    now = _utc_now_iso()
    user_id = str(uuid.uuid4())

    try:
        cursor.execute(
            """
        INSERT INTO users (uuid, email, password_hash, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
            (user_id, email, password_hash, now, now),
        )
        conn.commit()
        return {"id": user_id, "email": email}
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT uuid, email, password_hash FROM users WHERE email = ?",
        (email,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "email": row[1],
        "password_hash": row[2],
    }


def create_session(user_id, token_hash, expires_at):
    conn = get_connection()
    cursor = conn.cursor()
    now = _utc_now_iso()
    cursor.execute(
        """
    INSERT INTO sessions (token_hash, user_id, created_at, expires_at)
    VALUES (?, ?, ?, ?)
    """,
        (token_hash, user_id, now, expires_at),
    )
    conn.commit()
    conn.close()


def delete_session(token_hash):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
    conn.commit()
    conn.close()


def get_user_by_session(token_hash):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
    SELECT u.uuid, u.email, s.expires_at
    FROM sessions s
    JOIN users u ON u.uuid = s.user_id
    WHERE s.token_hash = ?
    """,
        (token_hash,),
    )
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    if _is_expired(row[2]):
        cursor.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
        conn.commit()
        conn.close()
        return None

    conn.close()
    return {
        "id": row[0],
        "email": row[1],
    }


def create_password_reset(user_id, token_hash, expires_at):
    conn = get_connection()
    cursor = conn.cursor()
    now = _utc_now_iso()

    cursor.execute("UPDATE password_resets SET used = 1 WHERE user_id = ? AND used = 0", (user_id,))
    cursor.execute(
        """
    INSERT INTO password_resets (token_hash, user_id, used, created_at, expires_at)
    VALUES (?, ?, 0, ?, ?)
    """,
        (token_hash, user_id, now, expires_at),
    )
    conn.commit()
    conn.close()


def get_password_reset(token_hash):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
    SELECT token_hash, user_id, used, expires_at
    FROM password_resets
    WHERE token_hash = ?
    """,
        (token_hash,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    if row[2] == 1 or _is_expired(row[3]):
        return None

    return {
        "token_hash": row[0],
        "user_id": row[1],
    }


def mark_password_reset_used(token_hash):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE password_resets SET used = 1 WHERE token_hash = ?", (token_hash,))
    conn.commit()
    conn.close()


def update_user_password_hash(user_id, password_hash):
    conn = get_connection()
    cursor = conn.cursor()
    now = _utc_now_iso()
    cursor.execute(
        """
    UPDATE users
    SET password_hash = ?, updated_at = ?
    WHERE uuid = ?
    """,
        (password_hash, now, user_id),
    )
    conn.commit()
    conn.close()
