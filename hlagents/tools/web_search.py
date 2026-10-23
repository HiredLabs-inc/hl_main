from django.conf import settings
from tavily import TavilyClient

from .base import Tool, ToolError


def web_search(query: str) -> dict:
    if not settings.TAVILY_API_KEY:
        raise ToolError("TAVILY_API_KEY isn't set.")
    return TavilyClient(api_key=settings.TAVILY_API_KEY).search(query=query, max_results=5)


WEB_SEARCH = Tool(
    name="web_search",
    description="Search the web.",
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string", "description": "The search query"}},
        "required": ["query"],
    },
    func=web_search,
)
