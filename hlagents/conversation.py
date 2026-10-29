"""A run's messages as entries for the run page."""
import json


def tool_text(messages) -> str:
    """Everything the run's tools returned, which candidates are checked against
    (AgentType.validate)."""
    return "\n".join(m.get("content") or "" for m in messages if m.get("role") == "tool")


def note(text, label) -> dict:
    """A message the app adds to a run for the agent, such as the known leads or
    a request to fix its answer. The run page shows it as a note, not as staff's."""
    return {"role": "user", "content": text, "note": label}


def _tool_summary(content):
    """Short description of a tool result: an error, how many results it had,
    or the page it read."""
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
        if "url" in data:
            return data["url"]
    return ""


def conversation(messages):
    """[{kind, text, detail}], where kind is system, user, note, thinking, search,
    result or answer. A user entry's detail is "Request" for the first and
    "Follow-up" after that. Search and result entries also have a label, and
    result entries Google's search suggestions, if any."""
    entries = []
    for message in messages:
        role = message.get("role")
        content = message.get("content") or ""
        if role == "system":
            entries.append({"kind": "system", "text": "System prompt", "detail": content})
        elif role == "user" and message.get("note"):
            entries.append({"kind": "note", "text": message["note"], "detail": content})
        elif role == "user":
            label = "Follow-up" if any(e["kind"] == "user" for e in entries) else "Request"
            entries.append({"kind": "user", "text": content, "detail": label})
        elif role == "tool":
            label = "Page" if message.get("tool_name") == "read_page" else "Search results"
            entries.append({
                "kind": "result", "text": _tool_summary(content), "detail": content, "label": label,
                "suggestions": message.get("suggestions", ""),
            })
        elif role == "assistant":
            if message.get("thinking"):
                entries.append({"kind": "thinking", "text": "Thinking", "detail": message["thinking"]})
            for call in message.get("tool_calls") or []:
                function = call.get("function", {})
                arguments = function.get("arguments") or {}
                if isinstance(arguments, dict) and ("query" in arguments or "url" in arguments):
                    text = arguments.get("query") or arguments["url"]
                else:
                    text = json.dumps(arguments)
                name = function.get("name", "")
                label = "Read" if name == "read_page" else "Searched"
                entries.append({"kind": "search", "text": text, "detail": name, "label": label})
            if content:
                entries.append({"kind": "answer", "text": content})
    return entries
