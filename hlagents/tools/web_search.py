from django.conf import settings
from tavily import TavilyClient

from .base import Tool, ToolError

# Characters of each result's snippet the model sees
SNIPPET_LENGTH = 1000
MAX_RESULTS = 8


def client() -> TavilyClient:
    if not settings.TAVILY_API_KEY:
        raise ToolError("TAVILY_API_KEY isn't set.")
    return TavilyClient(api_key=settings.TAVILY_API_KEY)


def web_search(query: str, max_results: int = MAX_RESULTS) -> dict:
    """Only each result's title, URL and snippet: the rest of Tavily's reply is
    noise to the model."""
    max_results = max(1, min(int(max_results), 20))
    response = client().search(query=query, search_depth="advanced", max_results=max_results)
    return {
        "results": [
            {"title": r.get("title", ""), "url": r.get("url", ""), "content": (r.get("content") or "")[:SNIPPET_LENGTH]}
            for r in response.get("results", [])
        ]
    }


WEB_SEARCH = Tool(
    name="web_search",
    description="Search the web. Returns each result's title, URL and a snippet.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query"},
            "max_results": {"type": "integer", "description": f"How many results, 1-20 (default {MAX_RESULTS})"},
        },
        "required": ["query"],
    },
    func=web_search,
)
