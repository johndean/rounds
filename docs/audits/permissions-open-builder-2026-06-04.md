# Phase 8 Audit — Open Builder Permissions Root Cause
Generated 2026-06-04 against tip 6df4170. **READ-ONLY investigation. No code modified.**

## Builder page — file + route

The only "Open builder" CTA in the codebase is the **Email Template Builder**, reached via:

- **Route:** `/settings/email` (vue-router param `:section=email`)
- **Container:** `frontend/src/views/SettingsView.vue` — line 84 mounts `<SectionEmail />` when `active === 'email'`. No role gate at the route or section level.
- **Drill-in:** `frontend/src/components/settings/SectionEmail.vue` — line 19 renders the CTA `{ label: 'Open builder', onClick: () => (view = 'builder') }`; line 14 then mounts `<EmailBuilder v-if="view === 'builder'" />`.
- **Builder file:** `frontend/src/components/settings/EmailBuilder.vue` — title on line 320 is literally "Email Template Builder".

(Searched all of `frontend/src` for the strings `Open Builder` / `open builder` / `Builder`. There is **no other** "Builder" surface — no Prompt-Template Builder, no Action-Plan Builder modal exposing an Open Builder CTA. `ImprovDetail.vue` is the "5-step Action Plan Builder" but never renders an "Open Builder" affordance.)

## Templates content — data source

Inside `EmailBuilder.vue` the heading **"Email Templates (per Type × Stage)"** (line 342) is what the user perceives as "Templates" inside the Builder. Two endpoints feed it:

1. **Type dropdown** (top-right select on line 326–334) — populated by `settingsApi.types()` in `EmailBuilder.vue:93` → `GET /v1/settings/types`.
2. **Subject + HTML body editor** (left pane of `set-emailbuilder`) — populated by `emailTemplatesApi.resolve()` in `EmailBuilder.vue:66` → `POST /v1/email-templates/resolve` with `{ session_type_id, stage_id, locale }`. Mutates `subject` / `body` / `resolvedFrom` refs that the template panel renders.

If either call 4xxs, the catch block on `EmailBuilder.vue:75-88` sets `current=null`, `subject=''`, `body=''`, shows an error toast — UI surface stays mounted but visibly empty. **That is the exact "Templates not visible" symptom.**

## Backend endpoint — auth dependency + role check (file:line)

`app/api/email_templates.py`:

- **`GET /v1/email-templates`** — `app/api/email_templates.py:91-92` — `_u: CurrentUser` only. **No admin guard.** Any logged-in user can list.
- **`GET /v1/email-templates/{id}`** — `app/api/email_templates.py:131-132` — `_u: CurrentUser` only.
- **`POST /v1/email-templates/resolve`** — `app/api/email_templates.py:242-244` — `_u: CurrentUser` only. **No admin guard.** Resolution is freely readable.
- **`POST /v1/email-templates`** (create) — `app/api/email_templates.py:143-149` — calls `_require_admin(user)` on line 149. Hardcoded check `user.email != "johndean@vin.com"` → **HTTP 403 `{code: "ADMIN_ONLY"}`**.
- **`PUT /v1/email-templates/{id}`** — `app/api/email_templates.py:187-192` — `_require_admin(user)` on line 192.
- **`DELETE /v1/email-templates/{id}`** — `app/api/email_templates.py:221-224` — `_require_admin(user)` on line 224.

The admin gate itself is `_require_admin` at `app/api/email_templates.py:39-44`:

```python
ADMIN_EMAIL = "johndean@vin.com"

def _require_admin(user) -> None:
    if not hasattr(user, "email") or user.email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail={"code": "ADMIN_ONLY", "message": "admin only"})
```

Type-listing (`GET /v1/settings/types`, `app/api/settings.py:316-325`) is also `_u: CurrentUser` only — no admin gate.

## RBAC pattern in rounds — how roles are encoded

The repo has **two parallel role concepts** that are not yet integrated:

