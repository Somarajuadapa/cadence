"""APScheduler wiring: register one job per active brief, run the agent,
send the email, and record the outcome."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from . import agent
from .db import Brief, get_session
from .email_sender import send_email

log = logging.getLogger("cadence.scheduler")

scheduler = BackgroundScheduler()

_INTERVAL_DAYS = {"every_2_days": 2, "every_3_days": 3}


def _next_time(time_of_day: str, tz: str) -> datetime:
    """Next occurrence of HH:MM in the given timezone (today or tomorrow)."""
    hour, minute = (int(x) for x in time_of_day.split(":"))
    zone = ZoneInfo(tz)
    now = datetime.now(zone)
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def _trigger_for(brief: Brief):
    hour, minute = (int(x) for x in brief.time_of_day.split(":"))
    tz = brief.timezone

    if brief.frequency == "daily":
        return CronTrigger(hour=hour, minute=minute, timezone=tz)

    if brief.frequency == "weekly":
        dow = brief.day_of_week if brief.day_of_week is not None else 0
        return CronTrigger(day_of_week=dow, hour=hour, minute=minute, timezone=tz)

    days = _INTERVAL_DAYS.get(brief.frequency, 1)
    return IntervalTrigger(days=days, start_date=_next_time(brief.time_of_day, tz))


def run_brief(brief_id: int) -> None:
    """Job body: generate and deliver one brief."""
    session = get_session()
    try:
        brief = session.get(Brief, brief_id)
        if not brief or not brief.active:
            return
        log.info("Running brief #%s for %s", brief.id, brief.email)
        try:
            result = agent.build_brief(brief.query, tz=brief.timezone, label=brief.label)
            sent, status = send_email(brief.email, result.subject, result.html, result.text)
            brief.last_status = status
        except Exception as e:  # pragma: no cover
            log.exception("Brief #%s failed", brief.id)
            brief.last_status = f"Error: {e}"
        brief.last_run_at = datetime.utcnow()
        session.commit()
    finally:
        session.close()


def register_brief(brief: Brief) -> None:
    job_id = f"brief-{brief.id}"
    scheduler.add_job(
        run_brief,
        trigger=_trigger_for(brief),
        args=[brief.id],
        id=job_id,
        replace_existing=True,
        misfire_grace_time=3600,
    )
    log.info("Scheduled %s (%s at %s %s)", job_id, brief.frequency,
             brief.time_of_day, brief.timezone)


def unregister_brief(brief_id: int) -> None:
    job_id = f"brief-{brief_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


def sync_from_db() -> None:
    """Rebuild all jobs from the database (called on startup)."""
    session = get_session()
    try:
        for brief in session.query(Brief).filter(Brief.active.is_(True)).all():
            register_brief(brief)
    finally:
        session.close()


def start() -> None:
    if not scheduler.running:
        scheduler.start()
    sync_from_db()


def shutdown() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
