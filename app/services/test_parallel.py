from app.services.youtube_helper import fetch_trending_videos, fetch_multiple_channel_analytics

def test():
    trending = fetch_trending_videos()

    channel_ids = trending["channel_ids"]

    print("Fetching analytics for channels:", channel_ids[:3])

    results = fetch_multiple_channel_analytics(channel_ids)

    for r in results:
        print("\nChannel:", r["channel_id"])

        if "data" in r:
            print("Top Videos:")
            for v in r["data"]["top_videos"]:
                print("-", v["title"])
        else:
            print("Error:", r["error"])

if __name__ == "__main__":
    test()