-- 039_seed_session_types — Seed Rounds' session_types with the 17 real
-- VIN conference rounds from MIC's Carla matrix (mic/migrations/012).
--
-- Matches the SESSION_TYPES fixture in frontend/src/fixtures/settings.ts.
-- ON CONFLICT (code) DO NOTHING — operator-added rows are not touched.
--
-- Runs AFTER 038 so is_default exists; the 'default' row is promoted
-- to is_default=TRUE by 038's UPDATE clause.

INSERT INTO session_types (code, label) VALUES
    ('default',                        'Default'),
    ('AAFV',                           'AAFV'),
    ('ABVP',                           'ABVP'),
    ('AEMV',                           'AEMV'),
    ('ARAV',                           'ARAV'),
    ('Cytology Cafe',                  'Cytology Cafe'),
    ('Euro',                           'Euro'),
    ('FelineVMA',                      'FelineVMA'),
    ('IVAPM',                          'IVAPM'),
    ('IVFSA',                          'IVFSA'),
    ('IVPA',                           'IVPA'),
    ('NAVAS',                          'NAVAS'),
    ('Therio',                         'Therio'),
    ('Tuesday Topic',                  'Tuesday Topic'),
    ('VECCS',                          'VECCS'),
    ('VVI Cage-Side',                  'VVI Cage-Side'),
    ('VVI Cage-Side Radiology Rounds', 'VVI Cage-Side Radiology Rounds')
ON CONFLICT (code) DO NOTHING;

-- Backfill is_default on the 'default' row if 038 ran before this seed
-- (which would have found no 'default' row and skipped the promotion).
UPDATE session_types SET is_default = TRUE
 WHERE code = 'default'
   AND NOT EXISTS (SELECT 1 FROM session_types WHERE is_default = TRUE);
