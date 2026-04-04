from app.services.websearch_helper import search_web


def web_search_tool(query: str, max_results: int = 3) -> dict:
    """Fetch web intelligence results for a query."""
    results = search_web(query=query, max_results=max_results)
    return {
        "query": query,
        "results": results,
        "count": len(results),
    }
