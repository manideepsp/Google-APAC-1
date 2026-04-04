import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.websearch_helper import search_web


def test() -> None:
    results = search_web("latest AI YouTube trends 2026")

    for result in results:
        print("\nTitle:", result["title"])
        print("Content:", result["content"])
        if result.get("key_ideas"):
            print("Key ideas:")
            for idea in result["key_ideas"]:
                print("-", idea)


if __name__ == "__main__":
    test()