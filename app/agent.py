"""The research agent: turn a user's request into a finished brief.

Pipeline:  request -> (LLM proposes search queries) -> web search
           -> LLM writes the brief -> HTML email.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from . import llm
from .search import format_context, web_search

log = logging.getLogger("cadence.agent")

QUERY_SYSTEM = (
    "You turn an information request into 1-3 focused web search queries. "
    "Return ONLY the queries, one per line, no numbering, no commentary."
)

BRIEF_SYSTEM = (
    "You are Cadence, a precise research assistant that writes concise, factual "
    "information briefs from web search results. Rules:\n"
    "- Lead with the single most important takeaway.\n"
    "- Use specific numbers, dates, and named sources when present in the context.\n"
    "- Prefer short sections with bold labels and tight bullet points.\n"
    "- If the context lacks the answer, say so plainly rather than inventing facts.\n"
    "- Never fabricate figures. Keep it skimmable in under two minutes.\n"
    "- Output clean, minimal HTML using only <h3>, <p>, <ul>, <li>, <strong>, "
    "<em>, and <a> tags. No <html>, <head>, or <body> wrappers."
)


@dataclass
class Brief:
    subject: str
    html: str
    text: str
    used_llm: bool
    used_search: bool
    note: str = ""


def _proposed_queries(request: str) -> list[str]:
    try:
        raw = llm.chat(QUERY_SYSTEM, request, temperature=0.2, max_tokens=120)
        queries = [q.strip("-• ").strip() for q in raw.splitlines() if q.strip()]
        return queries[:3] or [request]
    except Exception as e:
        log.warning("Query expansion failed, using raw request: %s", e)
        return [request]


def _wrap_email(inner_html: str, request: str, when: str) -> str:
    return f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
            max-width:640px;margin:0 auto;color:#1a1a1a;line-height:1.55;">
  <div style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;
              color:#6b7280;margin-bottom:4px;">Cadence brief · {when}</div>
  <div style="font-size:13px;color:#6b7280;margin-bottom:20px;">
    Your request: <em>{request}</em></div>
  <div style="border-top:1px solid #e5e7eb;padding-top:16px;">{inner_html}</div>
  <div style="border-top:1px solid #e5e7eb;margin-top:24px;padding-top:12px;
              font-size:12px;color:#9ca3af;">
    Delivered by Cadence · generated from live web search results.
  </div>
</div>"""


def build_brief(request: str, tz: str = "UTC", label: str = "") -> Brief:
    """Run the full pipeline and return a finished Brief."""
    try:
        now = datetime.now(ZoneInfo(tz))
    except Exception:
        now = datetime.utcnow()
    when = now.strftime("%A, %d %B %Y, %H:%M %Z").strip()

    # 1) Search the web (works with or without an LLM key).
    queries = _proposed_queries(request) if llm.settings.llm_enabled else [request]
    all_results = []
    for q in queries:
        all_results.extend(web_search(q, max_results=5))
    # de-dup by url
    seen, results = set(), []
    for r in all_results:
        k = r.url or r.title
        if k and k not in seen:
            seen.add(k)
            results.append(r)
    context = format_context(results[:10])
    used_search = bool(results)

    # 2) Compose the brief.
    subject_label = label.strip() or request.strip()
    subject = f"Cadence: {subject_label[:70]}"

    if not llm.settings.llm_enabled:
        # Graceful preview mode: show what we found, explain how to enable the LLM.
        items = "".join(
            f"<li><a href='{r.url}'>{r.title or r.url}</a>"
            f"{(' — ' + r.snippet) if r.snippet else ''}</li>"
            for r in results[:8]
        )
        inner = (
            "<h3>Preview mode</h3>"
            "<p>Add a <strong>GROQ_API_KEY</strong> to your <code>.env</code> to have "
            "Cadence write a real narrative brief. For now, here are the live web "
            "results it would summarize:</p>"
            f"<ul>{items or '<li>No results found.</li>'}</ul>"
        )
        html = _wrap_email(inner, request, when)
        return Brief(subject, html, _to_text(inner), used_llm=False,
                     used_search=used_search, note="LLM disabled (no GROQ_API_KEY)")

    user_prompt = (
        f"Today is {when}.\n\n"
        f"Information request:\n{request}\n\n"
        f"Web search results to base the brief on:\n{context}\n\n"
        "Write the brief now."
    )
    inner_html = llm.chat(BRIEF_SYSTEM, user_prompt, temperature=0.3, max_tokens=1200)
    html = _wrap_email(inner_html, request, when)
    return Brief(subject, html, _to_text(inner_html), used_llm=True,
                 used_search=used_search)


def _to_text(html: str) -> str:
    """Very small HTML-to-text for the plaintext email part."""
    import re

    text = re.sub(r"<li>", "• ", html)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
