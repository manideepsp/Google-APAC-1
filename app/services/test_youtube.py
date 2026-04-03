from app.services.youtube_client import get_trending

def test():
    res = get_trending()
    print("Titles:", list(res.titles))
    print("Topics:", list(res.topics))

if __name__ == "__main__":
    test()