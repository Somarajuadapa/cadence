"""LLM client — Groq's OpenAI-compatible chat completions API.

Uses an open-weights model (Llama 3.3 70B by default). Kept behind a single
`chat()` function so the provider can be swapped (Ollama, OpenRouter, ...).
"""

from __future__ import annotations

import httpx

from .config import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class LLMNotConfigured(RuntimeError):
    pass


def chat(system: str, user: str, temperature: float = 0.3, max_tokens: int = 1200) -> str:
    if not settings.llm_enabled:
        raise LLMNotConfigured(
            "GROQ_API_KEY is not set. Add it to your .env to enable real briefs."
        )

    payload = {
        "model": settings.GROQ_MODEL,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=60) as client:
        resp = client.post(GROQ_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    return data["choices"][0]["message"]["content"].strip()
