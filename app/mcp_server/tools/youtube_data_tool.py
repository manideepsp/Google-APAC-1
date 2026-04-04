from app.services.youtube_client import get_trending


def youtube_data_tool() -> dict:
    """Fetch current YouTube trending titles/topics via gRPC."""
    response = get_trending()
    return {
        "titles": list(response.titles),
        "topics": list(response.topics),
        "count": len(response.titles),
    }
