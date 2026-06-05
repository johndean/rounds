# ADR-001 — Authentication: JWT + AUTH_USERS env fallback

- **Status:** Accepted
- **Date:** 2026-05-17 (bootstrap), refined 2026-06-05 (this document)
- **Deciders:** johndean@vin.com
- **Related:** [BR-001](../BUSINESS_RULES.md#br-001), [BR-013](../BUSINESS_RULES.md#br-013), [BR-020](../BUSINESS_RULES.md#br-020), [ADR-002](./ADR-002-session-lifecycle.md), [ADR-008](./ADR-008-websocket-architecture.md)

## Context

Rounds inherits MIC's authentication posture: a comma-separated `AUTH_USERS` env variable that holds `email:plaintext_password` rows, plus a `users` table seeded from that env. JWT tokens are the session medium. The bootstrap port (2026-05-17) had two constraints:

1. **Continuity** — operators already logged into MIC must work in Rounds the moment the deploy lands.
2. **Cutover safety** — during a Railway redeploy, the new container may boot before the `auth_users` table has been seeded from the new env CSV. A login attempt during that window must not return 401 if the user's email is in the env.

A pure-DB lookup fails constraint 2. A pure-env lookup fails the design goal of moving toward hashed-at-rest storage.

## Decision

**JWT-based session tokens with an env-CSV fallback in the resolver.**

- Login endpoint (`POST /v1/auth/login`) accepts `username + password`, validates against `auth_users` table first, falls back to the `AUTH_USERS` env CSV if the table is empty or the row is missing.
- `get_current_user(token)` (`app/auth.py`) decodes the JWT, then looks up the email in `auth_users`; if the row is missing, the resolver falls back to the env CSV (one-time, for cutover safety — see [BR-020](../BUSINESS_RULES.md#br-020)).
- The signing secret is `API_SECRET_KEY` (HS256, 8-hour expiry — `ACCESS_TOKEN_EXPIRE_MINUTES = 480`).
- One named bootstrap admin email (`LEGACY_ADMIN_EMAIL = "johndean@vin.com"` — [BR-001](../BUSINESS_RULES.md#br-001)) gates all operator surfaces until role-based access lands on `auth_users.role`.

## Consequences

- **Positive.**
  - Operators stay logged in across deploys.
  - Login works during the table-seed gap (~first few seconds after a fresh Postgres provision).
  - The migration toward hashed-at-rest storage can land incrementally — first introduce hash columns, then switch the lookup to prefer hashes, then retire the env fallback.
- **Negative.**
  - Passwords are stored in plaintext in the env. The `AUTH_USERS` value sits in Railway's variable store + every deploy log. Documented as known debt (CLAUDE.md "AUTH_USERS plaintext debt").
  - Two sources of truth (table + env) means a stale env row can still authenticate after the user is removed from the table.
- **Risks.**
  - Env-CSV leak (Railway dashboard exposure, screen-share with vars visible, a downloaded `.env`) compromises every account.
  - The bootstrap admin gate ([BR-001](../BUSINESS_RULES.md#br-001)) is a single email literal — if that mailbox is compromised the admin attack surface is significant.

## Code locations

- `app/auth.py` — `create_access_token`, `get_current_user`, env-CSV fallback
- `app/api/auth.py` — `POST /v1/auth/login` route
- `app/services/auth_users.py::seed_from_env_if_empty` — boot-time seeder (called from `app/main.py:62` lifespan)
- `app/security/roles.py:41` — `LEGACY_ADMIN_EMAIL`
- `app/config.py:30` — `AUTH_USERS: str` (fails fast if unset)
- `app/config.py:33–34` — `ALGORITHM = "HS256"`, `ACCESS_TOKEN_EXPIRE_MINUTES = 480`

## Alternatives considered

1. **Pure-DB lookup** — rejected because the table-seed gap on a fresh deploy would lock everyone out.
2. **Hashed env (bcrypt in `AUTH_USERS`)** — rejected at bootstrap because the MIC port had to be a 1:1 behavioral mirror; hashing the env would have diverged the source of truth from MIC's posture. Future ADR can supersede this once `auth_users.password_hash` is wired through the lookup.
3. **External IdP (Auth0, Clerk, custom OIDC)** — rejected for cost + complexity at this stage. Operator count is small; the env-CSV mechanism scales to dozens of users without friction.
4. **No bootstrap admin literal — gate on `auth_users.role` from day one** — deferred because the role column isn't yet wired into every operator surface. Tracked as Phase 8 admin-gate adoption. Until then, [BR-001](../BUSINESS_RULES.md#br-001) is the gate.

## When this ADR should be revisited

- When the `auth_users` table reliably exists at every login (i.e. the seed is universally idempotent and the migration has run on every environment) — drop the env-CSV fallback.
- When `auth_users.role` is wired through to gate operator surfaces — retire [BR-001](../BUSINESS_RULES.md#br-001).
- When a credential leak (real or simulated) forces hashed-at-rest storage.
