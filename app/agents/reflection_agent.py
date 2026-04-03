from app.core.llm import get_llm
from app.services.youtube_client import get_channel_analytics

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

    analytics = get_channel_analytics("dummy_channel")

    current_tasks = state.get("tasks", [])

    prompt = f"""
    You are a YouTube growth expert.

    Current analytics:
    Growth: {analytics.growth}
    Top videos: {list(analytics.top_videos)}

    Current tasks:
    {current_tasks}

    Suggest improvements and new tasks.

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

    try:
        new_tasks = extract_json(response.content)
    except Exception:
        new_tasks = []

    state["tasks"] = new_tasks
    return state