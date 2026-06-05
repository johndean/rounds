"""
/v1/admin/email-debug — admin-only SMTP diagnostics (Phase 7).

Ports MIC `app/api/email_debug.py` (351 LOC) adapted to Rounds' raw-SQL
idiom + `CurrentUser`/`DbSession`. Replaces the theater EmailDebug UI:
real config check, real connectivity smoke test, real test sends, real
audit trail.

Endpoints:
  GET  /v1/admin/email-debug/config        — SMTP env-var presence (never
                                              leaks USERNAME/PASSWORD values)
  POST /v1/admin/email-debug/connectivity  — STARTTLS/LOGIN/NOOP/QUIT probe
                                              with per-step latency
  POST /v1/admin/email-debug/send          — admin-only test send to any
                                              address, captures raw SMTP wire
                                              into email_attempts.smtp_log
  GET  /v1/admin/email-debug/attempts      — paginated send-attempt log

Phase 7 of audit remediation. EmailBuilder + per-Type templates ship in a
follow-up alongside the SOP types port (the email_templates table FK'd to
sop_types in MIC).
"""
from __future__ import annotations

import logging
import os
import re
import smtplib
import sys
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.auth import CurrentUser
from app.db import DbSession
from app.security.roles import require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/admin/email-debug", tags=["email-debug"])


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _require_email_debug_admin(user) -> None:
    """Thin wrapper that adds the email-diagnostics-specific message
    while delegating the actual gate to app.security.roles.require_admin."""
    require_admin(user, message="Only admin can access email diagnostics")


class SendRequest(BaseModel):
    to: str = Field(..., min_length=3, max_length=255)
    subject: str = Field(default="Rounds Test Email", max_length=200)
    text_body: str = Field(default="This is a test.", max_length=8000)
    html_body: Optional[str] = Field(default=None, max_length=32000)


# ─── GET /config ────────────────────────────────────────────────────────
@router.get("/config")
async def get_config(_user: CurrentUser) -> dict:
    """Presence-only check on SMTP_* env vars. Returns the literal HOST/PORT/
    FROM values (non-secret) but only booleans for USERNAME/PASSWORD."""
    _require_email_debug_admin(_user)
    host = os.environ.get("SMTP_HOST") or ""
    port_raw = os.environ.get("SMTP_PORT") or ""
    frm = os.environ.get("SMTP_FROM") or ""
    return {
        "host":         {"present": bool(host),     "value": host or None},
        "port":         {"present": bool(port_raw), "value": port_raw or None},
        "from_address": {"present": bool(frm),      "value": frm or None},
        "username":     {"present": bool(os.environ.get("SMTP_USERNAME")), "value": None},
        "password":     {"present": bool(os.environ.get("SMTP_PASSWORD")), "value": None},
    }


# ─── POST /connectivity ─────────────────────────────────────────────────
@router.post("/connectivity")
async def test_connectivity(_user: CurrentUser) -> dict:
    """Connect → STARTTLS → LOGIN → NOOP → QUIT smoke test. No email is sent.
    Returns per-step {ok, latency_ms, error}; ok=null means skipped because a
    prior step failed."""
    _require_email_debug_admin(_user)

    host = os.environ.get("SMTP_HOST")
    if not host:
        raise HTTPException(status_code=400, detail="SMTP_HOST not configured")
    port = int(os.environ.get("SMTP_PORT", 587))
    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")

    result: dict[str, dict] = {
        "connect":  {"ok": None, "latency_ms": None, "error": None},
        "starttls": {"ok": None, "latency_ms": None, "error": None},
        "login":    {"ok": None, "latency_ms": None, "error": None},
        "noop":     {"ok": None, "latency_ms": None, "error": None},
        "quit":     {"ok": None, "latency_ms": None, "error": None},
    }

    server: Optional[smtplib.SMTP] = None
    try:
        t0 = time.time()
        server = smtplib.SMTP(host, port, timeout=10)
        result["connect"] = {"ok": True, "latency_ms": int((time.time() - t0) * 1000), "error": None}
    except Exception as e:  # noqa: BLE001
        result["connect"] = {"ok": False, "latency_ms": None, "error": f"{type(e).__name__}: {e}"}
        return result

    try:
        t0 = time.time()
        server.starttls()
        result["starttls"] = {"ok": True, "latency_ms": int((time.time() - t0) * 1000), "error": None}
    except Exception as e:  # noqa: BLE001
        result["starttls"] = {"ok": False, "latency_ms": None, "error": f"{type(e).__name__}: {e}"}
        try: server.quit()
        except Exception: pass
        return result

    if username and password:
        try:
            t0 = time.time()
            server.login(username, password)
            result["login"] = {"ok": True, "latency_ms": int((time.time() - t0) * 1000), "error": None}
        except Exception as e:  # noqa: BLE001
            result["login"] = {"ok": False, "latency_ms": None, "error": f"{type(e).__name__}: {e}"}
            try: server.quit()
            except Exception: pass
            return result
    else:
        result["login"] = {"ok": None, "latency_ms": None, "error": "skipped — no SMTP_USERNAME/PASSWORD set"}

    try:
        t0 = time.time()
        server.noop()
        result["noop"] = {"ok": True, "latency_ms": int((time.time() - t0) * 1000), "error": None}
    except Exception as e:  # noqa: BLE001
        result["noop"] = {"ok": False, "latency_ms": None, "error": f"{type(e).__name__}: {e}"}

    try:
        t0 = time.time()
        server.quit()
        result["quit"] = {"ok": True, "latency_ms": int((time.time() - t0) * 1000), "error": None}
    except Exception as e:  # noqa: BLE001
        result["quit"] = {"ok": False, "latency_ms": None, "error": f"{type(e).__name__}: {e}"}

    return result


