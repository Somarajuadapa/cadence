"""Database models and session handling (SQLAlchemy 2.0)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}
    if settings.DATABASE_URL.startswith("sqlite")
    else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# Frequency options exposed in the UI and understood by the scheduler.
FREQUENCIES = {
    "daily": "Every day",
    "every_2_days": "Every 2 days",
    "every_3_days": "Every 3 days",
    "weekly": "Every week",
}


class Brief(Base):
    __tablename__ = "briefs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(120), default="")
    query: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(String(255))
    frequency: Mapped[str] = mapped_column(String(32), default="daily")
    time_of_day: Mapped[str] = mapped_column(String(5), default="08:00")  # "HH:MM"
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    # Only used for weekly (0=Mon .. 6=Sun); NULL otherwise.
    day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(255), nullable=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_session():
    return SessionLocal()
