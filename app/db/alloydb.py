import logging
import os
import uuid
from typing import Any

from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

load_dotenv(override=False)

LOGGER = logging.getLogger(__name__)

_SCHEMA_READY = False
_DEFAULT_RELATED_LIMIT = 12
_DEFAULT_LOOKBACK_DAYS = 180


def _alloydb_dsn() -> str:
    for key in ("ALLOYDB_DSN", "ALLOYDB_URI", "DATABASE_URL"):
        value = str(os.getenv(key, "")).strip()
        if value.startswith("postgresql://") or value.startswith("postgres://"):
            return value
    return ""


def is_alloydb_configured() -> bool:
    return bool(_alloydb_dsn())


def _ensure_schema(conn) -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return

    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS generation_task_memory (
                id BIGSERIAL PRIMARY KEY,
                memory_uuid TEXT NOT NULL UNIQUE,
                user_id TEXT NOT NULL,
                channel_id TEXT,
                run_id TEXT,
                generation_number INTEGER NOT NULL,
                goal_text TEXT NOT NULL,
                goal_params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                task_text TEXT NOT NULL,
                priority TEXT,
                day TEXT,
                status TEXT,
                live BOOLEAN,
                task_payload_json JSONB NOT NULL,
                metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                search_text TEXT NOT NULL,
                search_vector TSVECTOR,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_generation_task_memory_user_channel_generation
            ON generation_task_memory(user_id, channel_id, generation_number DESC, created_at DESC)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_generation_task_memory_search_vector
            ON generation_task_memory USING GIN(search_vector)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_generation_task_memory_metadata
            ON generation_task_memory USING GIN(metadata_json)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_generation_task_memory_search_text_trgm
            ON generation_task_memory USING GIN(search_text gin_trgm_ops)
            """
        )

    conn.commit()
    _SCHEMA_READY = True


def init_alloydb() -> bool:
    dsn = _alloydb_dsn()
    if not dsn:
        return False

    try:
        with psycopg.connect(dsn) as conn:
            _ensure_schema(conn)
        return True
    except Exception as exc:
        LOGGER.warning("AlloyDB initialization skipped: %s", exc)
        return False


def _normalize_goal_params(goal_params: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(goal_params, dict):
        return {}

    normalized: dict[str, str] = {}
    for key, value in goal_params.items():
        k = str(key).strip()
        v = str(value).strip()
        if k and v:
            normalized[k] = v
    return normalized


def _search_text(
    *,
    goal_text: str,
    goal_params: dict[str, str],
    task: dict[str, Any],
    metadata: dict[str, Any],
) -> str:
    chunks: list[str] = [goal_text]
    chunks.extend(f"{k} {v}" for k, v in goal_params.items())

    task_text = str(task.get("task", "")).strip()
    if task_text:
        chunks.append(task_text)

    for key in ("priority", "day", "status"):
        value = str(task.get(key, "")).strip()
        if value:
            chunks.append(value)

    for key in ("source", "channel_id", "insights_excerpt"):
        value = str(metadata.get(key, "")).strip()
        if value:
            chunks.append(value)

    return " ".join(part for part in chunks if part)


def _query_text(goal_text: str, goal_params: dict[str, str], research: dict[str, Any] | None) -> str:
    chunks: list[str] = [goal_text]
    chunks.extend(f"{k} {v}" for k, v in goal_params.items())

    if isinstance(research, dict):
        for title in (research.get("titles") or [])[:10]:
            value = str(title).strip()
            if value:
                chunks.append(value)

        insights = str(research.get("insights", "")).strip()
        if insights:
            chunks.append(insights[:700])

    return " ".join(part for part in chunks if part).strip()


def _next_generation_number(conn, user_id: str, channel_id: str | None) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT COALESCE(MAX(generation_number), 0) AS latest_generation
            FROM generation_task_memory
            WHERE user_id = %s
              AND (%s IS NULL OR channel_id = %s)
            """,
            (user_id, channel_id, channel_id),
        )
        row = cur.fetchone() or {}
    latest = int(row.get("latest_generation") or 0)
    return latest + 1