# ─── helpers ────────────────────────────────────────────────────────────
def _send_with_wire_capture(
    host: str, port: int, username: Optional[str], password: Optional[str],
    from_email: str, to: str, subject: str, text_body: str, html_body: str,
) -> str:
    """Send via smtplib with debuglevel=1; capture raw wire chatter into a
    string so admins can see exactly what happened on the SMTP transport.
    """
    wire_buf: list[str] = []

    class _TeeStderr:
        def write(self, s: str) -> None:
            wire_buf.append(s)
        def flush(self) -> None:
            pass

    saved_stderr = sys.stderr
    sys.stderr = _TeeStderr()  # type: ignore[assignment]
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to
        msg.attach(MIMEText(text_body or "", "plain", "utf-8"))
        msg.attach(MIMEText(html_body or "", "html", "utf-8"))

        with smtplib.SMTP(host, port, timeout=10) as server:
            server.set_debuglevel(1)
            server.starttls()
            if username and password:
                server.login(username, password)
            server.sendmail(from_email, [to], msg.as_string())
    finally:
        sys.stderr = saved_stderr

    return "".join(wire_buf)


async def _record_attempt(
    db, *, from_address: str, to_address: str, subject: str, trigger: str,
    result: str, latency_ms: Optional[int] = None,
    error_message: Optional[str] = None, smtp_log: Optional[str] = None,
    operator_email: Optional[str] = None, sop_session_id: Optional[str] = None,
    stage: Optional[str] = None,
) -> None:
    """Append a row to email_attempts. Never raises."""
    try:
        await db.execute(
            text(
                """
                INSERT INTO email_attempts (
                    from_address, to_address, subject, trigger,
                    sop_session_id, stage, result, error_message,
                    latency_ms, smtp_log, operator_email
                ) VALUES (
                    :fa, :ta, :sj, :tr,
                    CAST(:sid AS uuid), :st, :res, :err,
                    :lat, :log, :op
                )
                """
            ),
            {
                "fa":  from_address,
                "ta":  to_address,
                "sj":  subject,
                "tr":  trigger,
                "sid": sop_session_id,
                "st":  stage,
                "res": result,
                "err": error_message,
                "lat": latency_ms,
                "log": smtp_log,
                "op":  operator_email,
            },
        )
        await db.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"email_attempts insert failed (non-fatal): {e}")


