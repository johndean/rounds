-- 030_email_attempts — audit trail for every email send attempt.
--
-- Ports MIC `migrations/020_email_attempts.sql` verbatim (renumbered to
-- fit Rounds' migration sequence). Persists every send (stage-notify,
-- debug-test, template-test) so admins can resolve "I wasn't notified
-- about X" complaints with: timestamp + recipient + result + error +
-- latency + optional raw SMTP wire log.
--
-- Phase 7 of audit remediation. The `email_templates` table from MIC's
-- 018 migration is intentionally deferred — it references sop_types
-- which Rounds doesn't have yet; ships in a follow-up alongside the
-- SOP types port.
--
-- Idempotent: every guard is IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS email_attempts (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    attempted_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    from_address   TEXT        NOT NULL,
    to_address     TEXT        NOT NULL,
    subject        TEXT,
    trigger        TEXT        NOT NULL,
    sop_session_id UUID        REFERENCES sessions(id) ON DELETE SET NULL,
    stage          TEXT,
    result         TEXT        NOT NULL,
    error_code     TEXT,
    error_message  TEXT,
    latency_ms     INTEGER,
    smtp_log       TEXT,
    operator_email TEXT,
    CONSTRAINT chk_email_attempts_result  CHECK (result IN ('sent', 'failed')),
    CONSTRAINT chk_email_attempts_trigger CHECK (trigger IN ('stage_notification', 'debug_test', 'template_test'))
);

CREATE INDEX IF NOT EXISTS email_attempts_attempted_at_idx ON email_attempts (attempted_at DESC);
CREATE INDEX IF NOT EXISTS email_attempts_to_address_idx   ON email_attempts (to_address);
CREATE INDEX IF NOT EXISTS email_attempts_session_idx      ON email_attempts (sop_session_id);
CREATE INDEX IF NOT EXISTS email_attempts_result_idx       ON email_attempts (result);
