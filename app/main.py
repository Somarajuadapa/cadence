"""FastAPI application: the tiny UI plus create/preview/toggle/delete routes."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from . import scheduler
from .agent import build_brief
from .config import settings
from .db import FREQUENCIES, Brief, get_session, init_db

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Cadence", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    session = get_session()
    try:
        briefs = session.query(Brief).order_by(Brief.created_at.desc()).all()
    finally:
        session.close()
    return TEMPLATES.TemplateResponse(
        request,
        "index.html",
        {
            "briefs": briefs,
            "frequencies": FREQUENCIES,
            "default_tz": settings.DEFAULT_TIMEZONE,
            "llm_enabled": settings.llm_enabled,
            "email_enabled": settings.email_enabled,
        },
    )


@app.post("/briefs")
def create_brief(
    query: str = Form(...),
    email: str = Form(...),
    frequency: str = Form("daily"),
    time_of_day: str = Form("08:00"),
    timezone: str = Form("Asia/Kolkata"),
    label: str = Form(""),
    day_of_week: str = Form(""),
):
    session = get_session()
    try:
        brief = Brief(
            label=label.strip(),
            query=query.strip(),
            email=email.strip(),
            frequency=frequency if frequency in FREQUENCIES else "daily",
            time_of_day=time_of_day or "08:00",
            timezone=timezone or settings.DEFAULT_TIMEZONE,
            day_of_week=int(day_of_week) if day_of_week.isdigit() else None,
            active=True,
        )
        session.add(brief)
        session.commit()
        scheduler.register_brief(brief)
    finally:
        session.close()
    return RedirectResponse("/", status_code=303)


@app.post("/api/preview")
def preview(query: str = Form(...), timezone: str = Form("UTC"), label: str = Form("")):
    """Generate a sample brief immediately without saving or emailing."""
    result = build_brief(query.strip(), tz=timezone or "UTC", label=label)
    return JSONResponse(
        {
            "subject": result.subject,
            "html": result.html,
            "used_llm": result.used_llm,
            "used_search": result.used_search,
            "note": result.note,
        }
    )


@app.post("/briefs/{brief_id}/toggle")
def toggle_brief(brief_id: int):
    session = get_session()
    try:
        brief = session.get(Brief, brief_id)
        if brief:
            brief.active = not brief.active
            session.commit()
            if brief.active:
                scheduler.register_brief(brief)
            else:
                scheduler.unregister_brief(brief.id)
    finally:
        session.close()
    return RedirectResponse("/", status_code=303)


@app.post("/briefs/{brief_id}/delete")
def delete_brief(brief_id: int):
    session = get_session()
    try:
        brief = session.get(Brief, brief_id)
        if brief:
            scheduler.unregister_brief(brief.id)
            session.delete(brief)
            session.commit()
    finally:
        session.close()
    return RedirectResponse("/", status_code=303)


@app.get("/health")
def health():
    return {"status": "ok", "llm": settings.llm_enabled, "email": settings.email_enabled}
