import os

from server.utils import setup_logger

logger = setup_logger(__name__)


MAX_CONTENT_CHARS = 800  # Truncate per-result content to limit memory on Render 512MB


def search_web(query: str, max_results: int = 2) -> list[dict]:
    """
    Search the web via Tavily. Returns [{content, url, title, source, source_type}].
    Returns empty list if TAVILY_API_KEY not set or search fails.
    """
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        logger.warning("TAVILY_API_KEY not set — skipping web search")
        return []

    logger.info("Tavily search | query: %s", query[:80])

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        response = client.search(query, max_results=max_results, search_depth="advanced")
        results = []
        for r in response.get("results", []):
            results.append({
                "content": r.get("content", "")[:MAX_CONTENT_CHARS],
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "source": r.get("url", ""),
                "source_type": "web",
                "page": None,
                "similarity_score": None,
                "bm25_score": None,
                "rrf_score": None,
                "rerank_score": None,
            })
        for i, r in enumerate(results):
            logger.info("  web[%d] %s | %s", i + 1, r["title"][:60], r["url"][:80])
        logger.info("Tavily: %d results returned", len(results))
        return results
    except Exception as e:
        logger.error("Tavily search failed: %s", e)
        return []


def format_web_context(results: list[dict]) -> str:
    """Format Tavily results as a context string to prepend to the question."""
    if not results:
        return ""
    parts = ["[Additional context from web search:]"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "Web result")
        url = r.get("url", "")
        content = r.get("content", "")
        parts.append(f"\n[{i}] {title} ({url})\n{content}")
    return "\n".join(parts)
