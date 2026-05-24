-- 048_email_templates — per-Type x per-Stage stage-notification HTML email
-- templates with locale support.
--
-- Phase 5 of the 2026-05-23 Settings BUILD remediation plan. Replaces the
-- ~300-line EmailBuilder.vue editor that previously warn-toasted every save
-- (frontend/src/components/settings/EmailBuilder.vue:63-73).
--
-- One active template per (session_type_id, stage_id, locale). A NULL
-- session_type_id row is the "default for all types" fallback. The
-- resolver returns the per-type row if present, otherwise the default.
--
-- This migration ONLY ships the table + 8 default rows (one per SOP
-- stage). Stage-transition triggers that actually fire emails on
-- sop_state.stage advance are explicitly out of scope - that's a
-- separate Celery hook in app/tasks/* that requires its own plan.
--
-- Idempotent (every CREATE uses IF NOT EXISTS), additive, reversible.

CREATE TABLE IF NOT EXISTS email_templates (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    session_type_id UUID         REFERENCES session_types(id) ON DELETE CASCADE,   -- NULL = applies to every Type
    stage_id        TEXT         NOT NULL,                                          -- 'prep' | 'copy_draft' | 'medical' | ... | 'complete'
    locale          TEXT         NOT NULL DEFAULT 'en-US',
    subject         TEXT         NOT NULL,
    body            TEXT         NOT NULL,                                          -- HTML
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_by      TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- One active template per (type, stage, locale). NULL type_id collapses to
-- the literal '_default_' string so partial-unique-on-NULL works
-- deterministically (Postgres treats NULL as distinct in unique indexes
-- without this trick, which would let multiple defaults coexist).
CREATE UNIQUE INDEX IF NOT EXISTS email_templates_type_stage_locale_uq
    ON email_templates (COALESCE(session_type_id::text, '_default_'), stage_id, locale)
    WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS email_templates_stage_active_idx
    ON email_templates (stage_id) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS email_templates_type_active_idx
    ON email_templates (session_type_id) WHERE is_active = TRUE AND session_type_id IS NOT NULL;

-- ─── Seed: 8 default-Type templates, one per SOP stage ────────────────────
-- These are the verbatim DEFAULTS dict from EmailBuilder.vue:27-34. With
-- session_type_id = NULL, they apply to every Type until an operator
-- overrides them with a per-Type row.

INSERT INTO email_templates (session_type_id, stage_id, locale, subject, body)
VALUES
    (NULL, 'prep',       'en-US',
     '[VIN] Ready for prep — {{ session_code }}',
     E'<!DOCTYPE html>\n<html><body style="margin:0;padding:0;background:#F7F7F7;font-family:''ProximaNova'',Helvetica,Arial,sans-serif;color:#002855;">\n  <table cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:640px;margin:0 auto;background:#FFFFFF;">\n    <tr><td style="background:#002855;padding:20px 28px;color:#FFFFFF;">\n      <div style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#B1C9E8;">VIN Transcript Software</div>\n      <div style="font-size:18px;font-weight:800;margin-top:4px;">Ready for prep · {{ session_code }}</div>\n    </td></tr>\n    <tr><td style="padding:24px 28px;font-size:14px;line-height:1.6;color:#002855;">\n      <p>Hi {{ assignee_first_name }},</p>\n      <p>A new session has been uploaded and is ready for your prep review. Open the session and verify the extras and confirm everything needed is present.</p>\n      <p><a href="{{ results_url }}" style="display:inline-block;background:#002855;color:#FFFFFF;padding:11px 22px;border-radius:8px;font-weight:600;text-decoration:none;">Open session →</a></p>\n    </td></tr>\n  </table>\n</body></html>'),
    (NULL, 'copy_draft', 'en-US',
     '[VIN] Ready to copy edit — {{ session_code }}',
     '<html><body style="font-family:''ProximaNova'',sans-serif;background:#F7F7F7;margin:0;"><div style="max-width:640px;margin:0 auto;background:#FFFFFF;"><div style="background:#002855;color:#FFFFFF;padding:20px 28px;"><div style="font-size:18px;font-weight:800;">Ready to copy edit · {{ session_code }}</div></div><div style="padding:24px 28px;font-size:14px;color:#002855;"><p>Hi {{ assignee_first_name }},</p><p>{{ prior_actor_full_name }} has finished prep on {{ session_code }}. It is ready for your draft copy edit in the AI editor.</p><p><a href="{{ editor_url }}" style="display:inline-block;background:#002855;color:#FFFFFF;padding:11px 22px;border-radius:8px;font-weight:600;text-decoration:none;">Open editor →</a></p></div></div></body></html>'),
    (NULL, 'medical',    'en-US',
     '[VIN] Medical review requested — {{ session_code }}',
     '<html><body style="font-family:''ProximaNova'',sans-serif;background:#F7F7F7;margin:0;"><div style="max-width:640px;margin:0 auto;background:#FFFFFF;"><div style="background:#002855;color:#FFFFFF;padding:20px 28px;"><div style="font-size:18px;font-weight:800;">Medical review requested · {{ session_code }}</div></div><div style="padding:24px 28px;font-size:14px;color:#002855;"><p>Hi {{ assignee_first_name }},</p><p>The draft transcript for {{ session_code }} — <em>{{ session_title }}</em> — is ready for your medical review. Please review with tracked changes enabled and return it to {{ prior_actor_full_name }} when complete.</p></div></div></body></html>'),
    (NULL, 'copy_final', 'en-US',
     '[VIN] Final copy edit pass — {{ session_code }}',
     '<html><body style="font-family:''ProximaNova'',sans-serif;background:#F7F7F7;margin:0;"><div style="max-width:640px;margin:0 auto;background:#FFFFFF;"><div style="background:#002855;color:#FFFFFF;padding:20px 28px;"><div style="font-size:18px;font-weight:800;">Final copy edit · {{ session_code }}</div></div><div style="padding:24px 28px;font-size:14px;color:#002855;"><p>Hi {{ assignee_first_name }},</p><p>Medical review is complete. Incorporate the medical reviewer notes, finalize speaker labels, and do the final readthrough.</p></div></div></body></html>'),
    (NULL, 'cms',        'en-US',
     '[VIN] Ready for CMS publish — {{ session_code }}',
     '<html><body style="font-family:''ProximaNova'',sans-serif;background:#F7F7F7;margin:0;"><div style="max-width:640px;margin:0 auto;background:#FFFFFF;"><div style="background:#002855;color:#FFFFFF;padding:20px 28px;"><div style="font-size:18px;font-weight:800;">Publish to CMS · {{ session_code }}</div></div><div style="padding:24px 28px;font-size:14px;color:#002855;"><p>Hi {{ assignee_first_name }},</p><p>Final copy is complete. Generate the CMS-ready document, upload to VIN library, and attest CE hours.</p></div></div></body></html>'),
    (NULL, 'captions',   'en-US',
     '[VIN] Captions ready for upload — {{ session_code }}',
     '<html><body style="font-family:''ProximaNova'',sans-serif;background:#F7F7F7;margin:0;"><div style="max-width:640px;margin:0 auto;background:#FFFFFF;"><div style="background:#002855;color:#FFFFFF;padding:20px 28px;"><div style="font-size:18px;font-weight:800;">Captions ready · {{ session_code }}</div></div><div style="padding:24px 28px;font-size:14px;color:#002855;"><p>Hi {{ assignee_first_name }},</p><p>The transcript is published to CMS. The SRT file is ready for Wistia upload and burn-in.</p></div></div></body></html>'),
    (NULL, 'qa',         'en-US',
     '[VIN] QA pass requested — {{ session_code }}',
     '<html><body style="font-family:''ProximaNova'',sans-serif;background:#F7F7F7;margin:0;"><div style="max-width:640px;margin:0 auto;background:#FFFFFF;"><div style="background:#002855;color:#FFFFFF;padding:20px 28px;"><div style="font-size:18px;font-weight:800;">QA pass · {{ session_code }}</div></div><div style="padding:24px 28px;font-size:14px;color:#002855;"><p>Hi {{ assignee_first_name }},</p><p>The session is ready for QA. Run end-to-end playback spot checks, verify mobile rendering, confirm search indexing, and validate GCS G1-G14 checks pass.</p></div></div></body></html>'),
    (NULL, 'complete',   'en-US',
     '[VIN] Session published · {{ session_code }}',
     '<html><body style="font-family:''ProximaNova'',sans-serif;background:#F7F7F7;margin:0;"><div style="max-width:640px;margin:0 auto;background:#FFFFFF;"><div style="background:#002855;color:#FFFFFF;padding:20px 28px;"><div style="font-size:18px;font-weight:800;">Published — {{ session_code }}</div></div><div style="padding:24px 28px;font-size:14px;color:#002855;"><p>Hi {{ prior_actor_full_name }},</p><p>{{ session_code }} is now live in the VIN library. Presenter notified, audit ledger archived.</p></div></div></body></html>')
ON CONFLICT ((COALESCE(session_type_id::text, '_default_')), stage_id, locale) WHERE is_active = TRUE DO NOTHING;
