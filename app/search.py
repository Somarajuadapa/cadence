"""Web search via DuckDuckGo (no API key required).

Kept behind a tiny interface so it can be swapped for Tavily/Brave later.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SearchResult:
    title: str
    snippet: str
    url: str
    source: str = ""
    date: str = ""


def _dedupe(results: list[SearchResult]) -> list[SearchResult]:
    seen: set[str] = set()
    out: list[SearchResult] = []
    for r in results:
        key = r.url or r.title
        if key and key not in seen:
            seen.add(key)
            out.append(r)
    return out


def web_search(query: str, max_results: int = 6) -> list[SearchResult]:
    """Return a mix of recent news and general web results for `query`."""
    try:
        from ddgs import DDGS
    except Exception:  # pragma: no cover - import guard
        return []

    results: list[SearchResult] = []
    try:
        with DDGS() as ddgs:
            # Recent news first — best for "what happened yesterday" briefs.
            try:
                for item in ddgs.news(query, max_results=max_results):
                    results.append(
                        SearchResult(
                            title=item.get("title", ""),
                            snippet=item.get("body", "") or item.get("excerpt", ""),
                            url=item.get("url", "") or item.get("link", ""),
                            source=item.get("source", ""),
                            date=item.get("date", ""),
                        )
                    )
            except Exception:
                pass

            # General web results to round out context.
            try:
                for item in ddgs.text(query, max_results=max_results):
                    results.append(
                        SearchResult(
                            title=item.get("title", ""),
                            snippet=item.get("body", ""),
                            url=item.get("href", "") or item.get("url", ""),
                        )
                    )
            except Exception:
                pass
    except Exception:
        return []

    return _dedupe(results)[: max_results * 2]


def format_context(results: list[SearchResult]) -> str:
    """Flatten search results into a text block for the LLM prompt."""
    if not results:
        return "(No web results were found.)"
    lines: list[str] = []
    for i, r in enumerate(results, 1):
        meta = " · ".join(x for x in (r.source, r.date) if x)
        header = f"[{i}] {r.title}" + (f" ({meta})" if meta else "")
        lines.append(header)
        if r.snippet:
            lines.append(f"    {r.snippet}")
        if r.url:
            lines.append(f"    URL: {r.url}")
    return "\n".join(lines)
