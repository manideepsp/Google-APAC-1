from app.services.youtube_client import get_trending
from app.services.youtube_helper import fetch_multiple_channel_analytics
from app.core.llm import get_llm
from app.services.kpi_builder import build_kpis
from app.services.websearch_helper import search_web


def research_agent(state: dict):
    llm = get_llm()
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
            }
        )

    # 4. Build KPIs
    kpis = build_kpis(
        trending_data={"titles": titles},
        analytics_data=analytics_data
    )

    # 5. Prepare summary input
    summary_input = f"""
    You are a YouTube growth strategist.

    Goal:
    {goal}

    Trending YouTube Titles:
    {titles}

    Channel Performance Insights:
    {analytics_data}

    Web Insights (latest trends & ideas):
    {web_insights}

    KPIs:
    {kpis}

     Analyze deeply and provide:

     1. Emerging Trends:
         - What topics are rising and why?

     2. Winning Patterns:
         - Common traits among high-performing content

     3. Strategic Recommendations:
         - What exact content direction should be followed?

     4. Content Opportunities:
         - Specific video ideas aligned with goal

     Be concise, actionable, and data-driven.
    """

    # 6. LLM synthesis
    response = llm.invoke(summary_input)

    state["research"] = {
        "goal": goal,
        "titles": titles,
        "channels": channels,
        "analytics": analytics_data,
        "web_insights": web_insights,
        "kpis": kpis,
        "insights": response.content
    }

    return state