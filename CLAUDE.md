# CLAUDE.md — project guide for Cadence

This file orients any Claude Code session working on this repo. Read it first.

## What this project is

**Cadence** lets you request any information once — *what* you want, *which email*,
*how often*, and *what time* — and it researches the topic on the live web, writes
a concise brief with an open-weight LLM, and emails it on a schedule. The flagship
use case is a daily pre-market **Nifty 50** brief delivered at 08:00 IST.

## Architecture (how the pieces connect)

```
Local web UI (optional)         GitHub Actions cron (production delivery)
  app/main.py  ── FastAPI            .github/workflows/briefs.yml (runs every 30m)
  app/templates/index.html               │
  APScheduler (in-process)               ▼
        │                          send_due_briefs.py
        ▼                                 │
   the same pipeline: ── app/agent.py ────┤
        DuckDuckGo (app/search.py)  →  finds web results
        Groq / Llama 3.3 (app/llm.py) →  writes the brief
        Resend (app/email_sender.py)  →  emails it
```

Two independent ways to run the exact same brief pipeline:

1. **Local app** (`python run.py` → http://localhost:8000): a single-page UI to
   create/preview/pause/delete briefs. Uses SQLite (`app/db.py`) + APScheduler
   (`app/scheduler.py`). Good for previewing topics. Only sends while running.
2. **GitHub Actions cron** (production): free, always-on. `send_due_briefs.py`
   reads `briefs.yaml`, sends whatever is due, and records `.cadence_state.json`
   to avoid duplicate sends. This is what actually delivers the daily email.

## Key files

| File | Role |
|------|------|
| `briefs.yaml` | **Source of truth** for scheduled briefs (topic, email, frequency, time, tz). |
| `send_due_briefs.py` | Cron entrypoint. Two modes: *deliver due* (scheduled) and *configure+send* (manual form run). |
| `.github/workflows/briefs.yml` | Cron schedule + the "Run workflow" input form. |
| `app/agent.py` | The pipeline: search → LLM → formatted HTML brief. |
| `app/llm.py` | Groq (OpenAI-compatible) client. Swap here for Ollama/OpenRouter. |
| `app/search.py` | DuckDuckGo search. Swap here for Tavily/Brave. |
| `app/email_sender.py` | Resend delivery (console fallback if no key). Swap here for SMTP. |
| `app/main.py` | FastAPI routes + the local web UI. |
| `.env.example` | Template for local keys (real `.env` is gitignored). |

## Secrets / config

Never commit keys. They live in two places:
- **Local**: `.env` (gitignored) — used by `python run.py` and local scripts.
- **GitHub Actions**: repo secrets `GROQ_API_KEY`, `RESEND_API_KEY`,
  `RECIPIENT_EMAIL` (Settings → Secrets → Actions). `EMAIL_FROM` is optional.

Notes:
- `briefs.yaml` uses `email: "env:RECIPIENT_EMAIL"` so the address stays private
  in this public repo. A literal address there would be publicly visible.
- Resend free tier only sends to the account owner's own address until a domain
  is verified. To email other recipients, verify a domain and set `EMAIL_FROM`.

## Stack

FastAPI · SQLAlchemy + SQLite · APScheduler · httpx · PyYAML · Jinja2 + Tailwind
(CDN). LLM = Groq `llama-3.3-70b-versatile`. Python 3.12.

## Common tasks

- **Run locally**: `python -m venv .venv && source .venv/bin/activate &&
  pip install -r requirements.txt && cp .env.example .env` (add keys) `&& python run.py`
- **Change the scheduled brief**: edit `briefs.yaml`, or use the workflow's
  "Run workflow" form (Actions tab), which rewrites `briefs.yaml` and emails a copy.
- **Add multiple recurring briefs**: add more entries under `briefs:` in `briefs.yaml`
  (each needs a unique `id`). The form manages a single brief only.
- **Deploy the always-on web UI instead** (optional): `Dockerfile`, `docker-compose.yml`,
  `fly.toml`, `railway.json` are provided.

## Conventions

- Keep each external service behind its thin adapter module (llm/search/email) so
  providers stay swappable.
- Frequencies supported: `daily`, `every_2_days`, `every_3_days`, `weekly`
  (weekly uses `day_of_week`, 0=Mon..6=Sun). See `MIN_INTERVAL_DAYS` in
  `send_due_briefs.py` and `_trigger_for` in `app/scheduler.py`.
