from app.services.youtube_client import get_channel_analytics


def youtube_analytics_tool(channel_id: str) -> dict:
    """Fetch YouTube channel analytics by channel id via gRPC."""
    response = get_channel_analytics(channel_id)
    return {
        "channel_id": channel_id,
        "growth": response.growth,
        "top_videos": list(response.top_videos),
    }