1. **`auth_users.role` column** (migration 045) — values `'admin'` or `'user'`, returned by `lookup_user` in `app/services/auth_users.py:108-130` (`AuthUserRow.role`). Seeded during env→DB bootstrap at `app/services/auth_users.py:206`: `role = "admin" if email.lower() == _ADMIN_EMAIL.lower() else "user"`. The seed pins `_ADMIN_EMAIL = "johndean@vin.com"` (line 36).
2. **`ADMIN_EMAIL` string constants** — `"johndean@vin.com"` literally hardcoded in five places: `app/api/settings.py:20`, `app/api/email_templates.py:36`, `app/api/email_debug.py`, `app/api/diagnostics.py`, `app/services/auth_users.py:36`. The comment at `auth_users.py:33-35` is explicit: "**When a future commit adds role-based middleware, this becomes a single source of truth via app/config.py.**"

The hot-path `get_current_user` dependency (`app/auth.py:169-202`) returns a frozen `User(email=str)` dataclass — **role is never read or carried**. The JWT (`app/auth.py:153`) only encodes `{sub: email}`. So even though `auth_users.role` exists in the DB, **no endpoint consults it**; every admin gate is a literal `user.email == "johndean@vin.com"` string compare. There is no `app/security/` package; `app/middleware/` only contains envelope/idempotency/rate-limit/request-id (not RBAC).

`AUTH_USERS` env CSV (`app/config.py:30`) is the DR fallback; it has no role syntax — entries are `email:password,email:password,…`. Role is inferred at seed time only.

## Frontend visibility gate — where + how

**There is no frontend role gate anywhere.** Searched `frontend/src/services/api.ts`: `auth.me` is typed as `http<{ email: string }>('/v1/auth/me')` at line 22 — **role is not requested or returned**. Backend `/v1/auth/me` at `app/api/auth.py:31-34` returns `{"email": user.email}` only.

Stores (`frontend/src/stores/`) hold no role state. The Settings nav (`SettingsView.vue:38-52`) lists every section unconditionally; SectionEmail's `Open builder` button (`SectionEmail.vue:19`) is unconditional; EmailBuilder mounts unconditionally; both `loadResolved()` (line 63) and `settingsApi.types()` (line 93) are unconditional. **The "Templates" inner panel has no `v-if`/`v-show` role check** — it always renders, populated from the API response.

## Walk-through: non-superadmin clicks Open Builder

1. User logs in (e.g. `lacy@vin.com`). `POST /v1/auth/login` returns a valid JWT with `sub=lacy@vin.com`.
2. User navigates to `#/settings/email`. `SettingsView.vue:84` mounts `<SectionEmail />`. **Renders.**
3. User clicks **Open builder** (`SectionEmail.vue:19`). `view` flips to `'builder'`. `<EmailBuilder />` mounts. The header "Email Template Builder" paints. **Builder visible** ✓ (matches symptom).
4. `onMounted` fires (`EmailBuilder.vue:91-99`):
   - `await settingsApi.types()` → `GET /v1/settings/types`. Backend (`app/api/settings.py:316-325`) requires only `CurrentUser` → **200 OK**, Type dropdown populates.
   - `await loadResolved()` → `POST /v1/email-templates/resolve` with `{session_type_id: null, stage_id: 'prep', locale: 'en-US'}`. Backend (`app/api/email_templates.py:242-286`) requires only `CurrentUser` → **200 OK** with default-row body+subject. `current.value`, `subject`, `body` populate.
5. **Templates panel SHOULD now render with the default 'prep' template subject and body.** The fact that the reporter says "Templates not visible" means one of:
   - 5a. The `resolve` call 404'd (no default row for stage=`prep` locale=`en-US` is active — migration 048 seed missing on the user's environment, or `is_active=FALSE` somehow). The catch on `EmailBuilder.vue:75-88` clears the editor and toasts.
   - 5b. The user's JWT is expired/invalid → `get_current_user` raises 401 → blanket auth failure on both calls → editor stays empty + toast.
   - 5c. The user's `auth_users.is_active` flipped to false → `get_current_user` (`app/auth.py:191`) returns 401 → same as 5b.
