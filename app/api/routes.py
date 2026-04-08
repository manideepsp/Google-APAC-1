from datetime import datetime, timedelta, timezone
import json
import logging
import re
import threading
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.agents.reflection_agent import reflection_agent
from app.core.security import (
    generate_token,
    hash_password,
    hash_token,
    normalize_email,
    verify_password,
)
from app.db.sqlite import (
    create_password_reset,
    create_session,
    create_user,
    delete_session,
    get_channel_ids_by_user,
    get_active_tasks_by_user,
    get_all_tasks_by_user,
    get_password_reset,
    get_research_snapshot,
    get_strategy_runs_by_user,
    get_task_by_uuid,
    get_task_modifications_by_user,
    get_tasks_by_run,
    get_user_by_email,
    get_user_by_session,
    log_task_modification,
    mark_password_reset_used,
    upsert_strategy_run,
    upsert_research_snapshot,
    update_task_fields,
    update_user_password_hash,
)
from app.core.llm import get_llm
from app.core.utils.json_parser import extract_json
from app.adk.ops_agent import build_ops_agent
from app.adk.workflow_runner import run_goal_workflow_adk
from app.services.sheets_sync import sync_tasks_to_sheets

router = APIRouter()
SESSION_TTL_DAYS = 7
RESET_TTL_MINUTES = 30
LOGGER = logging.getLogger(__name__)
_SYNC_STATE_LOCK = threading.Lock()
_SYNC_RUNNING_USERS: set[str] = set()
_SYNC_PENDING_USERS: set[str] = set()


def _expiry_iso(*, days=0, minutes=0):
    return (datetime.now(timezone.utc) + timedelta(days=days, minutes=minutes)).isoformat()


def _extract_retry_after_seconds(message: str) -> int | None:
    if not message:
        return None

    # Handles formats like "Please retry in 6.8s" and "retryDelay': '31s'".
    patterns = (
        r"retry(?:\s+in)?\s*([0-9]+(?:\.[0-9]+)?)s",
        r"retrydelay[^0-9]*([0-9]+(?:\.[0-9]+)?)s",
    )

    match = None
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            break

    if not match:
        return None

    try:
        return max(1, int(float(match.group(1))))
    except Exception:
        return None


def _raise_adk_http_error(stage: str, exc: Exception):
    message = str(exc)
    upper = message.upper()

    if "RESOURCE_EXHAUSTED" in upper or "QUOTA EXCEEDED" in upper:
        retry_after = _extract_retry_after_seconds(message)
        headers = {"X-Error-Code": "GEMINI_QUOTA_EXHAUSTED"}
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)

        raise HTTPException(
            status_code=429,
            detail=(
                "GEMINI_QUOTA_EXHAUSTED: Gemini quota is exhausted for the current model. "
                "Please retry after the cooldown period."
            ),
            headers=headers,
        )

    raise HTTPException(status_code=503, detail=f"ADK {stage} failed: {message}")


def _run_sync_worker(user_id: str):
    while True:
        try:
            sync_tasks_to_sheets(user_id=user_id)
        except Exception as exc:
            LOGGER.warning("Background task sync failed for user %s: %s", user_id, exc)

        with _SYNC_STATE_LOCK:
            if user_id in _SYNC_PENDING_USERS:
                _SYNC_PENDING_USERS.discard(user_id)
                continue

            _SYNC_RUNNING_USERS.discard(user_id)
            return


def _sync_tasks_best_effort(user_id: str):
    if not user_id:
        return

    with _SYNC_STATE_LOCK:
        if user_id in _SYNC_RUNNING_USERS:
            _SYNC_PENDING_USERS.add(user_id)
            return

        _SYNC_RUNNING_USERS.add(user_id)

    thread_name = f"sync-{user_id[:8]}"
    worker = threading.Thread(target=_run_sync_worker, args=(user_id,), daemon=True, name=thread_name)
    worker.start()


def _extract_channel_id(value: str | None) -> str | None:
    if not value:
        return None

    text = str(value).strip()
    if not text:
        return None

    direct = re.fullmatch(r"UC[a-zA-Z0-9_-]{22}", text)
    if direct:
        return direct.group(0)

    match = re.search(r"(UC[a-zA-Z0-9_-]{22})", text)
    if match:
        return match.group(1)

    return None


