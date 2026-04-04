from app.adk.workflow_agents import reflect_tasks_with_adk
from app.services.youtube_client import get_channel_analytics
from app.services.kpi_builder import build_kpis
from app.db.sqlite import get_active_tasks_by_user, replace_tasks
from app.services.sheets_sync import sync_tasks_to_sheets


def reflection_agent(state: dict):
    user_id = state.get("user_id")

    # 🔹 Get channel ID (static if not passed)
    channel_id = state.get("channel_id")

    if not channel_id:
        # fallback strategy
        return state

    analytics = get_channel_analytics(channel_id)

    # Convert analytics into pseudo structure
    analytics_data = [{
        "data": {
            "top_videos": [
                {"title": v, "views": 0} for v in analytics.top_videos
            ]
        }
    }]

    # 🔹 Build KPIs
    kpis = build_kpis(
        trending_data={"titles": []},  # reflection uses performance
        analytics_data=analytics_data
    )

    current_tasks = get_active_tasks_by_user(user_id)

    new_tasks = reflect_tasks_with_adk(kpis=kpis, current_tasks=current_tasks)

    if new_tasks:
        replace_tasks(new_tasks, user_id=user_id)
        sync_tasks_to_sheets(user_id=user_id)

    state["tasks"] = new_tasks
    return state