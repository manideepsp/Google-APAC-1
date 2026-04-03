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
    
def fetch_channel_analytics(channel_id: str, max_results=5):
    youtube = get_youtube_client()

    # 1. Channel stats
    channel_res = youtube.channels().list(
        part="statistics",
        id=channel_id
    ).execute()

    stats = channel_res["items"][0]["statistics"]

    subscriber_count = stats.get("subscriberCount", "0")
    video_count = stats.get("videoCount", "0")

    # 2. Get uploads playlist
    content_res = youtube.channels().list(
        part="contentDetails",
        id=channel_id
    ).execute()

    uploads_playlist = content_res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    # 3. Fetch videos
    playlist_res = youtube.playlistItems().list(
        part="snippet",
        playlistId=uploads_playlist,
        maxResults=max_results
    ).execute()

    video_ids = [
        item["snippet"]["resourceId"]["videoId"]
        for item in playlist_res["items"]
    ]

    # 4. Get video stats
    video_res = youtube.videos().list(
        part="statistics,snippet",
        id=",".join(video_ids)
    ).execute()

    videos = []

    for item in video_res["items"]:
        videos.append({
            "title": item["snippet"]["title"],
            "views": int(item["statistics"].get("viewCount", 0)),
            "likes": int(item["statistics"].get("likeCount", 0))
        })

    # Sort by views
    videos = sorted(videos, key=lambda x: x["views"], reverse=True)

    return {
        "subscriber_count": subscriber_count,
        "video_count": video_count,
        "top_videos": videos[:3]
    }