"""Web search for finding a competitor's pages. First provider: Tavily."""

import httpx

from app.core.config import settings

TAVILY_URL = "https://api.tavily.com/search"


class SearchUnavailable(Exception):
    """No search provider is configured."""


def enabled() -> bool:
    return bool(settings.TAVILY_API_KEY)


def search(query: str, max_results: int = 5) -> list[dict]:
    """[{url, title, content}] for a query; raises SearchUnavailable without a key."""
    if not settings.TAVILY_API_KEY:
        raise SearchUnavailable("TAVILY_API_KEY is not set")
    response = httpx.post(
        TAVILY_URL,
        headers={"Authorization": f"Bearer {settings.TAVILY_API_KEY}"},
        json={"query": query, "max_results": max_results, "search_depth": "basic"},
        timeout=20,
    )
    response.raise_for_status()
    return [
        {"url": r.get("url", ""), "title": r.get("title", ""), "content": (r.get("content") or "")[:300]}
        for r in response.json().get("results", [])
    ]
