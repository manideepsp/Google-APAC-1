def build_kpis(trending_data, analytics_data):
    kpis = {}

    # 🔹 Trending KPIs
    titles = trending_data.get("titles", [])
    kpis["total_trending_videos"] = len(titles)

    # Extract keywords (simple heuristic)
    keywords = []
    for title in titles:
        words = title.lower().split()
        keywords.extend(words)

    # crude frequency
    from collections import Counter
    common_words = Counter(keywords).most_common(10)

    kpis["top_keywords"] = [w for w, _ in common_words if len(w) > 3]

    # 🔹 Analytics KPIs
    all_views = []
    top_titles = []

    for channel in analytics_data:
        if "data" in channel:
            videos = channel["data"].get("top_videos", [])

            for v in videos:
                all_views.append(v["views"])
                top_titles.append(v["title"])

    if all_views:
        kpis["avg_views"] = sum(all_views) // len(all_views)
        kpis["max_views"] = max(all_views)
    else:
        kpis["avg_views"] = 0
        kpis["max_views"] = 0

    kpis["top_video_examples"] = top_titles[:5]

    return kpis