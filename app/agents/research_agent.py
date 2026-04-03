from app.services.youtube_client import get_trending

def research_agent(state: dict):
    res = get_trending()

    state["research"] = {
        "titles": list(res.titles),
        "topics": list(res.topics)
    }

    return state