# ─── POST /send ─────────────────────────────────────────────────────────
@router.post("/send")
async def send_test(body: SendRequest, db: DbSession, _user: CurrentUser) -> dict:
    """Admin-only test send. Captures full SMTP wire protocol into
    email_attempts.smtp_log so the entire transport exchange is auditable.
    No rate limit — admin needs to iterate templates."""
    _require_email_debug_admin(_user)
    operator = (_user.email or "").strip().lower()

    to = (body.to or "").strip()
    if not _EMAIL_RE.match(to):
        raise HTTPException(status_code=400, detail="Invalid 'to' email address")

    subject = (body.subject or "").strip() or "Rounds Test Email"
    text_body = body.text_body or "This is a test."
    html_body = body.html_body if body.html_body else (
        f"<pre style='font-family:monospace;font-size:13px'>{text_body}</pre>"
    )

    host = os.environ.get("SMTP_HOST")
    if not host:
        raise HTTPException(status_code=400, detail="SMTP_HOST not configured")

    from_address = os.environ.get("SMTP_FROM", "rounds-noreply@vin.com")
    port = int(os.environ.get("SMTP_PORT", 587))
    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")

    logger.info(f"email-debug send: from={from_address} to={to} subject={subject!r} html={bool(body.html_body)}")
    t0 = time.time()
    wire_log = ""
    try:
        wire_log = _send_with_wire_capture(
            host, port, username, password, from_address, to, subject,
            text_body, html_body,
        )
    except Exception as e:  # noqa: BLE001
        latency_ms = int((time.time() - t0) * 1000)
        err_text = f"{type(e).__name__}: {e}"
        logger.warning(f"email-debug send FAILED to={to} after {latency_ms}ms: {err_text}")
        await _record_attempt(
            db, from_address=from_address, to_address=to, subject=subject,
            trigger="debug_test", result="failed",
            latency_ms=latency_ms, error_message=err_text,
            smtp_log=wire_log or None, operator_email=operator,
        )
        return {
            "sent":       False,
            "to":         to,
            "subject":    subject,
            "latency_ms": latency_ms,
            "error":      err_text,
            "smtp_log":   wire_log,
        }

    latency_ms = int((time.time() - t0) * 1000)
    logger.info(f"email-debug send OK to={to} in {latency_ms}ms")
    await _record_attempt(
        db, from_address=from_address, to_address=to, subject=subject,
        trigger="debug_test", result="sent",
        latency_ms=latency_ms, smtp_log=wire_log or None,
        operator_email=operator,
    )
    return {
        "sent":       True,
        "to":         to,
        "subject":    subject,
        "latency_ms": latency_ms,
        "error":      None,
        "smtp_log":   wire_log,
    }


# ─── GET /attempts ──────────────────────────────────────────────────────
@router.get("/attempts")
async def list_attempts(
    db: DbSession, _user: CurrentUser,
    limit: int = Query(50, ge=1, le=500),
    to: Optional[str] = Query(None, description="Recipient substring filter"),
    result: Optional[str] = Query(None, pattern="^(sent|failed)$"),
    since_hours: Optional[int] = Query(None, ge=1, le=720),
) -> list[dict]:
    """Paginated audit trail for the Recent Attempts panel. Newest first."""
    _require_email_debug_admin(_user)

    where = ["1=1"]
    params: dict[str, object] = {"lim": limit}
    if to:
        where.append("to_address ILIKE :to")
        params["to"] = f"%{to}%"
    if result:
        where.append("result = :res")
        params["res"] = result
    if since_hours:
        where.append("attempted_at >= now() - interval '" + str(int(since_hours)) + " hours'")

    sql = f"""
        SELECT id, attempted_at, from_address, to_address, subject, trigger,
               sop_session_id, stage, result, error_code, error_message,
               latency_ms, smtp_log, operator_email
          FROM email_attempts
         WHERE {' AND '.join(where)}
         ORDER BY attempted_at DESC
         LIMIT :lim
    """
    rows = (await db.execute(text(sql), params)).mappings().all()
    return [
        {
            "id":             str(r["id"]),
            "attempted_at":   r["attempted_at"].isoformat() if r["attempted_at"] else None,
            "from_address":   r["from_address"],
            "to_address":     r["to_address"],
            "subject":        r["subject"],
            "trigger":        r["trigger"],
            "sop_session_id": str(r["sop_session_id"]) if r["sop_session_id"] else None,
            "stage":          r["stage"],
            "result":         r["result"],
            "error_code":     r["error_code"],
            "error_message":  r["error_message"],
            "latency_ms":     r["latency_ms"],
            "smtp_log":       r["smtp_log"],
            "operator_email": r["operator_email"],
        }
        for r in rows
    ]
