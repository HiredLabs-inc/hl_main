outreach_agent_tool_schema = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web for information about veteran-serving organizations.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"}
            },
            "required": ["query"]
        }
    }
}

funding_agent_tool_schema = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web for information about funding opportunities.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"}
            },
            "required": ["query"]
        }
    }
}
