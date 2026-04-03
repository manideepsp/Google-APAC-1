from app.services.youtube_client import get_channel_analytics

def test():
    res = get_channel_analytics("UC_x5XG1OV2P6uZZ5FSM9Ttw")

    print("Growth:", res.growth)
    print("Top Videos:")

    for v in res.top_videos:
        print("-", v)

if __name__ == "__main__":
    test()