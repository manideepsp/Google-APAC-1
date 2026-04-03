from app.services.youtube_helper import get_youtube_client

def test():
    yt = get_youtube_client()
    print("Client created:", yt is not None)

if __name__ == "__main__":
    test()