def _normalize_goal_params(payload: dict) -> dict:
    params = payload.get("goal_params")
    if isinstance(params, str):
        try:
            parsed = json.loads(params)
            params = parsed if isinstance(parsed, dict) else {}
        except Exception:
            params = {}
    elif not isinstance(params, dict):
        params = {}

    normalized = {
        str(k).strip(): str(v).strip()
        for k, v in params.items()
        if str(k).strip() and v is not None and str(v).strip()
    }

    goal = str(payload.get("goal", "")).strip()
    if goal and not normalized.get("Goal"):
        normalized["Goal"] = goal

    for key in ("Audience", "Budget", "Timeline", "Content Type"):
        value = str(payload.get(key.lower().replace(" ", "_"), "")).strip()
        if value and not normalized.get(key):
            normalized[key] = value

    channel_from_params = normalized.get("Channel ID")
    channel_from_payload = _extract_channel_id(payload.get("channel_id"))
    channel_id = _extract_channel_id(channel_from_params) or channel_from_payload
    if channel_id:
        normalized["Channel ID"] = channel_id

    return normalized


def _goal_text_from_params(goal_params: dict) -> str:
    if not goal_params:
        return ""

    direct = str(goal_params.get("Goal", "")).strip()
    if direct:
        return direct

    parts = [f"{k}: {v}" for k, v in goal_params.items() if str(k).strip() and str(v).strip()]
    return "; ".join(parts)


def _build_run_payload(payload: dict) -> tuple[str, str | None, dict, str]:
    goal_params = _normalize_goal_params(payload)
    run_id = str(payload.get("run_id") or uuid.uuid4())
    channel_id = _extract_channel_id(payload.get("channel_id")) or _extract_channel_id(goal_params.get("Channel ID"))
    goal_text = str(payload.get("goal", "")).strip() or _goal_text_from_params(goal_params)

    if goal_text and not goal_params.get("Goal"):
        goal_params["Goal"] = goal_text
    if channel_id:
        goal_params["Channel ID"] = channel_id

    return run_id, channel_id, goal_params, goal_text


def _coerce_live_value(value):
    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "on"}:
        return True
    if text in {"false", "0", "no", "n", "off"}:
        return False

    raise HTTPException(status_code=400, detail="live must be a boolean value")


def _trace_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def require_user(x_session_token: str | None = Header(default=None, alias="X-Session-Token")):
    if not x_session_token:
        raise HTTPException(status_code=401, detail="Authentication required")

    token_hash = hash_token(x_session_token)
    user = get_user_by_session(token_hash)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    user["token_hash"] = token_hash
    return user


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/auth/register")
def register(payload: dict):
    email = normalize_email(payload.get("email", ""))
    password = payload.get("password", "")

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email is required")

    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    if get_user_by_email(email):
        raise HTTPException(status_code=409, detail="Email already registered")

    user = create_user(email, hash_password(password))
    if not user:
        raise HTTPException(status_code=500, detail="Unable to create user")

    session_token = generate_token()
    create_session(user["id"], hash_token(session_token), _expiry_iso(days=SESSION_TTL_DAYS))

    return {
        "message": "Registered",
        "session_token": session_token,
        "user": {
            "id": user["id"],
            "email": user["email"],
        },
    }


@router.post("/auth/login")
def login(payload: dict):
    email = normalize_email(payload.get("email", ""))
    password = payload.get("password", "")

    user = get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    session_token = generate_token()
    create_session(user["id"], hash_token(session_token), _expiry_iso(days=SESSION_TTL_DAYS))

    return {
        "message": "Logged in",
        "session_token": session_token,
        "user": {
            "id": user["id"],
            "email": user["email"],
        },
    }


@router.post("/auth/logout")
def logout(user=Depends(require_user)):
    delete_session(user["token_hash"])
    return {"message": "Logged out"}


@router.get("/auth/me")
def me(user=Depends(require_user)):
    return {
        "user": {
            "id": user["id"],
            "email": user["email"],
        }
    }


@router.post("/auth/forgot-password")
def forgot_password(payload: dict):
    email = normalize_email(payload.get("email", ""))
    user = get_user_by_email(email)

    reset_token = None
    if user:
        reset_token = generate_token()
        create_password_reset(
            user["id"],
            hash_token(reset_token),
            _expiry_iso(minutes=RESET_TTL_MINUTES),
        )

    # MVP: return token directly because no email provider is wired yet.
    return {
        "message": "If the account exists, a reset token has been generated",
        "reset_token": reset_token,
    }


