from app.core.llm import get_llm
from app.services.youtube_client import get_channel_analytics
from app.services.kpi_builder import build_kpis
from app.db.sqlite import get_active_tasks_by_user, replace_tasks
from app.services.sheets_sync import sync_tasks_to_sheets


import re
import json


def extract_json(text: str):
    try:
        # Try direct parse
        return json.loads(text)
    except:
        pass

    # Try extracting JSON block
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except:
            pass

    return []


def reflection_agent(state: dict):
    llm = get_llm()
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

    # 🔹 LLM reasoning
    prompt = f"""
    You are a YouTube growth strategist.

    Channel Performance KPIs:
    {kpis}

    Previous Tasks:
    {current_tasks}

    Based on performance:
    - What is working?
    - What should change?
    - Generate improved tasks
    - Compare high-performing videos vs current plan and suggest optimizations.

    Return ONLY JSON:
    [
      {{
        "task": "...",
        "priority": "High/Medium/Low",
        "day": "Day X"
      }}
    ]
    """

    response = llm.invoke(prompt)

    raw_content = response.content
    if not isinstance(raw_content, str):
        raw_content = json.dumps(raw_content)

    try:
        new_tasks = extract_json(raw_content)
    except Exception:
        new_tasks = []

    if new_tasks:
        replace_tasks(new_tasks, user_id=user_id)
        sync_tasks_to_sheets(user_id=user_id)

    state["tasks"] = new_tasks
    return state