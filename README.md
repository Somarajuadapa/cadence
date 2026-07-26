# 🗓️ Cadence

**Ask for any information once. Get it researched and emailed to you on a schedule.**

Cadence is a tiny web app with a single question: *what information do you need?*
You add an email, a frequency, and a time — and Cadence researches the topic on
the live web, writes a concise brief with an open-weight LLM, and delivers it on
your cadence.

> **Example.** *"A summary of how the Nifty 50 performed yesterday — where it
> opened, closed, key moves, and the market news driving it."* → delivered to
> your inbox every weekday at **08:00 IST**, an hour or two before the market opens.

---

## How it works

```
 Browser (one small form)
        │
        ▼
 FastAPI backend ──► SQLite (stores your briefs)
        │
        ▼
 APScheduler  ── fires each brief at its scheduled time ──►  Research agent
                                                              │
                        DuckDuckGo web search ◄───────────────┤
                        Llama 3.3 70B (Groq) writes the brief ─┤
                        Resend emails it to you ◄──────────────┘
```

| Concern     | Choice                                   | Swappable? |
|-------------|------------------------------------------|------------|
| LLM         | **Llama 3.3 70B** (open weights) via Groq | `app/llm.py` |
| Web search  | **DuckDuckGo** (no API key)               | `app/search.py` |
| Email       | **Resend**                                | `app/email_sender.py` |
| Scheduling  | **APScheduler**                           | `app/scheduler.py` |
| Storage     | **SQLite** via SQLAlchemy                 | `app/db.py` |
| UI          | Server-rendered HTML + Tailwind           | `app/templates/index.html` |

Every external service sits behind a thin adapter, so you can move to Ollama,
Tavily, SMTP, Postgres, etc. without touching the rest of the app.

---

## Quick start

```bash
cd cadence
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # then add your keys (optional to start)
python run.py             # → http://localhost:8000
```

Open <http://localhost:8000>, type a request, and click **Preview now** to see a
sample brief immediately — or **Schedule this brief** to have it delivered on a
cadence.

### Runs with zero keys

Cadence works out of the box in **preview mode**:

- **No `GROQ_API_KEY`** → it still searches the web and shows you the source
  results (it just won't write the narrative summary).
- **No `RESEND_API_KEY`** → scheduled briefs are logged to the console instead of
  emailed.

Add keys when you're ready:

- **Groq** (free): <https://console.groq.com/keys>
- **Resend** (free tier): <https://resend.com/api-keys>

---

## The form — five small fields

1. **What information do you need?** — the free-text request (the one `?`).
2. **Deliver to** — the destination email.
3. **How often** — daily · every 2 days · every 3 days · weekly.
4. **At what time** (+ **timezone**) — e.g. 08:00 `Asia/Kolkata`.
5. **Label** *(optional)* — a name like "Nifty pre-market".

Plus **Preview now** to test a request instantly, and per-brief **Pause / Resume /
Delete**.

---

## Deploy (always-on)

The scheduler runs **in-process**, so briefs only fire while the app is running.
For real delivery, run it somewhere always-on. SQLite is kept on a persistent
volume so your briefs survive restarts and redeploys.

### Docker (any host, or locally)

```bash
docker compose up -d        # reads keys from your local .env
# → http://localhost:8000 , restarts automatically, DB persisted in a volume
```

### Fly.io

```bash
fly launch --copy-config --now
fly secrets set GROQ_API_KEY=... RESEND_API_KEY=...   # never commit these
fly volumes create cadence_data --size 1              # persistent SQLite
fly deploy
```

`fly.toml` keeps one machine always running (`min_machines_running = 1`,
`auto_stop_machines = false`) so scheduled briefs never miss.

### Railway

1. New Project → **Deploy from GitHub repo** (picks up `railway.json` → builds the Dockerfile).
2. **Variables**: add `GROQ_API_KEY` and `RESEND_API_KEY`.
3. **Add a Volume** mounted at `/data` (matches `DATABASE_URL=sqlite:////data/cadence.db`).
4. Deploy — Railway injects `$PORT` automatically.

> Keys are always set as host **secrets/variables**, never committed. `.env` is
> gitignored and only used for local runs.

## Testing delivery

Each scheduled brief has a **Send now** button — it generates and emails that
brief immediately, then shows the result (`Sent`, or why it was skipped). Use it
to confirm your Resend key works without waiting for the schedule.

## Project layout

```
cadence/
├── run.py                  # start the server
├── requirements.txt
├── .env.example
└── app/
    ├── main.py             # FastAPI routes + lifespan
    ├── config.py           # env/settings loader
    ├── db.py               # SQLAlchemy models
    ├── agent.py            # search → LLM → brief pipeline
    ├── llm.py              # Groq (open-weight Llama) client
    ├── search.py           # DuckDuckGo search
    ├── email_sender.py     # Resend delivery (+ console fallback)
    ├── scheduler.py        # APScheduler job wiring
    └── templates/
        └── index.html      # the whole UI
```

---

## Notes & next steps

- The scheduler runs **in-process**. For production, run it under a process
  manager (systemd, Docker, Railway, Fly.io) so it stays alive; jobs rebuild from
  the database on startup.
- Ideas: per-brief "send me a test now" button, richer source-fetching (read the
  full article text, not just snippets), Slack/Telegram delivery, and a
  "verify email" step before scheduling.

## License

MIT