@router.post("/auth/reset-password")
def reset_password(payload: dict):
    reset_token = payload.get("reset_token", "")
    new_password = payload.get("new_password", "")

    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    record = get_password_reset(hash_token(reset_token))
    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    update_user_password_hash(record["user_id"], hash_password(new_password))
    mark_password_reset_used(record["token_hash"])
    return {"message": "Password reset successful"}


@router.post("/channel/parse")
def parse_channel(payload: dict, user=Depends(require_user)):
    candidate = payload.get("value") or payload.get("channel") or payload.get("channel_id")
    channel_id = _extract_channel_id(candidate)
    return {
        "channel_id": channel_id,
        "valid": bool(channel_id),
    }


@router.get("/channels")
def get_channels(user=Depends(require_user)):
    channels = get_channel_ids_by_user(user["id"])
    return {"channels": channels}


@router.post("/goal/assistant")
def goal_assistant(payload: dict, user=Depends(require_user)):
    message = str(payload.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    goal_params = _normalize_goal_params(payload)
    history = payload.get("history") or []
    if not isinstance(history, list):
        history = []

    compact_history: list[str] = []
    for item in history[-6:]:
        if isinstance(item, dict):
            role = str(item.get("role", "user")).strip()[:12]
            text = str(item.get("text", "")).strip()[:500]
            if text:
                compact_history.append(f"{role}: {text}")

    prompt = f"""
You are an intelligent goal-building assistant for YouTube strategy planning.
The user is iteratively defining strategy parameters.

Current goal parameters:
{json.dumps(goal_params, ensure_ascii=False)}

Recent conversation:
{json.dumps(compact_history, ensure_ascii=False)}

Latest user message:
{message}

Return ONLY JSON with this schema:
{{
  "assistant_message": "short helpful response",
  "goal_params": {{"Goal": "...", "Audience": "...", "Budget": "...", "Timeline": "...", "Content Type": "...", "Channel ID": "UC..."}},
  "next_question": "single follow-up question",
  "ready": true_or_false
}}

Rules:
- Keep existing parameters unless user clearly changes them.
- Prefer concise values in goal_params.
- If user provides a channel link or ID, normalize to a UC... channel ID when possible.
- ready=true only when Goal and at least one of Audience/Content Type is present.
"""

    try:
        llm = get_llm()
        response = llm.invoke(prompt)
        parsed = extract_json(response.text)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Goal assistant failed: {exc}")

    if not isinstance(parsed, dict):
        parsed = {
            "assistant_message": "I updated your draft goal. Share more details for audience, budget, timeline, or content type.",
            "goal_params": goal_params,
            "next_question": "Who is your target audience?",
            "ready": bool(goal_params.get("Goal")),
        }

    merged_params = dict(goal_params)
    candidate_params = parsed.get("goal_params")
    if isinstance(candidate_params, dict):
        for key, value in candidate_params.items():
            k = str(key).strip()
            v = str(value).strip()
            if k and v:
                merged_params[k] = v

    detected_channel = _extract_channel_id(merged_params.get("Channel ID")) or _extract_channel_id(message)
    if detected_channel:
        merged_params["Channel ID"] = detected_channel

    ready = bool(merged_params.get("Goal") and (merged_params.get("Audience") or merged_params.get("Content Type")))
    if isinstance(parsed.get("ready"), bool):
        ready = parsed.get("ready") and ready

    assistant_message = str(parsed.get("assistant_message", "")).strip() or "I updated your goal parameters."
    next_question = str(parsed.get("next_question", "")).strip()
    if not next_question and not ready:
        next_question = "What audience are you targeting first?"

    return {
        "assistant_message": assistant_message,
        "next_question": next_question,
        "goal_params": merged_params,
        "ready": ready,
    }


@router.post("/goal")
def create_goal(payload: dict, user=Depends(require_user)):
    run_id, channel_id, goal_params, goal = _build_run_payload(payload)

    if not goal:
        raise HTTPException(status_code=400, detail="Goal is required")

    state = {
        "goal": goal,
        "channel_id": channel_id,
        "user_id": user["id"],
        "run_id": run_id,
        "goal_params": goal_params,
    }

    result = None
    try:
        result = run_goal_workflow_adk(state)
    except Exception as exc:
        _raise_adk_http_error("workflow", exc)

    if result is None:
        raise HTTPException(status_code=503, detail="ADK workflow failed")

    research = result.get("research", {})
    try:
        upsert_research_snapshot(
            user_id=user["id"],
            goal=goal,
            channel_id=channel_id,
            research=research,
        )
        upsert_strategy_run(
            run_id=run_id,
            user_id=user["id"],
            channel_id=channel_id,
            goal_text=goal,
            goal_params=goal_params,
            research=research,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to persist research snapshot: {exc}")

    return {
        "message": "Workflow executed",
        "run_id": run_id,
        "goal_params": goal_params,
        "channel_id": channel_id,
        "tasks": result.get("tasks", []),
        "research": research,
    }


@router.post("/analyze")
def analyze(payload: dict, user=Depends(require_user)):
    run_id, channel_id, goal_params, _ = _build_run_payload(payload)

    state = {
        "tasks": [],
        "channel_id": channel_id,
        "user_id": user["id"],
        "run_id": run_id,
        "goal_params": goal_params,
    }

    try:
        state = reflection_agent(state)
    except Exception as exc:
        _raise_adk_http_error("reflection", exc)

    return {
        "message": "Re-analysis complete",
        "run_id": run_id,
        "goal_params": goal_params,
        "new_tasks": state.get("tasks", []),
    }


@router.post("/task/update")
def update_task(payload: dict, user=Depends(require_user)):
    task_uuid = payload.get("uuid", "")
    priority = payload.get("priority")
    status = payload.get("status")
    live_raw = payload.get("live") if "live" in payload else None
    allowed_status = {"TODO", "IN_PROGRESS", "COMPLETED", "OUT_OF_SCOPE"}
    allowed_priority = {"High", "Medium", "Low"}

    if not task_uuid:
        raise HTTPException(status_code=400, detail="Task uuid is required")

    if priority is not None:
        priority = str(priority).strip()
        if priority not in allowed_priority:
            raise HTTPException(status_code=400, detail=f"Invalid priority. Allowed: {sorted(allowed_priority)}")

    if status is not None and status not in allowed_status:
        raise HTTPException(status_code=400, detail=f"Invalid status. Allowed: {sorted(allowed_status)}")

    live = None
    if live_raw is not None:
        live = _coerce_live_value(live_raw)

    if priority is None and status is None and live is None:
        raise HTTPException(status_code=400, detail="At least one of priority, status, or live is required")

    before = get_task_by_uuid(task_uuid, user_id=user["id"])
    if not before:
        raise HTTPException(status_code=404, detail="Task not found")

    target_priority = priority if priority is not None else before["priority"]
    target_status = status if status is not None else before["status"]
    target_live = live if live is not None else bool(before["live"])

    updated_rows = update_task_fields(
        task_uuid,
        user_id=user["id"],
        priority=target_priority,
        status=target_status,
        live=target_live,
    )
    if updated_rows == 0:
        raise HTTPException(status_code=404, detail="Task not found")

    after = get_task_by_uuid(task_uuid, user_id=user["id"])
    if not after:
        raise HTTPException(status_code=404, detail="Task not found after update")

    changed_fields: list[dict[str, str]] = []
    for field_name, previous_value, new_value in (
        ("priority", before.get("priority"), after.get("priority")),
        ("status", before.get("status"), after.get("status")),
        ("live", bool(before.get("live")), bool(after.get("live"))),
    ):
        if _trace_value(previous_value) == _trace_value(new_value):
            continue

        changed_fields.append(
            {
                "field": field_name,
                "previous": _trace_value(previous_value),
                "current": _trace_value(new_value),
            }
        )
        log_task_modification(
            task_uuid,
            user_id=user["id"],
            run_id=after.get("run_id"),
            channel_id=after.get("channel_id"),
            action="update",
            field_name=field_name,
            previous_value=previous_value,
            new_value=new_value,
            context={
                "source": "task_update_api",
                "task": after.get("task", ""),
            },
        )

    _sync_tasks_best_effort(user["id"])

    return {
        "message": "Task updated",
        "uuid": task_uuid,
        "changes": changed_fields,
        "task": {
            "priority": after.get("priority"),
            "status": after.get("status"),
            "live": bool(after.get("live")),
            "updated_at": after.get("updated_at"),
        },
    }


@router.post("/task/move")
def move_task(payload: dict, user=Depends(require_user)):
    task_uuid = payload.get("uuid", "")
    target = str(payload.get("target", "")).strip().lower()

    if not task_uuid:
        raise HTTPException(status_code=400, detail="Task uuid is required")

    if target not in {"tasks", "archive"}:
        raise HTTPException(status_code=400, detail="target must be either 'tasks' or 'archive'")

    before = get_task_by_uuid(task_uuid, user_id=user["id"])
    if not before:
        raise HTTPException(status_code=404, detail="Task not found")

    to_live = target == "tasks"
    updated_rows = update_task_fields(task_uuid, user_id=user["id"], live=to_live)
    if updated_rows == 0:
        raise HTTPException(status_code=404, detail="Task not found")

    after = get_task_by_uuid(task_uuid, user_id=user["id"])
    if not after:
        raise HTTPException(status_code=404, detail="Task not found after move")

    changes = []
    if bool(before.get("live")) != bool(after.get("live")):
        changes.append(
            {
                "field": "live",
                "previous": _trace_value(bool(before.get("live"))),
                "current": _trace_value(bool(after.get("live"))),
            }
        )
        log_task_modification(
            task_uuid,
            user_id=user["id"],
            run_id=after.get("run_id"),
            channel_id=after.get("channel_id"),
            action="move",
            field_name="live",
            previous_value=bool(before.get("live")),
            new_value=bool(after.get("live")),
            context={
                "source": "task_move_api",
                "target": target,
                "task": after.get("task", ""),
            },
        )

    _sync_tasks_best_effort(user["id"])

    return {
        "message": "Task moved",
        "uuid": task_uuid,
        "target": target,
        "live": bool(after.get("live")),
        "changes": changes,
    }


@router.get("/tasks")
def get_tasks(channel_id: str | None = Query(default=None), user=Depends(require_user)):
    normalized_channel_id = _extract_channel_id(channel_id)
    return {
        "tasks": get_active_tasks_by_user(user["id"], channel_id=normalized_channel_id)
    }


@router.get("/tasks/history")
def get_tasks_history(channel_id: str | None = Query(default=None), user=Depends(require_user)):
    normalized_channel_id = _extract_channel_id(channel_id)
    return {
        "tasks": get_all_tasks_by_user(user["id"], channel_id=normalized_channel_id)
    }


@router.get("/tasks/modifications")
def get_task_modifications(
    channel_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    user=Depends(require_user),
):
    normalized_channel_id = _extract_channel_id(channel_id)
    return {
        "modifications": get_task_modifications_by_user(
            user["id"],
            channel_id=normalized_channel_id,
            limit=limit,
        )
    }


@router.get("/runs")
def get_runs(channel_id: str | None = Query(default=None), user=Depends(require_user)):
    normalized_channel_id = _extract_channel_id(channel_id)
    runs = get_strategy_runs_by_user(user["id"], channel_id=normalized_channel_id)

    hydrated = []
    for run in runs:
        tasks = get_tasks_by_run(user["id"], run["run_id"], channel_id=normalized_channel_id)
        hydrated.append(
            {
                **run,
                "tasks": tasks,
            }
        )

    return {
        "runs": hydrated,
    }


@router.get("/archive")
def get_archive(channel_id: str | None = Query(default=None), user=Depends(require_user)):
    return get_runs(channel_id=channel_id, user=user)


@router.get("/research/latest")
def get_latest_research(channel_id: str | None = Query(default=None), user=Depends(require_user)):
    normalized_channel_id = _extract_channel_id(channel_id)
    snapshot = get_research_snapshot(user["id"], channel_id=normalized_channel_id)
    if not snapshot:
        return {
            "goal": None,
            "channel_id": None,
            "research": None,
            "updated_at": None,
        }

    return snapshot


@router.get("/ops/adk/agent")
def get_adk_agent_info(user=Depends(require_user)):
    agent = build_ops_agent()
    return {
        "name": agent.name,
        "model": agent.model,
        "tool_count": len(agent.tools),
    }