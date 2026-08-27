from duckduckgo_search import DDGS
from app.core.config import TAVILY_API_KEY


def _search_tavily(query: str, max_results: int = 5) -> list[dict]:
    if not TAVILY_API_KEY:
        return []
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=TAVILY_API_KEY)
        response = client.search(query=query, max_results=max_results, search_depth="basic")
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
                "source": "tavily",
                "score": r.get("score", 0),
            }
            for r in response.get("results", [])
        ]
    except Exception:
        return []


def _search_ddg(query: str, max_results: int = 5) -> list[dict]:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                    "source": "duckduckgo",
                    "score": 0,
                }
                for r in results
            ]
    except Exception:
        return []


def _merge_results(tavily: list[dict], ddg: list[dict]) -> list[dict]:
    seen_urls = set()
    merged = []

    for r in tavily:
        domain = r["url"].split("//")[-1].split("/")[0].replace("www.", "")
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            merged.append(r)

    for r in ddg:
        domain = r["url"].split("//")[-1].split("/")[0].replace("www.", "")
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            merged.append(r)

    return merged


def research_topic(problem_statement: str) -> tuple[str, list[dict], list[str]]:
    queries = [
        f"{problem_statement} existing products competitors",
        f"{problem_statement} open source github",
        f"{problem_statement} APIs tools libraries",
    ]

    all_results = []
    sources_used = set()

    for query in queries:
        tavily_results = _search_tavily(query, max_results=5)
        ddg_results = _search_ddg(query, max_results=5)

        if tavily_results:
            sources_used.add("Tavily")
        if ddg_results:
            sources_used.add("DuckDuckGo")

        merged = _merge_results(tavily_results, ddg_results)
        all_results.extend(merged)

    seen_urls = set()
    unique_results = []
    for r in all_results:
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            unique_results.append(r)

    if not unique_results:
        return "No web search results found. Using LLM knowledge only.", [], []

    source_label = " + ".join(sorted(sources_used)) if sources_used else "Web"
    formatted = f"## Web Research Results (Dual Search: {source_label})\n\n"
    formatted += f"**{len(unique_results)} unique results** from {len(sources_used)} search engine(s)\n\n"

    for r in unique_results:
        formatted += f"**{r['title']}** `[{r['source']}]`\n"
        formatted += f"URL: {r['url']}\n"
        formatted += f"{r['snippet']}\n\n"

    return formatted, unique_results, sorted(sources_used)


import asyncio

async def async_research_topic(problem_statement: str) -> tuple[str, list[dict], list[str]]:
    """Non-blocking async wrapper around synchronous web search."""
    return await asyncio.to_thread(research_topic, problem_statement)
