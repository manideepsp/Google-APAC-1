from app.services.youtube_helper import fetch_channel_analytics

def test():
    # Use any public channel ID
    channel_id = "UC_x5XG1OV2P6uZZ5FSM9Ttw"  # Google Developers

    data = fetch_channel_analytics(channel_id)

    print("Subscribers:", data["subscriber_count"])
    print("Top Videos:")

    for v in data["top_videos"]:
        print("-", v["title"], "| Views:", v["views"])

if __name__ == "__main__":
    test()