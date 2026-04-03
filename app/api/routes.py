from fastapi import APIRouter
from app.graph.workflow import build_graph

router = APIRouter()

graph = build_graph()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/goal")
def create_goal(payload: dict):
    goal = payload.get("goal", "")

    state = {
        "goal": goal
    }

    result = graph.invoke(state)

    return {
        "message": "Workflow executed",
        "tasks": result.get("tasks", []),
        "research": result.get("research", {})
    }