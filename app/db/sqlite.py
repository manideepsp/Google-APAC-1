import json
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _default_db_path() -> str:
    configured = str(os.getenv("SQLITE_DB_PATH", "")).strip()
    if configured:
        return configured
    if os.getenv("K_SERVICE"):
        return "/tmp/tasks.db"
    return "tasks.db"


DB_PATH = _default_db_path()
SQLITE_TIMEOUT_SECONDS = 1.5
SQLITE_BUSY_TIMEOUT_MS = 1500
_TASK_WRITE_LOCK = threading.Lock()


def _ensure_db_parent(path: str) -> str:
    if path == ":memory:":
        return path
    resolved = Path(path).expanduser()
    if str(resolved.parent) not in {"", "."}:
        resolved.parent.mkdir(parents=True, exist_ok=True)
    return str(resolved)


def get_connection():
    db_path = _ensure_db_parent(DB_PATH)
    conn = sqlite3.connect(db_path, timeout=SQLITE_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def _table_columns(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def _safe_json_loads(value, default=None):
    if value is None:
        return {} if default is None else default
    try:
        return json.loads(value)
    except Exception:
        return {} if default is None else default


def _normalize_trace_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


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
    if "channel_id" not in columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN channel_id TEXT")
    if "run_id" not in columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN run_id TEXT")
    if "goal_params_json" not in columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN goal_params_json TEXT")
    if "origin_run_id" not in columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN origin_run_id TEXT")
    if "origin_context_json" not in columns:
        cursor.execute("ALTER TABLE tasks ADD COLUMN origin_context_json TEXT")

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

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS research_snapshots (
        user_id TEXT PRIMARY KEY,
        goal TEXT,
        channel_id TEXT,
        research_json TEXT NOT NULL,
        updated_at TEXT
    )
    """
    )

    research_columns = _table_columns(cursor, "research_snapshots")
    if "channel_id" not in research_columns:
        cursor.execute("ALTER TABLE research_snapshots ADD COLUMN channel_id TEXT")

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS research_snapshots_channel (
        user_id TEXT NOT NULL,
        channel_id TEXT NOT NULL,
        goal TEXT,
        research_json TEXT NOT NULL,
        updated_at TEXT,
        PRIMARY KEY (user_id, channel_id)
    )
    """
    )

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS strategy_runs (
        run_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        channel_id TEXT,
        goal_text TEXT,
        goal_params_json TEXT,
        research_json TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """
    )

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS task_modifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_uuid TEXT NOT NULL,
        user_id TEXT,
        run_id TEXT,
        channel_id TEXT,
        action TEXT NOT NULL,
        field_name TEXT NOT NULL,
        previous_value TEXT,
        new_value TEXT,
        context_json TEXT,
        modified_at TEXT
    )
    """
    )

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_live ON tasks(user_id, live, status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_channel_live ON tasks(user_id, channel_id, live)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_run_id ON tasks(run_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_updated_at ON tasks(updated_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_password_resets_user_id ON password_resets(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_research_snapshots_updated_at ON research_snapshots(updated_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_research_snapshots_channel_updated_at ON research_snapshots_channel(user_id, channel_id, updated_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_strategy_runs_user_channel_created ON strategy_runs(user_id, channel_id, created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_modifications_user_modified ON task_modifications(user_id, modified_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_modifications_user_channel_modified ON task_modifications(user_id, channel_id, modified_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_modifications_task_uuid_modified ON task_modifications(task_uuid, modified_at)")

    conn.commit()
    conn.close()


def insert_task(
    task,
    priority,
    day,
    parent_uuid=None,
    user_id=None,
    channel_id=None,
    run_id=None,
    goal_params=None,
    origin_run_id=None,
    origin_context=None,
):
    conn = get_connection()
    cursor = conn.cursor()

    task_id = str(uuid.uuid4())
    now = _utc_now_iso()

    cursor.execute(
        """
    INSERT INTO tasks (
        uuid,
        task,
        priority,
        day,
        status,
        live,
        created_at,
        updated_at,
        parent_uuid,
        user_id,
        channel_id,
        run_id,
        goal_params_json,
        origin_run_id,
        origin_context_json
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            channel_id,
            run_id,
            json.dumps(goal_params or {}),
            origin_run_id,
            json.dumps(origin_context or {}),
        ),
    )

    conn.commit()
    conn.close()

    return task_id


def get_active_tasks():
    return get_active_tasks_by_user(None)


def get_active_tasks_by_user(user_id, channel_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    if user_id:
        if channel_id:
            cursor.execute(
                """
            SELECT uuid, task, priority, day, status, live, created_at, updated_at, run_id, channel_id,
                   goal_params_json, origin_run_id, origin_context_json
            FROM tasks
            WHERE user_id = ? AND channel_id = ? AND live = 1 AND status != 'COMPLETED'
            ORDER BY day, created_at
            """,
                (user_id, channel_id),
            )
        else:
            cursor.execute(
                """
            SELECT uuid, task, priority, day, status, live, created_at, updated_at, run_id, channel_id,
                   goal_params_json, origin_run_id, origin_context_json
            FROM tasks
            WHERE user_id = ? AND live = 1 AND status != 'COMPLETED'
            ORDER BY day, created_at
            """,
                (user_id,),
            )
    else:
        cursor.execute(
            """
        SELECT uuid, task, priority, day, status, live, created_at, updated_at, run_id, channel_id,
               goal_params_json, origin_run_id, origin_context_json
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
                "created_at": row[6],
                "updated_at": row[7],
                "run_id": row[8],
                "channel_id": row[9],
                "goal_params": _safe_json_loads(row[10], default={}),
                "origin_run_id": row[11],
                "origin_context": _safe_json_loads(row[12], default={}),
            }
        )

    return tasks


def get_all_tasks():
    return get_all_tasks_by_user(None)


def get_all_tasks_by_user(user_id, channel_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    if user_id:
        if channel_id:
            cursor.execute(
                """
            SELECT uuid, task, priority, day, status, live, created_at, updated_at, parent_uuid, user_id,
                   run_id, channel_id, goal_params_json, origin_run_id, origin_context_json
            FROM tasks
            WHERE user_id = ? AND channel_id = ?
            ORDER BY updated_at DESC, created_at DESC
            """,
                (user_id, channel_id),
            )
        else:
            cursor.execute(
                """
            SELECT uuid, task, priority, day, status, live, created_at, updated_at, parent_uuid, user_id,
                   run_id, channel_id, goal_params_json, origin_run_id, origin_context_json
            FROM tasks
            WHERE user_id = ?
            ORDER BY updated_at DESC, created_at DESC
            """,
                (user_id,),
            )
    else:
        cursor.execute(
            """
        SELECT uuid, task, priority, day, status, live, created_at, updated_at, parent_uuid, user_id,
               run_id, channel_id, goal_params_json, origin_run_id, origin_context_json
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
                "run_id": row[10],
                "channel_id": row[11],
                "goal_params": _safe_json_loads(row[12], default={}),
                "origin_run_id": row[13],
                "origin_context": _safe_json_loads(row[14], default={}),
            }
        )

    return tasks


def get_task_by_uuid(task_uuid, user_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    if user_id:
        cursor.execute(
            """
        SELECT uuid, task, priority, day, status, live, created_at, updated_at, parent_uuid, user_id,
               run_id, channel_id, goal_params_json, origin_run_id, origin_context_json
        FROM tasks
        WHERE uuid = ? AND user_id = ?
        LIMIT 1
        """,
            (task_uuid, user_id),
        )
    else:
        cursor.execute(
            """
        SELECT uuid, task, priority, day, status, live, created_at, updated_at, parent_uuid, user_id,
               run_id, channel_id, goal_params_json, origin_run_id, origin_context_json
        FROM tasks
        WHERE uuid = ?
        LIMIT 1
        """,
            (task_uuid,),
        )

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "uuid": row[0],
        "task": row[1],
        "priority": row[2],
        "day": row[3],
        "status": row[4],
        "live": bool(row[5]),
        "created_at": row[6],
        "updated_at": row[7],
        "parent_uuid": row[8],
        "user_id": row[9],
        "run_id": row[10],
        "channel_id": row[11],
        "goal_params": _safe_json_loads(row[12], default={}),
        "origin_run_id": row[13],
        "origin_context": _safe_json_loads(row[14], default={}),
    }


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


def update_task_fields(task_uuid, user_id=None, priority=None, status=None, live=None, retries=3):
    if priority is None and status is None and live is None:
        return 0

    last_error = None

    for attempt in range(max(1, retries)):
        conn = None
        try:
            with _TASK_WRITE_LOCK:
                conn = get_connection()
                cursor = conn.cursor()

                now = _utc_now_iso()
                fields: list[str] = []
                params: list[object] = []

                if priority is not None:
                    fields.append("priority = ?")
                    params.append(priority)
                if status is not None:
                    fields.append("status = ?")
                    params.append(status)
                if live is not None:
                    fields.append("live = ?")
                    params.append(1 if bool(live) else 0)

                fields.append("updated_at = ?")
                params.append(now)

                if user_id:
                    cursor.execute(
                        f"UPDATE tasks SET {', '.join(fields)} WHERE uuid = ? AND user_id = ?",
                        (*params, task_uuid, user_id),
                    )
                else:
                    cursor.execute(
                        f"UPDATE tasks SET {', '.join(fields)} WHERE uuid = ?",
                        (*params, task_uuid),
                    )

                updated_rows = cursor.rowcount
                conn.commit()
                return updated_rows
        except sqlite3.OperationalError as exc:
            last_error = exc
            if "locked" in str(exc).lower() and attempt < max(1, retries) - 1:
                time.sleep(0.15 * (attempt + 1))
                continue
            raise
        finally:
            if conn is not None:
                conn.close()

    if last_error:
        raise last_error

    return 0


def update_task_status(task_uuid, status, user_id=None):
    return update_task_fields(task_uuid, user_id=user_id, status=status, retries=2)


def set_task_live(task_uuid, live, user_id=None, retries=3):
    return update_task_fields(task_uuid, user_id=user_id, live=bool(live), retries=retries)


def replace_tasks(
    new_tasks,
    user_id=None,
    channel_id=None,
    run_id=None,
    goal_params=None,
    origin_run_id=None,
):
    """Replace all active tasks with a new active set."""
    conn = get_connection()
    cursor = conn.cursor()

    now = _utc_now_iso()

    if user_id:
        if channel_id:
            cursor.execute(
                """
            UPDATE tasks
            SET live = 0, updated_at = ?
            WHERE live = 1 AND user_id = ? AND channel_id = ?
            """,
                (now, user_id, channel_id),
            )
        else:
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
        INSERT INTO tasks (
            uuid, task, priority, day, status, live, created_at, updated_at,
            parent_uuid, user_id, channel_id, run_id, goal_params_json, origin_run_id, origin_context_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                channel_id,
                run_id,
                json.dumps(goal_params or {}),
                origin_run_id,
                json.dumps({"replaced": True}),
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


def upsert_research_snapshot(user_id, goal, research, channel_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    now = _utc_now_iso()
    serialized = json.dumps(research or {})

    safe_channel_id = channel_id or "default"

    cursor.execute(
        """
    INSERT INTO research_snapshots_channel (user_id, channel_id, goal, research_json, updated_at)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(user_id, channel_id)
    DO UPDATE SET
      goal = excluded.goal,
      research_json = excluded.research_json,
      updated_at = excluded.updated_at
    """,
        (user_id, safe_channel_id, goal, serialized, now),
    )

    conn.commit()
    conn.close()


def get_research_snapshot(user_id, channel_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    if channel_id:
        cursor.execute(
            """
        SELECT goal, channel_id, research_json, updated_at
        FROM research_snapshots_channel
        WHERE user_id = ? AND channel_id = ?
        """,
            (user_id, channel_id),
        )
    else:
        cursor.execute(
            """
        SELECT goal, channel_id, research_json, updated_at
        FROM research_snapshots_channel
        WHERE user_id = ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
            (user_id,),
        )

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    payload = _safe_json_loads(row[2], default={})

    return {
        "goal": row[0],
        "channel_id": row[1],
        "research": payload,
        "updated_at": row[3],
    }


def upsert_strategy_run(run_id, user_id, channel_id, goal_text, goal_params, research=None):
    conn = get_connection()
    cursor = conn.cursor()
    now = _utc_now_iso()

    cursor.execute(
        """
    INSERT INTO strategy_runs (
        run_id, user_id, channel_id, goal_text, goal_params_json, research_json, created_at, updated_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(run_id)
    DO UPDATE SET
      channel_id = excluded.channel_id,
      goal_text = excluded.goal_text,
      goal_params_json = excluded.goal_params_json,
      research_json = excluded.research_json,
      updated_at = excluded.updated_at
    """,
        (
            run_id,
            user_id,
            channel_id,
            goal_text,
            json.dumps(goal_params or {}),
            json.dumps(research or {}),
            now,
            now,
        ),
    )

    conn.commit()
    conn.close()


def get_strategy_runs_by_user(user_id, channel_id=None, limit=60):
    conn = get_connection()
    cursor = conn.cursor()

    if channel_id:
        cursor.execute(
            """
        SELECT run_id, channel_id, goal_text, goal_params_json, research_json, created_at, updated_at
        FROM strategy_runs
        WHERE user_id = ? AND channel_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
            (user_id, channel_id, limit),
        )
    else:
        cursor.execute(
            """
        SELECT run_id, channel_id, goal_text, goal_params_json, research_json, created_at, updated_at
        FROM strategy_runs
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
            (user_id, limit),
        )

    rows = cursor.fetchall()
    conn.close()

    runs = []
    for row in rows:
        runs.append(
            {
                "run_id": row[0],
                "channel_id": row[1],
                "goal": row[2],
                "goal_params": _safe_json_loads(row[3], default={}),
                "research": _safe_json_loads(row[4], default={}),
                "created_at": row[5],
                "updated_at": row[6],
            }
        )

    return runs


def get_tasks_by_run(user_id, run_id, channel_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    if channel_id:
        cursor.execute(
            """
        SELECT uuid, task, priority, day, status, live, created_at, updated_at, parent_uuid, user_id,
               run_id, channel_id, goal_params_json, origin_run_id, origin_context_json
        FROM tasks
        WHERE user_id = ? AND run_id = ? AND channel_id = ?
        ORDER BY created_at ASC
        """,
            (user_id, run_id, channel_id),
        )
    else:
        cursor.execute(
            """
        SELECT uuid, task, priority, day, status, live, created_at, updated_at, parent_uuid, user_id,
               run_id, channel_id, goal_params_json, origin_run_id, origin_context_json
        FROM tasks
        WHERE user_id = ? AND run_id = ?
        ORDER BY created_at ASC
        """,
            (user_id, run_id),
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
                "run_id": row[10],
                "channel_id": row[11],
                "goal_params": _safe_json_loads(row[12], default={}),
                "origin_run_id": row[13],
                "origin_context": _safe_json_loads(row[14], default={}),
            }
        )

    return tasks


def get_channel_ids_by_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    values = set()

    cursor.execute("SELECT DISTINCT channel_id FROM tasks WHERE user_id = ? AND channel_id IS NOT NULL AND channel_id != ''", (user_id,))
    for row in cursor.fetchall():
        values.add(row[0])

    cursor.execute("SELECT DISTINCT channel_id FROM strategy_runs WHERE user_id = ? AND channel_id IS NOT NULL AND channel_id != ''", (user_id,))
    for row in cursor.fetchall():
        values.add(row[0])

    cursor.execute("SELECT DISTINCT channel_id FROM research_snapshots_channel WHERE user_id = ? AND channel_id IS NOT NULL AND channel_id != ''", (user_id,))
    for row in cursor.fetchall():
        values.add(row[0])

    conn.close()
    return sorted(values)


def log_task_modification(
    task_uuid,
    *,
    user_id,
    action,
    field_name,
    previous_value=None,
    new_value=None,
    run_id=None,
    channel_id=None,
    context=None,
):
    conn = get_connection()
    cursor = conn.cursor()
    now = _utc_now_iso()

    cursor.execute(
        """
    INSERT INTO task_modifications (
        task_uuid, user_id, run_id, channel_id, action, field_name,
        previous_value, new_value, context_json, modified_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            task_uuid,
            user_id,
            run_id,
            channel_id,
            action,
            field_name,
            _normalize_trace_value(previous_value),
            _normalize_trace_value(new_value),
            json.dumps(context or {}),
            now,
        ),
    )

    conn.commit()
    conn.close()


def get_task_modifications_by_user(user_id, channel_id=None, limit=100, task_uuid=None):
    conn = get_connection()
    cursor = conn.cursor()

    query = (
        """
        SELECT id, task_uuid, user_id, run_id, channel_id, action, field_name,
               previous_value, new_value, context_json, modified_at
        FROM task_modifications
        WHERE user_id = ?
        """
    )
    params: list[object] = [user_id]

    if channel_id:
        query += " AND channel_id = ?"
        params.append(channel_id)
    if task_uuid:
        query += " AND task_uuid = ?"
        params.append(task_uuid)

    query += " ORDER BY modified_at DESC, id DESC LIMIT ?"
    params.append(max(1, int(limit)))

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()

    modifications = []
    for row in rows:
        modifications.append(
            {
                "id": row[0],
                "task_uuid": row[1],
                "user_id": row[2],
                "run_id": row[3],
                "channel_id": row[4],
                "action": row[5],
                "field_name": row[6],
                "previous_value": row[7],
                "new_value": row[8],
                "context": _safe_json_loads(row[9], default={}),
                "modified_at": row[10],
            }
        )

    return modifications
