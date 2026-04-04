import os
import re
import time
from typing import Any

from dotenv import load_dotenv
from tavily import TavilyClient


CACHE = {
    "web_search": {}
}

CACHE_TTL = 300  # 5 minutes


def get_tavily_client() -> TavilyClient:
    load_dotenv()
    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        raise ValueError("TAVILY_API_KEY not set")

    return TavilyClient(api_key=api_key)


def _clean_text(text: str) -> str:
    # Normalize whitespace and remove noisy control characters from snippets.
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    return cleaned


def _extract_key_ideas(content: str, limit: int = 3) -> list[str]:
    content = _clean_text(content)
    if not content:
        return []

    parts = re.split(r"(?<=[.!?])\s+", content)
    ideas = [p.strip() for p in parts if p.strip()]
    return ideas[:limit]


def search_web(query: str, max_results: int = 3) -> list[dict[str, Any]]:
    normalized_query = _clean_text(query)
    if not normalized_query:
        return []

    safe_max_results = max(1, min(max_results, 3))
    cache_key = f"{normalized_query.lower()}::{safe_max_results}"

    if cache_key in CACHE["web_search"]:
        data, ts = CACHE["web_search"][cache_key]
        if time.time() - ts < CACHE_TTL:
            return data

    client = get_tavily_client()
    response = client.search(query=normalized_query, max_results=safe_max_results)

    results: list[dict[str, Any]] = []
    for item in response.get("results", []):
        raw_content = item.get("content", "")
        content = _clean_text(raw_content)[:300]
        results.append(
            {
                "title": _clean_text(item.get("title", "")),
                "summary": content,
                "content": content,
                "key_ideas": _extract_key_ideas(raw_content),
                "url": item.get("url", ""),
            }
        )

    CACHE["web_search"][cache_key] = (results, time.time())

    return results