6. User clicks **Save default** / **Save for this Type**: `saveForType()` (`EmailBuilder.vue:103-166`) calls `emailTemplatesApi.add` or `.update`. Backend (`email_templates.py:149` or `:192`) calls `_require_admin(user)` → **HTTP 403 ADMIN_ONLY** because `user.email != "johndean@vin.com"`. Toast "403 — admin only". The save silently fails.
7. Test send (`sendTest`, `EmailBuilder.vue:193-233`) hits `emailDebug.send()` → `/v1/admin/email-debug/send`, which also has an `_require_admin` gate (`app/api/email_debug.py`, same `ADMIN_EMAIL` constant) → **403** for non-admins.

## Root cause hypothesis — RANKED most-likely first

### 1. Hardcoded single-admin gate; non-admin users can READ templates but cannot SAVE — UI surfaces save-failure as if Templates is broken

**Evidence:**
- Six write endpoints in `email_templates.py` + `email_debug.py` + `settings.py` (templates) gate on `user.email == "johndean@vin.com"` (`email_templates.py:36-44`).
- Read endpoints (`list`, `get`, `resolve`) require only `CurrentUser` — so for a logged-in non-admin, the data DOES come back. The Templates panel populates.
- BUT every `Save` / `Save for this Type` / `Remove override` / `Send test` button returns **403 ADMIN_ONLY**, and the toast is the only feedback. If the user perceives "I can't edit anything in Templates" as "Templates not visible," this is the cause.
- This matches the symptom **"Builder visible, Templates not visible"** as a UX framing: the page paints, the editor pane visually exists, but it behaves as inert/read-only with no explanation — i.e. functionally "not visible" as a feature.

**Fix shape (NOT implemented):** in `app/api/email_templates.py:39-44`, replace the hardcoded email compare with a role lookup against `auth_users.role`. Concretely: introduce `app/security/roles.py::require_admin(user)` that joins the email to `auth_users` and checks `role == 'admin'`, then call it from `email_templates.py:149,192,224`. Equivalent fix in `app/api/settings.py:20-25` and `email_debug.py`. Do **not** broaden write access — keep it `role='admin'` only; just stop comparing to a single literal email so the existing `auth_users.role='admin'` rows actually grant access. One-line shape: `_require_admin` → `if user.role != 'admin': raise 403` after threading `role` through `User` and JWT.

### 2. Frontend `User` shape drops `role`, so even if a frontend gate existed, it'd be a no-op

**Evidence:**
- `auth.me` in `frontend/src/services/api.ts:22` is typed `http<{ email: string }>`.
- Backend `/v1/auth/me` (`app/api/auth.py:31-34`) returns `{"email": user.email}` only — `User` dataclass in `app/auth.py:33-35` has only `email`. JWT in `app/auth.py:153` carries only `sub` (email).
- This means there is **no client-side way today** to gate a UI element by role even if we wanted to.

**Fix shape (NOT implemented):** thread `role` from `auth_users` row → `User` dataclass → `/v1/auth/me` response → frontend `auth.me()` type → store. Add `v-if="userRole === 'admin'"` only on the *write* affordances (Save / Send test) — not on the Builder page or Templates panel itself. Read access already works.

### 3. Backend returns 200 + empty/missing default row for the (stage, locale) combo

**Evidence:**
- `loadResolved()` on first mount asks for `stage_id='prep', locale='en-US'` (`EmailBuilder.vue:32-49,66-70`). Migration 048 is documented as seeding "one default row per stage." If the seed didn't run (fresh DB, partial migration, environment that skipped 048), `resolve` 404s with `NOT_FOUND` (`email_templates.py:282-286`).
- The catch (`EmailBuilder.vue:75-88`) clears `subject`/`body`/`current` and toasts — exact "Templates empty" symptom.
- Easy to distinguish from #1 by reproing as a known admin (`johndean@vin.com`): if it's still blank, it's a data issue, not a permissions issue.

