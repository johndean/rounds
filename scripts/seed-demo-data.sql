-- scripts/seed-demo-data.sql
--
-- Seeds a couple of demo sessions + slides + segments + a couple of
-- improvements so the Rounds UI has something to render against the
-- live API. Run manually:
--
--   railway connect Postgres
--   \i scripts/seed-demo-data.sql
--
-- Idempotent on UNIQUE constraints (session code, etc). Safe to re-run.

-- ─── Session 1: a sample lecture ────────────────────────────────────────
INSERT INTO sessions (code, title, presenter, recorded_at, duration_sec, attendee_count, word_count, segment_count, taxonomy, status)
VALUES (
    'VIN-2026-001',
    'Approach to the Acute Abdomen in Small Animal Patients',
    'Dr. Heather Hayes',
    '2026-04-12 14:00:00+00',
    3600,
    142,
    8420,
    31,
    '["Internal Medicine","Surgery","Emergency"]'::jsonb,
    'ready'
) ON CONFLICT (code) DO UPDATE
    SET title = EXCLUDED.title,
        presenter = EXCLUDED.presenter,
        status = EXCLUDED.status,
        updated_at = now();

-- ─── Session 2: in-ingest ──────────────────────────────────────────────
INSERT INTO sessions (code, title, presenter, duration_sec, attendee_count, taxonomy, status)
VALUES (
    'VIN-2026-002',
    'Update on Feline Diabetes Management',
    'Dr. Brian Hur',
    2700,
    98,
    '["Endocrinology","Feline"]'::jsonb,
    'ingesting'
) ON CONFLICT (code) DO UPDATE
    SET status = EXCLUDED.status,
        updated_at = now();

-- ─── Session 3: a third example with different status ─────────────────
INSERT INTO sessions (code, title, presenter, duration_sec, taxonomy, status)
VALUES (
    'VIN-2026-003',
    'Oncology Rounds: Lymphoma Staging and Treatment',
    'Dr. Carla Bensley',
    4500,
    '["Oncology"]'::jsonb,
    'ready'
) ON CONFLICT (code) DO UPDATE
    SET status = EXCLUDED.status,
        updated_at = now();

-- ─── A few slides for session 1 ───────────────────────────────────────
WITH s1 AS (SELECT id FROM sessions WHERE code = 'VIN-2026-001')
INSERT INTO slides (session_id, slide_index, title, start_ms, end_ms)
SELECT s1.id, x.slide_index, x.title, x.start_ms, x.end_ms FROM s1, (VALUES
    (0, 'Title — Approach to the Acute Abdomen', 0, 30000),
    (1, 'Learning objectives', 30000, 90000),
    (2, 'Triage framework', 90000, 300000),
    (3, 'Differential diagnosis', 300000, 600000),
    (4, 'Imaging strategy', 600000, 900000),
    (5, 'Surgical decision making', 900000, 1500000)
) AS x(slide_index, title, start_ms, end_ms)
ON CONFLICT (session_id, slide_index) DO NOTHING;

-- ─── A couple of speakers ─────────────────────────────────────────────
WITH s1 AS (SELECT id FROM sessions WHERE code = 'VIN-2026-001')
INSERT INTO speakers (session_id, name, role, avatar_color)
SELECT s1.id, x.name, x.role, x.color FROM s1, (VALUES
    ('Dr. Heather Hayes', 'Instructor', '#2563eb'),
    ('Audience Q&A',     'Q&A',         '#7c3aed')
) AS x(name, role, color)
ON CONFLICT DO NOTHING;

-- ─── Sample segments for session 1 ────────────────────────────────────
WITH ctx AS (
    SELECT
        s.id AS sid,
        (SELECT id FROM slides WHERE session_id = s.id AND slide_index = 0) AS sl0,
        (SELECT id FROM slides WHERE session_id = s.id AND slide_index = 1) AS sl1,
        (SELECT id FROM slides WHERE session_id = s.id AND slide_index = 2) AS sl2,
        (SELECT id FROM speakers WHERE session_id = s.id AND name = 'Dr. Heather Hayes' LIMIT 1) AS spk
    FROM sessions s WHERE s.code = 'VIN-2026-001'
)
INSERT INTO segments (session_id, slide_id, speaker_id, seq, start_ms, end_ms, text, confidence, flags)
SELECT ctx.sid, x.slide, ctx.spk, x.seq, x.start_ms, x.end_ms, x.txt, x.conf, x.flags::jsonb
FROM ctx, (VALUES
    (1, 'sl0',  0,     7500,  'Welcome to today''s rounds on the acute abdomen in small animal patients.', 0.97, '[]'),
    (2, 'sl0',  7500,  16000, 'I''m Heather Hayes, and we''ll spend the next hour walking through triage, differentials, imaging, and the surgical decision tree.', 0.95, '[]'),
    (3, 'sl1',  30000, 48000, 'By the end of this session you should be able to apply a structured triage framework and articulate when imaging escalation is warranted.', 0.93, '[]'),
    (4, 'sl2',  90000, 110000,'Triage starts with the ABCs and a focused abdominal palpation — watch carefully for pain mapping and rigidity.', 0.91, '["terminology"]'),
    (5, 'sl2', 110000, 135000,'Note that fluid resuscitation should be started early but titrated cautiously in patients with possible cardiac compromise.', 0.94, '[]')
) AS x(seq, slide_key, start_ms, end_ms, txt, conf, flags)
LEFT JOIN ctx ON TRUE
JOIN LATERAL (SELECT CASE x.slide_key WHEN 'sl0' THEN ctx.sl0 WHEN 'sl1' THEN ctx.sl1 WHEN 'sl2' THEN ctx.sl2 END AS slide) AS sl ON TRUE
ON CONFLICT (session_id, seq) DO NOTHING;

-- ─── SOP state for session 1 ──────────────────────────────────────────
INSERT INTO sop_state (session_id, current_stage)
SELECT id, 'medical' FROM sessions WHERE code = 'VIN-2026-001'
ON CONFLICT (session_id) DO NOTHING;

INSERT INTO sop_state (session_id, current_stage)
SELECT id, 'prep' FROM sessions WHERE code = 'VIN-2026-002'
ON CONFLICT (session_id) DO NOTHING;

INSERT INTO sop_state (session_id, current_stage)
SELECT id, 'complete' FROM sessions WHERE code = 'VIN-2026-003'
ON CONFLICT (session_id) DO NOTHING;

-- ─── A couple of improvements ─────────────────────────────────────────
INSERT INTO improvements (title, description, type, status, priority, risk, area, submitted_by, is_security)
VALUES
    ('Add bulk reassign of segments to a slide',
     'When several consecutive segments belong to the same slide, allow drag-selecting and reassigning them in one action instead of one-by-one.',
     'feature', 'pending', 'medium', 'low', 'editor', 'johndean@vin.com', FALSE),
    ('Surface medication-flag confidence on hover',
     'Hovering a "medication" flag should show the Gemini classification confidence inline so reviewers know when to second-guess.',
     'ux', 'under_review', 'medium', 'low', 'editor', 'johndean@vin.com', FALSE),
    ('Audit redaction for closed sessions',
     'Sessions in the "archived" state should redact the corrections ledger from anyone below admin role.',
     'feature', 'pending', 'high', 'medium', 'audit', 'johndean@vin.com', TRUE)
ON CONFLICT DO NOTHING;
