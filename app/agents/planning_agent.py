from app.core.llm import get_llm
from app.core.utils.json_parser import extract_json



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

    tasks = extract_json(response.content)

    state["tasks"] = tasks
    return state