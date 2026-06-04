"""
Lightweight SMTP send helper.

Reusable across tasks + routes that need to dispatch a single email. Mirrors
the env-var pattern used by app/api/email_debug.py's diagnostic endpoints
(SMTP_HOST / SMTP_PORT / SMTP_FROM / SMTP_USERNAME / SMTP_PASSWORD) so a
single SMTP configuration covers the whole app — no separate settings for
operational vs diagnostic mail.

Sync helper, safe to call from Celery tasks. Returns a result dict; never
raises. Callers decide how to log the outcome (audit_events row, log line,
toast, etc).
"""
from __future__ import annotations

import logging
import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, TypedDict

logger = logging.getLogger(__name__)


class EmailResult(TypedDict):
    ok:         bool
    error:      Optional[str]
    latency_ms: int


def send_smtp_email(
    to: str,
    subject: str,
    text_body: str,
    html_body: Optional[str] = None,
    *,
    from_email: Optional[str] = None,
) -> EmailResult:
    """
    Send a single email via SMTP_* env vars. Never raises.

    Returns {ok, error, latency_ms}. `ok=False` cases include: missing
    SMTP_HOST, malformed `to`, smtplib connection/auth errors, or DNS
    timeout. Caller is expected to log/audit the result.

    `from_email` defaults to env SMTP_FROM, then to a sentinel that will
    cause most SMTP servers to reject — set SMTP_FROM in production.
    """
    started = time.monotonic()
    host = os.environ.get("SMTP_HOST")
    if not host:
        return {"ok": False, "error": "SMTP_HOST not configured", "latency_ms": 0}

    if not to or "@" not in to:
        return {"ok": False, "error": f"invalid recipient: {to!r}", "latency_ms": 0}

    port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")
    sender = from_email or os.environ.get("SMTP_FROM") or "rounds-noreply@vin.com"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.attach(MIMEText(text_body or "", "plain", "utf-8"))
    if html_body:
        msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            if username and password:
                server.login(username, password)
            server.sendmail(sender, [to], msg.as_string())
    except Exception as exc:  # noqa: BLE001
        elapsed = int((time.monotonic() - started) * 1000)
        logger.warning(f"send_smtp_email failed: to={to} subject={subject!r}: {exc}")
        return {"ok": False, "error": str(exc)[:500], "latency_ms": elapsed}

    elapsed = int((time.monotonic() - started) * 1000)
    return {"ok": True, "error": None, "latency_ms": elapsed}
