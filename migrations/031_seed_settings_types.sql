-- 031_seed_settings_types — Idempotent seed of the 17 VIN session_types so
-- a fresh Rounds DB matches MIC's Settings → Types list out-of-box.
--
-- Codes match frontend/src/fixtures/settings.ts::SESSION_TYPES. Re-running
-- this migration is safe: ON CONFLICT (code) DO NOTHING.

INSERT INTO session_types (code, label) VALUES
    ('default',                          'default'),
    ('AAFV',                             'AAFV'),
    ('ABVP',                             'ABVP'),
    ('AEMV',                             'AEMV'),
    ('ARAV',                             'ARAV'),
    ('Cytology Cafe',                    'Cytology Cafe'),
    ('Euro',                             'Euro'),
    ('FelineVMA',                        'FelineVMA'),
    ('IVAPM',                            'IVAPM'),
    ('IVFSA',                            'IVFSA'),
    ('IVPA',                             'IVPA'),
    ('NAVAS',                            'NAVAS'),
    ('Therio',                           'Therio'),
    ('Tuesday Topic',                    'Tuesday Topic'),
    ('VECCS',                            'VECCS'),
    ('VVI Cage-Side',                    'VVI Cage-Side'),
    ('VVI Cage-Side Radiology Rounds',   'VVI Cage-Side Radiology Rounds')
ON CONFLICT (code) DO NOTHING;
