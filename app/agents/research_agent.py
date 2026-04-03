from app.core.llm import get_llm

def research_agent(state: dict):
    llm = get_llm()
    
    goal = state["goal"]

    prompt = f"""
    You are a YouTube growth expert.

    Analyze this goal:
    {goal}

    Provide:
    - trending topics
    - content ideas
    - audience insights
    """

    response = llm.invoke(prompt)

    state["research"] = response.content
    return state