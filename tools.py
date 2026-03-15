import logging
import httpx
from markdownify import markdownify as md
from langchain_core.tools import InjectedToolArg, tool
from tavily import TavilyClient
from typing_extensions import Annotated, Literal

_client: TavilyClient | None = None 

def _get_tavily_client() -> TavilyClient:
    global _client
    if _client is None:
        _client = TavilyClient()
    return _client

log = logging.getLogger(__name__)

@tool(parse_docstring=True)
def tavily_search(
    query: str,
    topic: Literal["general", "news", "finance"] = "general",
    search_depth: Literal["advanced", "basic", "fast", "ultra-fast"] = "fast",
    fetch_full_content: bool = False,
    max_results: Annotated[int, InjectedToolArg] = 1,
    ) -> str:
    """Search the web for general context, facts, or news on a topic.

    Prefer 'fast' for most queries. Use 'advanced' for high-precision research.
    Set fetch_full_content=True to fetch and convert the full page content when snippets are insufficient.

    Args:
        query: Search query to execute
        topic: 'general' for broad searches, 'news' for current events, 'finance' for financial data.
        search_depth: 'fast' for low latency, 'ultra-fast' for minimum latency, 'basic' for balanced, 'advanced' for highest relevance.
        fetch_full_content: Set True to fetch full page content via HTTP and convert to markdown. Use when snippet is insufficient.

    Returns:
        Search results with title, URL, and content
    """

    try:
        log.info(f"[RESEARCH AGENT] Executing tavily_search tool for {query}")

        sep = "\n"

        search_results = _get_tavily_client().search(
            query=query,
            max_results=max_results,
            topic=topic,
            search_depth=search_depth,
        )

        results_texts = []

        for result in search_results.get("results", []):
            url = result["url"]
            title = result["title"]
            if fetch_full_content:
                try:
                    response = httpx.get(url, follow_redirects=True, timeout=10)
                    content = md(response.text)
                except Exception as fetch_err:
                    log.warning(f"[RESEARCH AGENT] httpx fetch failed for {url}: {fetch_err}, falling back to snippet")
                    content = result.get("content", "")[:1000]
            else:
                content = result.get("content", "")[:1000]

            result_text = (
                f"{title}\n"
                f"**URL:** {url}\n"
                f"{content}\n\n"
                "---\n"
            )

            results_texts.append(result_text)

        return f"""Found {len(results_texts)} result(s) for '{query}'\n\n{sep.join(results_texts)}"""
    except Exception as e:
        log.error(f"Failed to conduct a search on {query}: {e}", exc_info=True)
        raise


@tool(parse_docstring=True)
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on research progress and decision-making.

    Use this tool after each tool use to analyze results and plan next steps systematically.
    This creates a deliberate pause in the research workflow for quality decision-making.

    When to use:
    - After receiving tool results: What key information did I find?
    - Before deciding next steps: Do I have enough to answer comprehensively?
    - When assessing gaps: What specific information am I still missing?
    - Before concluding: Can I provide a complete answer now?

    Reflection should address:
    1. Analysis of current findings - What concrete information have I gathered?
    2. Gap assessment - What crucial information is still missing?
    3. Quality evaluation - Do I have sufficient evidence/examples for a good answer?
    4. Strategic decision - Should I continue searching or provide my answer?

    Args:
        reflection: Your detailed reflection on research progress, findings, gaps, and next steps

    Returns:
        Confirmation that reflection was recorded for decision-making
    """
    return f"Reflection recorded: {reflection}"