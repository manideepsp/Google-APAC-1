from googleapiclient.discovery import build
import os
from dotenv import load_dotenv

load_dotenv()

import time

CACHE = {
    "trending": {},
    "channel_analytics": {}
}

CACHE_TTL = 300  # 5 minutes


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
    
    cache_key = f"{region}"

    # ✅ CACHE CHECK
    if cache_key in CACHE["trending"]:
        data, ts = CACHE["trending"][cache_key]
        if time.time() - ts < CACHE_TTL:
            print("Using cached trending data")
            return data
    
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
    channel_ids = []

    for item in response.get("items", []):
        snippet = item.get("snippet", {})

        titles.append(snippet.get("title", ""))
        channels.append(snippet.get("channelTitle", ""))
        channel_ids.append(snippet.get("channelId", ""))

    result = {
        "titles": titles,
        "channels": channels,
        "channel_ids": list(set(channel_ids))  # unique
    }

    # ✅ CACHE STORE
    CACHE["trending"][cache_key] = (result, time.time())

    return result

def fetch_channel_analytics(channel_id: str, max_results=5):
    
    cache_key = channel_id

    # ✅ CACHE CHECK
    if cache_key in CACHE["channel_analytics"]:
        data, ts = CACHE["channel_analytics"][cache_key]
        if time.time() - ts < CACHE_TTL:
            print(f"Using cached analytics for {channel_id}")
            return data
    
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

    result = {
        "subscriber_count": subscriber_count,
        "video_count": video_count,
        "top_videos": videos[:3]
    }

    # ✅ CACHE STORE
    CACHE["channel_analytics"][cache_key] = (result, time.time())

    return result

from concurrent.futures import ThreadPoolExecutor, as_completed


def fetch_multiple_channel_analytics(channel_ids, max_workers=3):
    results = []

    def fetch_single(channel_id):
        try:
            data = fetch_channel_analytics(channel_id)
            return {
                "channel_id": channel_id,
                "data": data
            }
        except Exception as e:
            return {
                "channel_id": channel_id,
                "error": str(e)
            }

    # Limit number of channels
    channel_ids = channel_ids[:5]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_single, cid) for cid in channel_ids]

        for future in as_completed(futures):
            results.append(future.result())

    return results