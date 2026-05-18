-- 032_seed_people_and_groups — Idempotent seed of the 10 VIN team members
-- and 5 standard groups + memberships. Matches frontend fixtures so the
-- Team & roles section in Settings shows the same defaults as MIC.

INSERT INTO people (email, name) VALUES
    ('carlab@vin.com',          'Carla Burris'),
    ('hembroff@telus.net',      'Debbie Hembroff'),
    ('ericah@vin.com',          'Erica Hulse'),
    ('HeatherH@vin.com',        'Heather Howell'),
    ('janet.stomberg@vin.com',  'Janet Stomberg'),
    ('john@vetvision.org',      'John Dean'),
    ('lacy.sanders@vin.com',    'Lacy Sanders'),
    ('rachael@vin.com',         'Rachalel Carpenter'),
    ('ruth@vin.com',            'Ruth Schoonover'),
    ('tina.payton@vin.com',     'Tina Payton')
ON CONFLICT (email) DO NOTHING;

INSERT INTO groups (name) VALUES
    ('Content Team'),
    ('Debbie (and Team)'),
    ('External'),
    ('Main Contact'),
    ('V@V')
ON CONFLICT (name) DO NOTHING;

-- Group memberships — only INSERT if both sides exist.
INSERT INTO group_members (group_id, person_id)
SELECT g.id, p.id
FROM groups g, people p
WHERE (g.name, p.name) IN (
    ('Content Team',      'Carla Burris'),
    ('Content Team',      'Heather Howell'),
    ('Content Team',      'Ruth Schoonover'),
    ('Debbie (and Team)', 'Debbie Hembroff'),
    ('External',          'Carla Burris'),
    ('External',          'Heather Howell'),
    ('External',          'Ruth Schoonover'),
    ('Main Contact',      'Carla Burris'),
    ('V@V',               'Carla Burris')
)
ON CONFLICT (group_id, person_id) DO NOTHING;
