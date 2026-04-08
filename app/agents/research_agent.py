from app.services.youtube_client import get_trending
from app.services.youtube_helper import fetch_multiple_channel_analytics
from app.adk.workflow_agents import summarize_research_with_adk
from app.services.kpi_builder import build_kpis
from app.services.websearch_helper import search_web


def research_agent(state: dict):
    goal = state.get("goal", "")

    # 1. Fetch trending via gRPC
    trending = get_trending()

    titles = list(trending.titles)
    channels = list(trending.topics)  # topics = channels (MVP)

    # 2. Extract channel IDs via helper (re-fetch for IDs)
    from app.services.youtube_helper import fetch_trending_videos
    trending_raw = fetch_trending_videos()

    channel_ids = trending_raw.get("channel_ids", [])

    # 3. Fetch analytics in parallel
    analytics_data = fetch_multiple_channel_analytics(channel_ids)

    # 3.5 Web search (goal-driven)
    query_goal = goal[:100]
    search_query = f"{query_goal} YouTube trends 2026 content ideas"
    try:
        web_results = search_web(search_query, max_results=3)
    except Exception:
        web_results = []

    web_insights = []
    for item in web_results:
        web_insights.append(
            {
                "title": item.get("title", ""),
                "ideas": item.get("key_ideas", []),
                "url": item.get("url", ""),
                "summary": item.get("summary", ""),
            }
        )

    # 4. Build KPIs
    kpis = build_kpis(
        trending_data={"titles": titles},
        analytics_data=analytics_data
    )

    insights = summarize_research_with_adk(
        goal=goal,
        titles=titles,
        analytics_data=analytics_data,
        web_insights=web_insights,
        kpis=kpis,
    )

    state["research"] = {
        "goal": goal,
        "titles": titles,
        "channels": channels,
        "analytics": analytics_data,
        "web_insights": web_insights,
        "kpis": kpis,
        "insights": insights
    }

    return state