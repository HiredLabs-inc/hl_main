"""Tools agents can call (docs/hlagents.md §3.1)."""
from .base import Tool, ToolError
from .web_search import WEB_SEARCH

TOOLS = {tool.name: tool for tool in (WEB_SEARCH,)}


def tool_schema(name, description=None) -> dict:
    """The tool's schema for a provider, with an optional description override."""
    tool = TOOLS[name]
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": description or tool.description,
            "parameters": tool.parameters,
        },
    }
