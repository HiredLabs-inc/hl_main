"""A run's messages as entries for the run page."""
import json


def _tool_summary(content):
    """Short description of a tool result: an error, or how many results it had."""
    try:
        data = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return ""
    if isinstance(data, dict):
        if "error" in data:
            return f"Error: {data['error']}"
        if isinstance(data.get("results"), list):
            count = len(data["results"])
            return f"{count} result{'' if count == 1 else 's'}"
    return ""


def conversation(messages):
    """[{kind, text, detail}], where kind is system, user, thinking, search, result or answer."""
    entries = []
    for message in messages:
        role = message.get("role")
        content = message.get("content") or ""
        if role == "system":
            entries.append({"kind": "system", "text": "System prompt", "detail": content})
        elif role == "user":
            entries.append({"kind": "user", "text": content})
        elif role == "tool":
            entries.append({"kind": "result", "text": _tool_summary(content), "detail": content})
        elif role == "assistant":
            if message.get("thinking"):
                entries.append({"kind": "thinking", "text": "Thinking", "detail": message["thinking"]})
            for call in message.get("tool_calls") or []:
                function = call.get("function", {})
                arguments = function.get("arguments") or {}
                if isinstance(arguments, dict) and "query" in arguments:
                    text = arguments["query"]
                else:
                    text = json.dumps(arguments)
                entries.append({"kind": "search", "text": text, "detail": function.get("name", "")})
            if content:
                entries.append({"kind": "answer", "text": content})
    return entries
