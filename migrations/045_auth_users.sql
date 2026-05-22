-- 045_auth_users — DB-backed user login table with bcrypt-hashed passwords.
--
-- Replaces the plaintext AUTH_USERS env-var CSV (known debt per CLAUDE.md +
-- audit §10 finding #7). The runtime seed hook in app/main.py lifespan
-- populates this table from AUTH_USERS on first boot if (and only if) it
-- is empty — so the cutover is invisible to existing logins.
--
-- Idempotent: every statement is `IF NOT EXISTS`. Reversible by
-- `DROP TABLE auth_users`.

CREATE TABLE IF NOT EXISTS auth_users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT NOT NULL,
    password_hash   TEXT NOT NULL,                   -- bcrypt $2b$… ~60 chars
    role            TEXT NOT NULL DEFAULT 'user',    -- 'admin' | 'user'
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ NULL,
    password_reset_at TIMESTAMPTZ NULL,              -- last admin-initiated reset
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Unique index on lower(email) so 'CarlaB@vin.com' and 'carlab@vin.com'
-- collapse to one row. Matches the case-insensitive _USER_DB.get(email.lower())
-- behavior in the env-CSV path.
CREATE UNIQUE INDEX IF NOT EXISTS auth_users_email_lower_uq
    ON auth_users (lower(email));

-- Partial index: most lookups are for active rows; filtered index keeps it small.
CREATE INDEX IF NOT EXISTS auth_users_active_idx
    ON auth_users (is_active) WHERE is_active = TRUE;
