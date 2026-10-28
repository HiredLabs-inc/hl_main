"""Web search through the web_search task: a Gemini call with Google Search
grounding (docs/gcp-agents.md §3.2)."""
import re
from urllib.parse import urlsplit

import requests
from django.conf import settings

from .base import SUGGESTIONS, Tool, ToolError

# Characters of each result's snippet the model sees
SNIPPET_LENGTH = 1000
MAX_RESULTS = 8
TASK = "web_search"
# Grounding links point here and redirect to the page Gemini cited
REDIRECT_HOST = "vertexaisearch.cloud.google.com"
RESOLVE_TIMEOUT = 10
# Snippets are Gemini's words about a page, not the page's, so a URL or email in
# one could be made up. They're removed, so the lead checks only find ones a
# real page had (AgentType.validate).
UNGROUNDED = re.compile(r"https?://\S+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def search(query, max_results) -> tuple[list, str]:
    """Up to `max_results` results for the sources Gemini cited, with their real
    URLs, and Google's search-suggestions HTML."""
    # Imported here: completion imports services, which the tools mustn't need to load
    from hlagents.completion import CompletionFailed, complete_result

    try:
        result = complete_result(TASK, query, limit=settings.HLAGENTS_CALL_TIME_LIMIT)
    except CompletionFailed as e:
        raise ToolError(f"The search failed: {e.reason}") from e
    results = []
    for source in result.sources:
        url = resolve(source["uri"])
        if not url or any(r["url"] == url for r in results):
            continue
        snippet = " ".join(UNGROUNDED.sub("", " ".join(source["snippets"])).split())
        results.append({"title": source["title"], "url": url, "content": snippet[:SNIPPET_LENGTH]})
        if len(results) >= max_results:
            break
    return results, result.suggestions


def resolve(uri) -> str:
    """The page a grounding link redirects to, or "" if it doesn't. A redirect
    link would fail the funding agent's URL checks."""
    if urlsplit(uri).hostname != REDIRECT_HOST:
        return uri
    try:
        response = requests.head(uri, allow_redirects=False, timeout=RESOLVE_TIMEOUT)
    except requests.RequestException:
        return ""
    return response.headers.get("Location", "") if response.is_redirect else ""


def web_search(query: str, max_results: int = MAX_RESULTS) -> dict:
    max_results = max(1, min(int(max_results), 20))
    results, suggestions = search(query, max_results)
    output = {"results": results}
    if suggestions:
        output[SUGGESTIONS] = suggestions
    return output


WEB_SEARCH = Tool(
    name="web_search",
    description="Search the web with Google. Returns each result's title, URL and what it says about the query.",
    note="Snippets leave out links and email addresses: read the page for those.",
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
