from app.core.llm import get_llm
from app.core.utils.json_parser import extract_json



def planning_agent(state: dict):
    llm = get_llm()

    goal = state.get("goal", "")
    research = state.get("research", {})

    insights = research.get("insights", "")
    titles = research.get("titles", [])

    prompt = f"""
    You are an expert YouTube growth strategist.

    Goal:
    {goal}

    Trending Signals:
    {titles}

    Strategic Insights:
    {insights}

    Based on this:
    1. Define a clear content strategy
    2. Generate actionable tasks

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
        tasks = extract_json(response.content)
    except Exception:
        tasks = []

    state["tasks"] = tasks
    return state