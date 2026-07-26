"""Small config loader. Reads a local .env (if present) into os.environ,
then exposes typed settings. No external dependency required."""

from __future__ import annotations

import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env parser so we don't need python-dotenv."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Don't clobber real environment variables.
        os.environ.setdefault(key, value)


_load_dotenv(_ROOT / ".env")


class Settings:
    GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "").strip()
    GROQ_MODEL: str = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile").strip()

    RESEND_API_KEY: str = os.environ.get("RESEND_API_KEY", "").strip()
    EMAIL_FROM: str = os.environ.get("EMAIL_FROM", "Cadence <onboarding@resend.dev>").strip()

    DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite:///./cadence.db").strip()
    DEFAULT_TIMEZONE: str = os.environ.get("DEFAULT_TIMEZONE", "Asia/Kolkata").strip()

    @property
    def llm_enabled(self) -> bool:
        return bool(self.GROQ_API_KEY)

    @property
    def email_enabled(self) -> bool:
        return bool(self.RESEND_API_KEY)


settings = Settings()
