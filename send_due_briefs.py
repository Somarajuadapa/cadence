"""Cadence delivery script — runs in GitHub Actions.

Two modes, chosen automatically:

1. **Configure mode** (manual "Run workflow" with form inputs) — build a brief
   from the form, save it to `briefs.yaml`, and email a copy immediately so you
   see it right away. From then on the cron delivers it on your schedule.

2. **Deliver mode** (the scheduled cron, no inputs) — read `briefs.yaml` and send
   any briefs that are due now, de-duplicated via `.cadence_state.json`.

Also runnable locally: `python send_due_briefs.py`.
"""

from __future__ import annotations

import json
import os
import re
import time
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

MIN_INTERVAL_DAYS = {"daily": 1, "every_2_days": 2, "every_3_days": 3, "weekly": 7}
VALID_FREQ = set(MIN_INTERVAL_DAYS)

BRIEFS_HEADER = (
    "# Cadence briefs. You can edit this file directly, or set it via the\n"
    '# "Send Cadence briefs" workflow form (Actions tab -> Run workflow).\n'
    "# frequency: daily | every_2_days | every_3_days | weekly\n"
)


# ── shared helpers ────────────────────────────────────────────────────────
def load_briefs() -> list[dict]:
    if not BRIEFS_FILE.exists():
        return []
    data = yaml.safe_load(BRIEFS_FILE.read_text()) or {}
    return data.get("briefs", []) or []


def write_briefs(briefs: list[dict]) -> None:
    body = yaml.safe_dump({"briefs": briefs}, sort_keys=False, allow_unicode=True)
    BRIEFS_FILE.write_text(BRIEFS_HEADER + "\n" + body)


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
    """`env:NAME` pulls the recipient from an environment variable/secret."""
    raw = (raw or "").strip()
    if raw.startswith("env:"):
        return os.environ.get(raw[4:], "").strip()
    return raw


def _now(tz: str) -> datetime:
    try:
        return datetime.now(ZoneInfo(tz))
    except Exception:
        return datetime.now(ZoneInfo("UTC"))


# ── configure mode (form inputs) ──────────────────────────────────────────
def configure_from_inputs() -> None:
    query = os.environ.get("BRIEF_QUERY", "").strip()
    email_in = os.environ.get("BRIEF_EMAIL", "").strip()
    frequency = os.environ.get("BRIEF_FREQUENCY", "daily").strip() or "daily"
    time_of_day = os.environ.get("BRIEF_TIME", "08:00").strip() or "08:00"
    timezone = os.environ.get("BRIEF_TZ", "Asia/Kolkata").strip() or "Asia/Kolkata"
    dow = os.environ.get("BRIEF_DOW", "0").strip() or "0"

    if frequency not in VALID_FREQ:
        frequency = "daily"

    # Blank email => use the private RECIPIENT_EMAIL secret (kept out of the repo).
    email_field = email_in if email_in else "env:RECIPIENT_EMAIL"

    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")[:30] or "brief"
    brief = {
        "id": f"{slug}-{int(time.time()) % 100000}",
        "label": query[:60],
        "query": query,
        "email": email_field,
        "frequency": frequency,
        "time_of_day": time_of_day,
        "timezone": timezone,
    }
    if frequency == "weekly":
        brief["day_of_week"] = int(dow) if dow.isdigit() else 0

    # This form defines your brief — replace the file with it.
    write_briefs([brief])
    print(f"Saved brief '{brief['id']}' to briefs.yaml "
          f"({frequency} at {time_of_day} {timezone}).")

    if not settings.email_enabled:
        print("ERROR: RESEND_API_KEY not set — saved the brief but can't email it.")
        return

    to = resolve_email(email_field)
    if not to:
        print("! Saved, but no recipient resolved. Fill the email field, or add a "
              "RECIPIENT_EMAIL secret.")
        return

    print(f"→ Sending a first copy now to {to} …")
    result = build_brief(query, tz=timezone, label=brief["label"])
    ok, status = send_email(to, result.subject, result.html, result.text)
    print(f"   {status}")

    # Mark as sent today so the scheduled run doesn't send a duplicate.
    if ok:
        state = load_state()
        state[brief["id"]] = _now(timezone).date().isoformat()
        save_state(state)


# ── deliver mode (scheduled cron) ─────────────────────────────────────────
def is_due(b: dict, now: datetime, last_sent: date | None) -> bool:
    freq = b.get("frequency", "daily")
    hh, mm = (int(x) for x in str(b.get("time_of_day", "08:00")).split(":"))
    scheduled = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if now < scheduled:
        return False
    if last_sent == now.date():
        return False
    if freq == "weekly":
        return now.weekday() == int(b.get("day_of_week", 0) or 0)
    if last_sent is None:
        return True
    return (now.date() - last_sent).days >= MIN_INTERVAL_DAYS.get(freq, 1)


def deliver_due() -> None:
    if not settings.email_enabled:
        print("ERROR: RESEND_API_KEY not set — cannot send email. Aborting.")
        return

    briefs = load_briefs()
    state = load_state()
    sent_any = False

    for i, b in enumerate(briefs):
        key = brief_key(b, i)
        tz = b.get("timezone", "UTC")
        now = _now(tz)
        last_raw = state.get(key)
        last_sent = date.fromisoformat(last_raw) if last_raw else None

        if not is_due(b, now, last_sent):
            print(f"- {key}: not due ({now:%Y-%m-%d %H:%M %Z})")
            continue

        to = resolve_email(b.get("email", ""))
        if not to:
            print(f"! {key}: no recipient resolved — skipping")
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
    print("Done." + (" Sent at least one brief." if sent_any else " Nothing due right now."))


def main() -> None:
    if not settings.llm_enabled:
        print("WARNING: GROQ_API_KEY not set — briefs would be preview-only.")
    if os.environ.get("BRIEF_QUERY", "").strip():
        configure_from_inputs()
    else:
        deliver_due()


if __name__ == "__main__":
    main()
