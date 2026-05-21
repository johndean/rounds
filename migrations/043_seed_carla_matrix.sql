-- 043_seed_carla_matrix — Per-Type stage-default matrix from Carla's
-- 2026-04-18 spreadsheet (MIC migration 013). Ported to Rounds with:
--   - lowercase stage IDs (prep/copy_draft/medical/copy_final/cms/captions/qa)
--   - people matched by email (Rounds seed 032) instead of first_name
--     because Rachael's row has a typo'd first_name; emails are stable
--
-- Assignment summary:
--   - Tina (tina.payton@vin.com):     default + AAFV + ABVP + AEMV + ARAV +
--                                     Euro + IVPA + Therio — Prep/Copy/CMS
--   - Janet (janet.stomberg@vin.com): Cytology Cafe + VVI Cage-Side
--   - Rachael (rachael@vin.com):      FelineVMA + IVAPM + NAVAS + VECCS
--                                     (Medical Review handled by Rachael directly,
--                                     not via External)
--   - Lacy (lacy.sanders@vin.com):    IVFSA + Tuesday Topic + VVI Radiology +
--                                     QA on every type
--   - Erica (ericah@vin.com):         Captions on every type
--   - "External" group:               Medical Review on 11 types (default + AAFV +
--                                     ABVP + AEMV + ARAV + Cytology Cafe + Euro +
--                                     IVFSA + IVPA + Therio + Tuesday Topic)
--
-- Idempotent via ON CONFLICT (type_id, stage) DO UPDATE — Carla's spreadsheet
-- is the source of truth so operator edits will be overwritten on next migrate.
-- If operators need permanent overrides, ship as Unit 7 (session_stage_assignees
-- override that doesn't touch the Type matrix).
--
-- Depends on:
--   migration 032: people seed (the 5 names by email)
--   migration 038: is_default on session_types
--   migration 039: session_types seed (17 conference rounds)
--   migration 040: stage_assignees.person_id + group_id columns

-- ─── Ensure "External" group exists ──────────────────────────────────────
INSERT INTO groups (name) VALUES ('External')
ON CONFLICT (name) DO NOTHING;

-- ─── Person rows (Prep/Copy/CMS/Captions/QA by named person) ─────────────
INSERT INTO stage_assignees (type_id, stage, person_id, group_id, assignee_email, notify_email)
SELECT st.id, v.stage, p.id, NULL, p.email, TRUE
FROM (VALUES
    -- default
    ('default',                        'prep',       'tina.payton@vin.com'),
    ('default',                        'copy_draft', 'tina.payton@vin.com'),
    ('default',                        'copy_final', 'tina.payton@vin.com'),
    ('default',                        'cms',        'tina.payton@vin.com'),
    ('default',                        'captions',   'ericah@vin.com'),
    ('default',                        'qa',         'lacy.sanders@vin.com'),
    -- AAFV
    ('AAFV',                           'prep',       'tina.payton@vin.com'),
    ('AAFV',                           'copy_draft', 'tina.payton@vin.com'),
    ('AAFV',                           'copy_final', 'tina.payton@vin.com'),
    ('AAFV',                           'cms',        'tina.payton@vin.com'),
    ('AAFV',                           'captions',   'ericah@vin.com'),
    ('AAFV',                           'qa',         'lacy.sanders@vin.com'),
    -- ABVP
    ('ABVP',                           'prep',       'tina.payton@vin.com'),
    ('ABVP',                           'copy_draft', 'tina.payton@vin.com'),
    ('ABVP',                           'copy_final', 'tina.payton@vin.com'),
    ('ABVP',                           'cms',        'tina.payton@vin.com'),
    ('ABVP',                           'captions',   'ericah@vin.com'),
    ('ABVP',                           'qa',         'lacy.sanders@vin.com'),
    -- AEMV
    ('AEMV',                           'prep',       'tina.payton@vin.com'),
    ('AEMV',                           'copy_draft', 'tina.payton@vin.com'),
    ('AEMV',                           'copy_final', 'tina.payton@vin.com'),
    ('AEMV',                           'cms',        'tina.payton@vin.com'),
    ('AEMV',                           'captions',   'ericah@vin.com'),
    ('AEMV',                           'qa',         'lacy.sanders@vin.com'),
    -- ARAV
    ('ARAV',                           'prep',       'tina.payton@vin.com'),
    ('ARAV',                           'copy_draft', 'tina.payton@vin.com'),
    ('ARAV',                           'copy_final', 'tina.payton@vin.com'),
    ('ARAV',                           'cms',        'tina.payton@vin.com'),
    ('ARAV',                           'captions',   'ericah@vin.com'),
    ('ARAV',                           'qa',         'lacy.sanders@vin.com'),
    -- Cytology Cafe (Janet runs it)
    ('Cytology Cafe',                  'prep',       'janet.stomberg@vin.com'),
    ('Cytology Cafe',                  'copy_draft', 'janet.stomberg@vin.com'),
    ('Cytology Cafe',                  'copy_final', 'janet.stomberg@vin.com'),
    ('Cytology Cafe',                  'cms',        'janet.stomberg@vin.com'),
    ('Cytology Cafe',                  'captions',   'ericah@vin.com'),
    ('Cytology Cafe',                  'qa',         'lacy.sanders@vin.com'),
    -- Euro
    ('Euro',                           'prep',       'tina.payton@vin.com'),
    ('Euro',                           'copy_draft', 'tina.payton@vin.com'),
    ('Euro',                           'copy_final', 'tina.payton@vin.com'),
    ('Euro',                           'cms',        'tina.payton@vin.com'),
    ('Euro',                           'captions',   'ericah@vin.com'),
    ('Euro',                           'qa',         'lacy.sanders@vin.com'),
    -- FelineVMA (Rachael does MR + everything)
    ('FelineVMA',                      'prep',       'rachael@vin.com'),
    ('FelineVMA',                      'copy_draft', 'rachael@vin.com'),
    ('FelineVMA',                      'medical',    'rachael@vin.com'),
    ('FelineVMA',                      'copy_final', 'rachael@vin.com'),
    ('FelineVMA',                      'cms',        'rachael@vin.com'),
    ('FelineVMA',                      'captions',   'ericah@vin.com'),
    ('FelineVMA',                      'qa',         'lacy.sanders@vin.com'),
    -- IVAPM (Rachael does MR + everything)
    ('IVAPM',                          'prep',       'rachael@vin.com'),
    ('IVAPM',                          'copy_draft', 'rachael@vin.com'),
    ('IVAPM',                          'medical',    'rachael@vin.com'),
    ('IVAPM',                          'copy_final', 'rachael@vin.com'),
    ('IVAPM',                          'cms',        'rachael@vin.com'),
    ('IVAPM',                          'captions',   'ericah@vin.com'),
    ('IVAPM',                          'qa',         'lacy.sanders@vin.com'),
    -- IVFSA (Lacy runs it)
    ('IVFSA',                          'prep',       'lacy.sanders@vin.com'),
    ('IVFSA',                          'copy_draft', 'lacy.sanders@vin.com'),
    ('IVFSA',                          'copy_final', 'lacy.sanders@vin.com'),
    ('IVFSA',                          'cms',        'lacy.sanders@vin.com'),
    ('IVFSA',                          'captions',   'ericah@vin.com'),
    ('IVFSA',                          'qa',         'lacy.sanders@vin.com'),
    -- IVPA
    ('IVPA',                           'prep',       'tina.payton@vin.com'),
    ('IVPA',                           'copy_draft', 'tina.payton@vin.com'),
    ('IVPA',                           'copy_final', 'tina.payton@vin.com'),
    ('IVPA',                           'cms',        'tina.payton@vin.com'),
    ('IVPA',                           'captions',   'ericah@vin.com'),
    ('IVPA',                           'qa',         'lacy.sanders@vin.com'),
    -- NAVAS (Rachael does MR + everything)
    ('NAVAS',                          'prep',       'rachael@vin.com'),
    ('NAVAS',                          'copy_draft', 'rachael@vin.com'),
    ('NAVAS',                          'medical',    'rachael@vin.com'),
    ('NAVAS',                          'copy_final', 'rachael@vin.com'),
    ('NAVAS',                          'cms',        'rachael@vin.com'),
    ('NAVAS',                          'captions',   'ericah@vin.com'),
    ('NAVAS',                          'qa',         'lacy.sanders@vin.com'),
    -- Therio
    ('Therio',                         'prep',       'tina.payton@vin.com'),
    ('Therio',                         'copy_draft', 'tina.payton@vin.com'),
    ('Therio',                         'copy_final', 'tina.payton@vin.com'),
    ('Therio',                         'cms',        'tina.payton@vin.com'),
    ('Therio',                         'captions',   'ericah@vin.com'),
    ('Therio',                         'qa',         'lacy.sanders@vin.com'),
    -- Tuesday Topic (Lacy runs it)
    ('Tuesday Topic',                  'prep',       'lacy.sanders@vin.com'),
    ('Tuesday Topic',                  'copy_draft', 'lacy.sanders@vin.com'),
    ('Tuesday Topic',                  'copy_final', 'lacy.sanders@vin.com'),
    ('Tuesday Topic',                  'cms',        'lacy.sanders@vin.com'),
    ('Tuesday Topic',                  'captions',   'ericah@vin.com'),
    ('Tuesday Topic',                  'qa',         'lacy.sanders@vin.com'),
    -- VECCS (Rachael does MR + everything)
    ('VECCS',                          'prep',       'rachael@vin.com'),
    ('VECCS',                          'copy_draft', 'rachael@vin.com'),
    ('VECCS',                          'medical',    'rachael@vin.com'),
    ('VECCS',                          'copy_final', 'rachael@vin.com'),
    ('VECCS',                          'cms',        'rachael@vin.com'),
    ('VECCS',                          'captions',   'ericah@vin.com'),
    ('VECCS',                          'qa',         'lacy.sanders@vin.com'),
    -- VVI Cage-Side (Janet does MR + everything)
    ('VVI Cage-Side',                  'prep',       'janet.stomberg@vin.com'),
    ('VVI Cage-Side',                  'copy_draft', 'janet.stomberg@vin.com'),
    ('VVI Cage-Side',                  'medical',    'janet.stomberg@vin.com'),
    ('VVI Cage-Side',                  'copy_final', 'janet.stomberg@vin.com'),
    ('VVI Cage-Side',                  'cms',        'janet.stomberg@vin.com'),
    ('VVI Cage-Side',                  'captions',   'ericah@vin.com'),
    ('VVI Cage-Side',                  'qa',         'lacy.sanders@vin.com'),
    -- VVI Cage-Side Radiology Rounds (Lacy does MR + everything)
    ('VVI Cage-Side Radiology Rounds', 'prep',       'lacy.sanders@vin.com'),
    ('VVI Cage-Side Radiology Rounds', 'copy_draft', 'lacy.sanders@vin.com'),
    ('VVI Cage-Side Radiology Rounds', 'medical',    'lacy.sanders@vin.com'),
    ('VVI Cage-Side Radiology Rounds', 'copy_final', 'lacy.sanders@vin.com'),
    ('VVI Cage-Side Radiology Rounds', 'cms',        'lacy.sanders@vin.com'),
    ('VVI Cage-Side Radiology Rounds', 'captions',   'ericah@vin.com'),
    ('VVI Cage-Side Radiology Rounds', 'qa',         'lacy.sanders@vin.com')
) AS v(type_code, stage, person_email)
JOIN session_types st ON st.code = v.type_code
JOIN people p ON LOWER(p.email) = LOWER(v.person_email)
ON CONFLICT (type_id, stage) DO UPDATE
    SET person_id      = EXCLUDED.person_id,
        group_id       = NULL,
        assignee_email = EXCLUDED.assignee_email,
        notify_email   = EXCLUDED.notify_email;

-- ─── Group rows (Medical Review → External for 11 types) ─────────────────
INSERT INTO stage_assignees (type_id, stage, person_id, group_id, assignee_email, notify_email)
SELECT st.id, 'medical', NULL, g.id, 'Group: ' || g.name, TRUE
FROM (VALUES
    ('default'),
    ('AAFV'),
    ('ABVP'),
    ('AEMV'),
    ('ARAV'),
    ('Cytology Cafe'),
    ('Euro'),
    ('IVFSA'),
    ('IVPA'),
    ('Therio'),
    ('Tuesday Topic')
) AS v(type_code)
JOIN session_types st ON st.code = v.type_code
JOIN groups g ON g.name = 'External'
ON CONFLICT (type_id, stage) DO UPDATE
    SET person_id      = NULL,
        group_id       = EXCLUDED.group_id,
        assignee_email = EXCLUDED.assignee_email,
        notify_email   = EXCLUDED.notify_email;
