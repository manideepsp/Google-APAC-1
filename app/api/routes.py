from fastapi import APIRouter
from app.graph.workflow import build_graph
from app.db.sqlite import update_task_status
from app.services.sheets_sync import sync_tasks_to_sheets

router = APIRouter()

graph = build_graph()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/goal")
def create_goal(payload: dict):
    goal = payload.get("goal", "")
    channel_id = payload.get("channel_id", None)  # Static for now

    state = {
        "goal": goal,
        "channel_id": channel_id
    }

    result = graph.invoke(state)

    return {
        "message": "Workflow executed",
        "tasks": result.get("tasks", []),
        "research": result.get("research", {})
    }
    
from app.agents.reflection_agent import reflection_agent


@router.post("/analyze")
def analyze(payload: dict):
    channel_id = payload.get("channel_id", None)
    state = {
        "tasks": [],
        "channel_id": channel_id
    }

    state = reflection_agent(state)

    return {
        "message": "Re-analysis complete",
        "new_tasks": state.get("tasks", [])
    }


@router.post("/task/update")
def update_task(payload: dict):
    task_uuid = payload.get("uuid", "")
    status = payload.get("status", "")
    allowed = {"TODO", "IN_PROGRESS", "COMPLETED", "OUT_OF_SCOPE"}

    if not task_uuid:
        return {"message": "Task uuid is required"}

    if status not in allowed:
        return {
            "message": "Invalid status",
            "allowed": sorted(allowed)
        }

    update_task_status(task_uuid, status)
    sync_tasks_to_sheets()

    return {
        "message": "Task updated",
        "uuid": task_uuid,
        "status": status
    }