def fetch_related_generation_tasks(
    *,
    user_id: str | None,
    channel_id: str | None,
    goal_text: str,
    goal_params: dict[str, Any] | None,
    research: dict[str, Any] | None = None,
    limit: int = _DEFAULT_RELATED_LIMIT,
    lookback_days: int = _DEFAULT_LOOKBACK_DAYS,
) -> list[dict[str, Any]]:
    if not user_id:
        return []

    dsn = _alloydb_dsn()
    if not dsn:
        return []

    query_goal_params = _normalize_goal_params(goal_params)
    query_text = _query_text(goal_text, query_goal_params, research)
    safe_limit = max(1, min(100, int(limit)))
    safe_lookback = max(7, min(3650, int(lookback_days)))

    try:
        with psycopg.connect(dsn) as conn:
            _ensure_schema(conn)

            with conn.cursor(row_factory=dict_row) as cur:
                if query_text:
                    cur.execute(
                        """
                        WITH ranked AS (
                            SELECT
                                task_text,
                                priority,
                                day,
                                status,
                                live,
                                run_id,
                                generation_number,
                                goal_text,
                                goal_params_json,
                                metadata_json,
                                created_at,
                                ts_rank_cd(search_vector, plainto_tsquery('english', %s)) AS fts_score,
                                similarity(search_text, %s) AS trigram_score,
                                (1.0 / (1.0 + EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400.0)) AS recency_score
                            FROM generation_task_memory
                            WHERE user_id = %s
                              AND (%s IS NULL OR channel_id = %s)
                              AND created_at >= NOW() - (%s * INTERVAL '1 day')
                        )
                        SELECT
                            task_text,
                            priority,
                            day,
                            status,
                            live,
                            run_id,
                            generation_number,
                            goal_text,
                            goal_params_json,
                            metadata_json,
                            created_at,
                            (0.55 * fts_score + 0.35 * trigram_score + 0.10 * recency_score) AS relevance
                        FROM ranked
                        WHERE fts_score > 0 OR trigram_score > 0.08
                        ORDER BY relevance DESC, created_at DESC
                        LIMIT %s
                        """,
                        (
                            query_text,
                            query_text,
                            user_id,
                            channel_id,
                            channel_id,
                            safe_lookback,
                            safe_limit,
                        ),
                    )
                    rows = cur.fetchall()
                else:
                    rows = []

                if not rows:
                    cur.execute(
                        """
                        SELECT
                            task_text,
                            priority,
                            day,
                            status,
                            live,
                            run_id,
                            generation_number,
                            goal_text,
                            goal_params_json,
                            metadata_json,
                            created_at,
                            NULL::DOUBLE PRECISION AS relevance
                        FROM generation_task_memory
                        WHERE user_id = %s
                          AND (%s IS NULL OR channel_id = %s)
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (user_id, channel_id, channel_id, safe_limit),
                    )
                    rows = cur.fetchall()

        related: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            task_text = str(row.get("task_text", "")).strip()
            if not task_text:
                continue

            dedupe_key = task_text.lower()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            related.append(
                {
                    "task": task_text,
                    "priority": row.get("priority"),
                    "day": row.get("day"),
                    "status": row.get("status"),
                    "live": row.get("live"),
                    "run_id": row.get("run_id"),
                    "generation_number": row.get("generation_number"),
                    "goal": row.get("goal_text"),
                    "goal_params": row.get("goal_params_json") or {},
                    "metadata": row.get("metadata_json") or {},
                    "created_at": row.get("created_at"),
                    "relevance": row.get("relevance"),
                }
            )

        return related
    except Exception as exc:
        LOGGER.warning("AlloyDB relevance fetch skipped: %s", exc)
        return []


def record_generation_tasks(
    *,
    user_id: str | None,
    run_id: str | None,
    channel_id: str | None,
    goal_text: str,
    goal_params: dict[str, Any] | None,
    tasks: list[dict[str, Any]],
    research: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    generation_number: int | None = None,
) -> dict[str, Any]:
    if not user_id:
        return {"enabled": False, "stored": 0, "reason": "missing_user_id"}

    if not tasks:
        return {"enabled": bool(_alloydb_dsn()), "stored": 0, "reason": "no_tasks"}

    dsn = _alloydb_dsn()
    if not dsn:
        return {"enabled": False, "stored": 0, "reason": "missing_dsn"}

    normalized_goal_params = _normalize_goal_params(goal_params)
    metadata_base = dict(metadata or {})

    if isinstance(research, dict):
        titles = [str(title).strip() for title in (research.get("titles") or [])[:8] if str(title).strip()]
        if titles:
            metadata_base.setdefault("titles", titles)

        insights = str(research.get("insights", "")).strip()
        if insights:
            metadata_base.setdefault("insights_excerpt", insights[:700])

    try:
        with psycopg.connect(dsn) as conn:
            _ensure_schema(conn)

            generation = generation_number or _next_generation_number(conn, user_id, channel_id)
            stored = 0

            with conn.cursor() as cur:
                for index, task in enumerate(tasks, start=1):
                    task_text = str(task.get("task", "")).strip()
                    if not task_text:
                        continue

                    task_metadata = dict(metadata_base)
                    task_metadata["task_index"] = index

                    search_text = _search_text(
                        goal_text=goal_text,
                        goal_params=normalized_goal_params,
                        task=task,
                        metadata=task_metadata,
                    )

                    cur.execute(
                        """
                        INSERT INTO generation_task_memory (
                            memory_uuid,
                            user_id,
                            channel_id,
                            run_id,
                            generation_number,
                            goal_text,
                            goal_params_json,
                            task_text,
                            priority,
                            day,
                            status,
                            live,
                            task_payload_json,
                            metadata_json,
                            search_text,
                            search_vector
                        )
                        VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            to_tsvector('english', %s)
                        )
                        """,
                        (
                            str(uuid.uuid4()),
                            user_id,
                            channel_id,
                            run_id,
                            generation,
                            goal_text,
                            Jsonb(normalized_goal_params),
                            task_text,
                            str(task.get("priority", "")).strip() or None,
                            str(task.get("day", "")).strip() or None,
                            str(task.get("status", "")).strip() or None,
                            bool(task.get("live")) if task.get("live") is not None else None,
                            Jsonb(task),
                            Jsonb(task_metadata),
                            search_text,
                            search_text,
                        ),
                    )
                    stored += 1

            conn.commit()

        return {
            "enabled": True,
            "stored": stored,
            "generation_number": generation,
        }
    except Exception as exc:
        LOGGER.warning("AlloyDB generation memory write skipped: %s", exc)
        return {
            "enabled": True,
            "stored": 0,
            "error": str(exc),
        }