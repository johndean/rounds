# CLAUDE.md — Rounds project guidance

This file is loaded by Claude Code when working in this repo. Keep it tight and authoritative.

## What this repo is

**Rounds** = transcript software for VIN, successor to MIC. Domain: [rounds.vin](https://rounds.vin).

| Layer | Status | Notes |
|---|---|---|
| Backend (FastAPI + SQLAlchemy + Celery + GCS/STT/Gemini/Vertex) | **Production-clean** | Ported 1:1 from the MIC `MIC-AUDIT.md` reference. 32 routes live. |
| Plumbing (auth/api client/router/stores/composables) | **Production-clean** | Type-safe, JWT-injected, hash-routed. |
| Frontend views | **In progress — pixel-by-pixel React→Vue port from `docs/port-source/`** | Login + chrome ported. Dashboard / Sessions / SessionDetail / Editor / SOP / Audit / Improvements / Upload / Viewer / Processing / Settings / TweaksPanel pending. |

The frontend is a **faithful Vue port of the React prototype**. Source of truth for layout, class names, and DOM structure is `docs/port-source/*.jsx`. Source of truth for styling is `frontend/src/styles/*.css` (copied verbatim from the prototype's `app.css` / `colors_and_type.css` / `wiring.css` / `settings.css` / `login.css`).

## Authoritative spec files

| File | Purpose |
|---|---|
| [`docs/IMPLEMENTATION.md`](./docs/IMPLEMENTATION.md) | Transcript Software v4 zero-gap reference (v4.0.0-ssot-r2) — prose description of every route/component/state. |
| [`docs/port-source/`](./docs/port-source/) | The React prototype source — 16 JSX files + 5 CSS files + HTML entry + fonts/assets. **Authoritative for layout + class names.** When porting a view, read the corresponding `.jsx` first. |
| [`docs/plans/2026-05-17-001-feat-rounds-bootstrap-plan.md`](./docs/plans/2026-05-17-001-feat-rounds-bootstrap-plan.md) | Build plan — 10 phases, ~70 implementation units. Updated as phases land. |
| [`docs/SPEC.md`](./docs/SPEC.md) | Open dependencies + decisions log. |

**THE REACT JSX IS THE SINGLE SOURCE OF TRUTH.** Per direct user directive (2026-05-17): "the react version is 100% accurate and is SSOT." When porting any view:
- Open the corresponding `docs/port-source/<name>.jsx` file.
- That React component's class names, DOM tree, data-test-ids, fixture shapes, behaviors are the spec.
- Port everything to Vue verbatim — no skips, no simplifications, no "the Vue HTML does it differently so I'll match that."

The Vue HTML at `docs/port-source/Transcript Software v4 - Vue.html` is an experimental Vue 3 port shipped alongside the React source. **DO NOT use it as a porting source.** Treat it as outdated/inaccurate. The gap analysis at [`docs/port-source-gap-analysis.md`](./docs/port-source-gap-analysis.md) documented its omissions — those omissions confirmed why React is the only authority. The Vue HTML can be served at [https://rounds.vin/prototype.html](https://rounds.vin/prototype.html) as a rough visual aid only.

## Porting rules (when converting a .jsx file to .vue)

1. **Read the JSX first.** Open `docs/port-source/<name>.jsx`. Note the exact class names, DOM structure, data-test-id attributes, and prop shapes.
2. **Match class names exactly** so the bundled `app.css` styles apply unchanged.
3. **Preserve `data-test-id`** attributes for Playwright + DX continuity.
4. **Replace mock state with real backend** — fixtures in `data.jsx` map to live endpoints in `frontend/src/services/api.ts`. The mock `toast.push` / `confirm.open` / `modal.open` calls map to my composables. The mock `wired.*` namespace maps to my `services/wired.ts`.
5. **No scaffolding banners. No "placeholder" comments. No "TODO Phase X".** If a section can't be ported faithfully, port what's ported well and leave the rest of the surface absent — don't fake it.
6. **Test paint by visual diff** against `https://rounds.vin/prototype.html` (the Vue HTML reference) and the React HTML at `docs/port-source/Transcript Software v4.html`.

## Backend boundaries (do NOT change without explicit user authorization)

- **Locked processing weights** (`FUSION_*`, `ALIGN_*`, `IIL_*`, `CELERY_*`) — see [`app/config.py`](./app/config.py) + pinning test [`tests/test_health.py::test_locked_weights_match_audit`](./tests/test_health.py).
- **R7 invariant** — `/v1/gcs/upload-complete` rejects any `gcs_uri` outside `gs://<bucket>/sessions/<id>/`. See [`app/services/gcs.py::find_out_of_scope_uri`](./app/services/gcs.py) + [`tests/test_gcs_scope.py`](./tests/test_gcs_scope.py).
- **AUTH_USERS** is plaintext in env (known debt — same posture as MIC audit §10 finding #7). Hashed-at-rest migration is a future plan.

## Production infrastructure (currently sharing MIC's data plane)

`GCP_PROJECT_ID`, `GCS_BUCKET`, `GCP_KEY_B64`, `GEMINI_API_KEY`, `SMTP_*`, `AUTH_USERS` were all copied verbatim from MIC's Railway env. Uploads land in `video-pipeline-uploads-mic`, Gemini bills MIC's quota, SMTP sends as `mic@design.veterinary.support`. Database + Redis are isolated (Rounds has its own Postgres + Redis plugins). If you need to provision Rounds-specific GCP / Gemini / SMTP, see [`docs/SPEC.md`](./docs/SPEC.md) for the migration steps — but require explicit user authorization first.

## Conventions

- **Two-remote git:** `origin=vin-swe/rounds` (dev), `production=johndean/rounds` (Railway auto-deploy). Push to both on every commit.
- **Conventional commits:** `feat(scope):`, `fix(scope):`, `perf(scope):`, `docs(scope):`, `refactor(scope):`.
- **Co-author tag** on commits: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
- **CSS class naming:** BEM-ish from the prototype (`.app-header__brand`, `.editor__statusbar`, etc.). Don't invent new class names — use what's already in `app.css`.
- **Component naming:** Vue SFC `PascalCase`, one component per file. Shared in `components/shared/`, route views in `views/`, route-specific sub-components in `components/<route>/`.
- **Internal-page aesthetic:** dark topbar + ProximaNova sans-serif. Login uses Instrument Serif via `login.css`.
- **No `useRouter`/`useRoute` unused imports** — vue-tsc rejects them (TS6133). Same for any unused composable.
- **204 endpoints** must use `response_class=Response` + return `Response(status_code=204)`. FastAPI 0.115 rejects `-> None` annotations with 204.

## Live URLs

- **Production:** [`https://rounds.vin`](https://rounds.vin) and [`https://api-production-c198.up.railway.app`](https://api-production-c198.up.railway.app)
- **Visual reference:** [`https://rounds.vin/prototype.html`](https://rounds.vin/prototype.html) — the Vue HTML reference build for side-by-side diffing
- **API docs:** [`https://rounds.vin/docs`](https://rounds.vin/docs) — FastAPI auto-generated Swagger UI
- **OpenAPI:** [`https://rounds.vin/openapi.json`](https://rounds.vin/openapi.json) — full route catalog

## Common operations

```bash
# Run the production deploy poller until terminal
cd /c/Users/JohnDean/rounds && railway service status --all --json

# Trigger a fresh deploy when git push doesn't seem to register
railway environment edit --json <<'JSON'
{"services":{"e1b3da55-...":{"variables":{"ROUNDS_DEPLOY_TRIGGER":{"value":"YYYY-MM-DD-N"}}}}}
JSON

# Local frontend build (fast smoke test of TS + Vite)
cd frontend && npm run build

# Tail the live deploy log
railway logs --service api --deployment --lines 100
```

## Railway service IDs (Rounds project `5741583d-47dd-4697-9732-d7744e82f215`)

- api: `e1b3da55-8789-4326-9362-b5a8e7c409cc`
- worker: `22ecca2b-5b8f-4757-ba94-ec1f2cd90e39`
- Postgres: `3eab9a85-562f-4c8a-86a6-fb4ccb027578`
- Redis: `639d68f5-35d4-4479-b0d1-1b16c95e3108`

## Emergency operator commands (`/v1/diag/*`)

The backend exposes 13 operator-only diagnostic + manual-rescue endpoints under `/v1/diag/`. All require a logged-in user (`CurrentUser` dep). None have a UI surface — they exist for curl / Postman use by operators when something has gone sideways. Source: [`app/api/diagnostics.py`](./app/api/diagnostics.py).

Auth pattern (run once to capture a token):
```bash
TOKEN=$(curl -s -X POST https://rounds.vin/v1/auth/login \
  -d "username=johndean@vin.com&password=<PW>" | python -c "import sys,json;print(json.load(sys.stdin)['data']['access_token'])")
```

### Read-only probes

```bash
# GCS credentials/project/bucket alignment check
curl -s -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/gcs

# Which classification backend is currently routed (gemini_dev vs vertex_ai)
curl -s -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/classify-route

# Full 14-item GCS health check ledger
curl -s -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/gcs-checks
```

### Per-session manual rescue

```bash
# Re-run the entire ingest pipeline for a session (resets status to 'uploading')
curl -s -X POST -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/reingest/<SESSION_ID>

# Re-trigger lcs_discrepancies_task (populates word_alignment for legacy sessions)
curl -s -X POST -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/realign/<SESSION_ID>

# Fire session_stage_assignees init (for sessions ingested before auto-init hook)
curl -s -X POST -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/init-session-stages/<SESSION_ID>

# Fire poll auto-placement (backfill polls that landed before autoplace was wired)
curl -s -X POST -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/autoplace-polls/<SESSION_ID>

# Force-abort a session that's stuck (sets status to 'failed', kills any in-flight task)
curl -s -X POST -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/abort-session/<SESSION_ID>
```

### Queue + task surgery

```bash
# Drain ALL pending Celery messages (use sparingly; after a misfired batch)
curl -s -X POST -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/flush-celery-queue

# Revoke a specific in-flight Celery task by task_id (from Celery logs / Flower)
curl -s -X POST -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/revoke-task/<TASK_ID>

# Run sop_check_deadlines_task synchronously (skips the Celery Beat cadence)
curl -s -X POST -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/sop-check
```

### Rate-limit + auth recovery

```bash
# Sweep Redis active-sessions slots for the calling user (unblocks 429 RATE_LIMIT_USER
# after a create+delete cycle leaves orphan slots)
curl -s -X POST -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/clear-rate-limit-slots

# Reseed auth_users table from the AUTH_USERS env CSV (use after Railway env update)
curl -s -X POST -H "Authorization: Bearer $TOKEN" https://rounds.vin/v1/diag/reseed-auth-users
```

These routes are stable. They are not test endpoints; they are production operator tools. If a route here ever becomes destructive (data loss potential), add a confirmation token requirement before relying on it in scripts.