**Fix shape (NOT implemented):** ops fix — verify migration 048 seed actually ran on the affected environment (`SELECT count(*) FROM email_templates WHERE session_type_id IS NULL AND is_active = TRUE GROUP BY stage_id` should return 8 rows). Re-run migration if not. No code change.

### 4. User's `auth_users.is_active = FALSE`

**Evidence:** `get_current_user` (`app/auth.py:190-200`) returns 401 if `user_is_active` is false and env CSV fallback also doesn't have them. All endpoints fail → catch clears editor. But this would also break the Builder itself painting fully (login would survive on token; per-request 401s would be uniform). Less consistent with "Builder visible, Templates not visible" framing than #1.

**Fix shape (NOT implemented):** ops — reactivate user via Settings → Auth & logins, or `UPDATE auth_users SET is_active = TRUE WHERE email = '<user>'`.

### 5. (c) frontend hides templates section unless role check — **ruled out**

There is no frontend role check anywhere. Confirmed by grep over `frontend/src` for `isAdmin`, `is_admin`, `role` — no template-visibility gate exists. The Templates panel renders unconditionally.

## Highest-confidence next step (read-only verification we can run)

```bash
# 1. As the affected non-admin user (capture token):
TOKEN_USER=$(curl -s -X POST https://rounds.vin/v1/auth/login \
  -d "username=<affected_user>@vin.com&password=<PW>" \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 2. Confirm READ works (expect 200 + JSON body):
curl -sv -H "Authorization: Bearer $TOKEN_USER" \
  -H "Content-Type: application/json" \
  -d '{"session_type_id": null, "stage_id": "prep", "locale": "en-US"}' \
  https://rounds.vin/v1/email-templates/resolve

# 3. Confirm WRITE returns 403 ADMIN_ONLY (this is the smoking gun for #1):
curl -sv -X POST -H "Authorization: Bearer $TOKEN_USER" \
  -H "Content-Type: application/json" \
  -d '{"session_type_id": null, "stage_id": "prep", "locale": "en-US", "subject": "x", "body": "y"}' \
  https://rounds.vin/v1/email-templates

# Expected result that confirms hypothesis #1:
#   step 2 → 200 OK with subject/body  (READ works → Templates content IS server-side available)
#   step 3 → 403 {"detail":{"code":"ADMIN_ONLY","message":"admin only"}}
#
# If step 2 is 404 instead, hypothesis shifts to #3 (missing seed row).
# If step 2 is 401, hypothesis shifts to #2/#4 (token/account invalidity).
```

## Risks of proposed minimal fix

- **Do NOT broaden write access**: keep the gate at `role='admin'`. Today `auth_users.role` already has exactly one `'admin'` row per design (`johndean@vin.com`), so swapping email-compare for role-lookup is functionally identical for the live admin and explicitly scoped for future admin promotion via Settings → Auth & logins. Anything looser would expand the trust boundary.
- **Locked constants unchanged**: the proposed fix only edits the admin gate in three API files (`email_templates.py`, `settings.py`, `email_debug.py`); does not touch `FUSION_*`/`ALIGN_*`/`IIL_*`/`CELERY_*` (CLAUDE.md "locked weights"), `app/services/gcs.py::find_out_of_scope_uri` (R7 invariant), the C1-locked pipeline tasks under `app/tasks/`, or `frontend/src/views/UploadView.vue` (C2-locked).
- **AUTH_USERS env semantics unchanged**: env CSV still has no role syntax; admin promotion remains a DB-only operation via Settings → Auth & logins (`/v1/settings/auth-users`), preserving the "AUTH_USERS plaintext is known debt" posture from CLAUDE.md.
- **Token rev**: threading `role` into JWT (per hypothesis #2 fix) would invalidate existing tokens on cutover — operator-visible re-login required. Acceptable but should be flagged in the migration plan, not silently shipped.
- **Read access stays open to all logged-in users** in the proposed fix shape — that matches today's behavior and is required so the Type dropdown + default-template preview keep working for non-admins who might be granted limited write access later via more granular roles. If product later wants read also gated, that's a separate scope.
