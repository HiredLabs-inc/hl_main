from .base import Tool, ToolError
from .web_search import client

# Characters of the page the model sees
PAGE_LENGTH = 12000


def read_page(url: str) -> dict:
    response = client().extract(urls=[url], format="markdown")
    results = response.get("results") or []
    if not results:
        failed = response.get("failed_results") or [{}]
        raise ToolError(f"Couldn't read {url}: {failed[0].get('error') or 'no content'}")
    page = results[0]
    content = page.get("raw_content") or ""
    return {
        "url": page.get("url") or url,
        "content": content[:PAGE_LENGTH],
        "truncated": len(content) > PAGE_LENGTH,
    }


READ_PAGE = Tool(
    name="read_page",
    description="Read a web page's text, to check details a search snippet doesn't show.",
    parameters={
        "type": "object",
        "properties": {"url": {"type": "string", "description": "The page's full URL"}},
        "required": ["url"],
    },
    func=read_page,
)
