"""Email delivery via Resend, with a console fallback when no key is set."""

from __future__ import annotations

import logging

import httpx

from .config import settings

log = logging.getLogger("cadence.email")

RESEND_URL = "https://api.resend.com/emails"


def send_email(to: str, subject: str, html: str, text: str = "") -> tuple[bool, str]:
    """Send an email. Returns (sent, status_message)."""
    if not settings.email_enabled:
        log.info("Email not configured — would have sent to %s: %s", to, subject)
        print(f"\n[cadence] (no RESEND_API_KEY) would email {to}: {subject}\n")
        return False, "Email skipped (no RESEND_API_KEY configured)"

    payload = {
        "from": settings.EMAIL_FROM,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text

    headers = {
        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(RESEND_URL, json=payload, headers=headers)
            resp.raise_for_status()
        return True, "Sent"
    except httpx.HTTPStatusError as e:
        detail = e.response.text[:200]
        log.error("Resend error %s: %s", e.response.status_code, detail)
        return False, f"Email failed ({e.response.status_code}): {detail}"
    except Exception as e:  # pragma: no cover
        log.error("Email send failed: %s", e)
        return False, f"Email failed: {e}"
