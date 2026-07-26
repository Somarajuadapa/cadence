"""Send any briefs that are due right now.

Run by the GitHub Actions cron (.github/workflows/briefs.yml), but also runnable
locally:  `python send_due_briefs.py`.

Source of truth for briefs is `briefs.yaml`. A small state file
(`.cadence_state.json`) records the date each brief was last sent, so we never
double-send and can honour "every N days" cadences without an always-on server.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from app.agent import build_brief
from app.config import settings
from app.email_sender import send_email

ROOT = Path(__file__).resolve().parent
BRIEFS_FILE = ROOT / "briefs.yaml"
STATE_FILE = ROOT / ".cadence_state.json"

# Minimum days between sends for each cadence.
MIN_INTERVAL_DAYS = {"daily": 1, "every_2_days": 2, "every_3_days": 3, "weekly": 7}


def load_briefs() -> list[dict]:
    if not BRIEFS_FILE.exists():
        return []
    data = yaml.safe_load(BRIEFS_FILE.read_text()) or {}
    return data.get("briefs", []) or []


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def brief_key(b: dict, i: int) -> str:
    return str(b.get("id") or b.get("label") or i)


def resolve_email(raw: str) -> str:
    """Allow `env:NAME` to pull the recipient from an environment variable/secret."""
    raw = (raw or "").strip()
    if raw.startswith("env:"):
        return os.environ.get(raw[4:], "").strip()
    return raw


def is_due(b: dict, now: datetime, last_sent: date | None) -> bool:
    freq = b.get("frequency", "daily")
    hh, mm = (int(x) for x in str(b.get("time_of_day", "08:00")).split(":"))
    scheduled = now.replace(hour=hh, minute=mm, second=0, microsecond=0)

    if now < scheduled:
        return False  # not yet time today
    if last_sent == now.date():
        return False  # already sent today

    if freq == "weekly":
        return now.weekday() == int(b.get("day_of_week", 0) or 0)

    if last_sent is None:
        return True
    return (now.date() - last_sent).days >= MIN_INTERVAL_DAYS.get(freq, 1)


def main() -> None:
    briefs = load_briefs()
    state = load_state()

    if not settings.llm_enabled:
        print("WARNING: GROQ_API_KEY not set — briefs would be preview-only.")
    if not settings.email_enabled:
        print("ERROR: RESEND_API_KEY not set — cannot send email. Aborting.")
        return

    sent_any = False
    for i, b in enumerate(briefs):
        key = brief_key(b, i)
        tz = b.get("timezone", "UTC")
        try:
            now = datetime.now(ZoneInfo(tz))
        except Exception:
            now = datetime.now(ZoneInfo("UTC"))

        last_raw = state.get(key)
        last_sent = date.fromisoformat(last_raw) if last_raw else None

        if not is_due(b, now, last_sent):
            print(f"- {key}: not due ({now:%Y-%m-%d %H:%M %Z})")
            continue

        to = resolve_email(b.get("email", ""))
        if not to:
            print(f"! {key}: no recipient resolved (check email / RECIPIENT_EMAIL) — skipping")
            continue

        print(f"→ {key}: due — researching and sending to {to}")
        try:
            result = build_brief(b["query"], tz=tz, label=b.get("label", ""))
            ok, status = send_email(to, result.subject, result.html, result.text)
            print(f"   {status}")
            if ok:
                state[key] = now.date().isoformat()
                sent_any = True
        except Exception as e:
            print(f"   ERROR: {e}")

    save_state(state)
    print("Done." + (" Sent at least one brief." if sent_any else " Nothing to send right now."))


if __name__ == "__main__":
    main()
