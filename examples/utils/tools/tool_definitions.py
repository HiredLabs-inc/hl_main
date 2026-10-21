from tavily import TavilyClient


def web_search(query: str, api_key) -> dict:
    client = TavilyClient(api_key=api_key)
    results = client.search(query=query, max_results=5)
    return results
