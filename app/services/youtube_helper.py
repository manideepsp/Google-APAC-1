from googleapiclient.discovery import build
import os
from dotenv import load_dotenv
load_dotenv()


def get_youtube_client():
    api_key = os.getenv("YOUTUBE_API_KEY")

    if not api_key:
        raise ValueError("YOUTUBE_API_KEY not set")

    youtube = build(
        "youtube",
        "v3",
        developerKey=api_key
    )
    return youtube

def fetch_trending_videos(region="IN", max_results=10):
    youtube = get_youtube_client()

    request = youtube.videos().list(
        part="snippet",
        chart="mostPopular",
        regionCode=region,
        maxResults=max_results
    )

    response = request.execute()

    titles = []
    channels = []
    published_at = []

    for item in response.get("items", []):
        snippet = item.get("snippet", {})

        titles.append(snippet.get("title", ""))
        channels.append(snippet.get("channelTitle", ""))
        published_at.append(snippet.get("publishedAt", ""))

    return {
        "titles": titles,
        "channels": channels,
        "published_at": published_at
    }