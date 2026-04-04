from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException

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
    get_active_tasks_by_user,
    get_all_tasks_by_user,
    get_password_reset,
    get_user_by_email,
    get_user_by_session,
    mark_password_reset_used,
    set_task_live,
    update_task_status,
    update_user_password_hash,
)
from app.adk.ops_agent import build_ops_agent
from app.adk.workflow_runner import run_goal_workflow_adk
from app.services.sheets_sync import sync_tasks_to_sheets

router = APIRouter()
SESSION_TTL_DAYS = 7
RESET_TTL_MINUTES = 30


def _expiry_iso(*, days=0, minutes=0):
    return (datetime.now(timezone.utc) + timedelta(days=days, minutes=minutes)).isoformat()


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


@router.post("/goal")
def create_goal(payload: dict, user=Depends(require_user)):
    goal = payload.get("goal", "")
    channel_id = payload.get("channel_id", None)  # Static for now

    state = {
        "goal": goal,
        "channel_id": channel_id,
        "user_id": user["id"],
    }

    try:
        result = run_goal_workflow_adk(state)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"ADK workflow failed: {exc}")

    return {
        "message": "Workflow executed",
        "tasks": result.get("tasks", []),
        "research": result.get("research", {}),
    }


@router.post("/analyze")
def analyze(payload: dict, user=Depends(require_user)):
    channel_id = payload.get("channel_id", None)
    state = {
        "tasks": [],
        "channel_id": channel_id,
        "user_id": user["id"],
    }

    try:
        state = reflection_agent(state)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"ADK reflection failed: {exc}")

    return {
        "message": "Re-analysis complete",
        "new_tasks": state.get("tasks", []),
    }


@router.post("/task/update")
def update_task(payload: dict, user=Depends(require_user)):
    task_uuid = payload.get("uuid", "")
    status = payload.get("status")
    live = payload.get("live")
    allowed = {"TODO", "IN_PROGRESS", "COMPLETED", "OUT_OF_SCOPE"}

    if not task_uuid:
        return {"message": "Task uuid is required"}

    if status is not None and status not in allowed:
        return {
            "message": "Invalid status",
            "allowed": sorted(allowed)
        }

    if status is not None:
        update_task_status(task_uuid, status, user_id=user["id"])

    if live is not None:
        set_task_live(task_uuid, bool(live), user_id=user["id"])

    sync_tasks_to_sheets(user_id=user["id"])

    return {
        "message": "Task updated",
        "uuid": task_uuid,
        "status": status,
        "live": live
    }


@router.get("/tasks")
def get_tasks(user=Depends(require_user)):
    return {
        "tasks": get_active_tasks_by_user(user["id"])
    }


@router.get("/tasks/history")
def get_tasks_history(user=Depends(require_user)):
    return {
        "tasks": get_all_tasks_by_user(user["id"])
    }


@router.get("/ops/adk/agent")
def get_adk_agent_info(user=Depends(require_user)):
    agent = build_ops_agent()
    return {
        "name": agent.name,
        "model": agent.model,
        "tool_count": len(agent.tools),
    }