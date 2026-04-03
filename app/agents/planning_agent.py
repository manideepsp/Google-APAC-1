from app.core.llm import get_llm
import json


def planning_agent(state: dict):
    llm = get_llm()

    research = state.get("research", {})

    prompt = f"""
    You are a YouTube growth strategist.

    Based on this research data:
    {research}

    Generate a list of actionable tasks.

    Return ONLY valid JSON in this format:
    [
      {{
        "task": "...",
        "priority": "High/Medium/Low",
        "day": "Day 1"
      }}
    ]

    Do not include any explanation.
    """

    response = llm.invoke(prompt)

    try:
        tasks = json.loads(response.content)
    except Exception:
        tasks = []

    state["tasks"] = tasks
    return state