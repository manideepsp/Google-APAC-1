from langchain_google_genai import data

from app.services.youtube_helper import fetch_trending_videos

def test():
    data = fetch_trending_videos()
    print(data["channel_ids"])

    print("Titles:")
    for t in data["titles"]:
        print("-", t)

    print("\nChannels:")
    for c in data["channels"]:
        print("-", c)

if __name__ == "__main__":
    test()