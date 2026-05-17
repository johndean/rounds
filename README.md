# Rounds

Transcript software for VIN. Successor to MIC (Media Intelligence Console).

**Production:** [`https://api-production-c198.up.railway.app`](https://api-production-c198.up.railway.app)
(rounds.vin custom domain pending DNS setup)

**Stack:**
- Frontend: Vue 3 + TypeScript + Vite + Pinia + Vue Router (hash mode)
- Backend: FastAPI + SQLAlchemy (async) + asyncpg + Celery + Redis
- Database: PostgreSQL 16 with pgvector
- Services: Google Cloud Storage, Cloud Speech-to-Text, Gemini, Vertex AI, Resend SMTP
- Hosting: Railway (Rounds project `5741583d-47dd-4697-9732-d7744e82f215`)

## Spec sources

- **Frontend design:** [`docs/IMPLEMENTATION.md`](./docs/IMPLEMENTATION.md) — Transcript Software v4 zero-gap reference (v4.0.0-ssot-r2).
- **Backend architecture:** [`docs/MIC-AUDIT.md`](./docs/MIC-AUDIT.md) — Exacting duplication reference from the MIC GCS / Railway / AI-services audit.
- **Build plan:** [`docs/plans/2026-05-17-001-feat-rounds-bootstrap-plan.md`](./docs/plans/2026-05-17-001-feat-rounds-bootstrap-plan.md) — 10 phases, ~70 implementation units.
- **Open dependencies:** [`docs/SPEC.md`](./docs/SPEC.md) — prototype CSS bundle retrieval, etc.

## What works today (production)

- ✅ Login flow (`POST /v1/auth/login` issues JWT; `/login` UI route serves the Vue app)
- ✅ Session CRUD (`/v1/sessions` GET/POST, filterable by `?stage` / `?ai`)
- ✅ Segments inline edit + reassign (`PATCH /v1/sessions/{id}/segments/{seg}`, `POST .../reassign`) — writes corrections ledger
- ✅ SOP state machine (`/v1/sessions/{id}/sop` + `/advance` + `/checks/resolve`) — forward-only 8-stage transitions
- ✅ Discrepancies API (`/v1/sessions/{id}/discrepancies` + `/resolve`)
- ✅ Improvements with 5-step wizard (`/v1/improvements` + `/wizard/{step}` + admin patch)
- ✅ Settings k/v + people/groups/types/email-templates (`/v1/settings/*`)
- ✅ Audit ledger (`/v1/audit` with `session_id` / `actor` / `kind` filters)
- ✅ GCS signed-URL upload with R7 scope-validation invariant (`/v1/gcs/upload-url` + `/v1/gcs/upload-complete`)
- ✅ Diagnostics endpoints (`/v1/diag/gcs`, `/v1/diag/classify-route`)
- ✅ Migrations 001-007 applied (incl. `CREATE EXTENSION vector`; embedding column ready)
- ✅ Frontend: AppHeader/TopBar, hash router with all 13 routes, Login screen, ⌘K Command Palette, Toast/Confirm/Modal hosts, Dashboard with live KPIs, Sessions list with `?stage`/`?ai` filter chips, Improvements master list + inline Suggest modal

## What's pending

- **rounds.vin DNS** — needs to be registered on the api service via Railway dashboard (CLI mutation requires browser confirmation for custom domains)
- **Prototype CSS bundle** — `app.css` (~3000 LOC), `wiring.css`, `settings.css`. Design URL is a viewer SPA; manual retrieval required. See [docs/SPEC.md](./docs/SPEC.md).
- **Phase 6 ingest pipelines** — Celery tasks (transcribe, frame_task, slide_extract, align, fuse, IIL, AI mode, classify_discrepancies, burn_captions). Celery app is bootstrapped; tasks land per [plan §7 Phase 6](./docs/plans/2026-05-17-001-feat-rounds-bootstrap-plan.md).
- **Phase 4 editor surface** — 3-column resizable layout + AI/STT/Discrepancies/Audit tabs + Slide Rail + Right Rail. Scaffolded views in place; full implementation gated on prototype bundle for pixel parity.

## Repo conventions

- **Two-remote git:** `origin=vin-swe/rounds` (dev), `production=johndean/rounds` (Railway auto-deploy).
- **Conventional commits:** `feat(scope):`, `fix(scope):`, `perf(scope):`, `docs(scope):`.
- **Locked processing weights:** FUSION_*, ALIGN_*, IIL_*, CELERY_* — see plan §10 and `tests/test_health.py::test_locked_weights_match_audit`. Do not tune without explicit authorization.
- **Internal-page aesthetic:** dark topbar + sans-serif (ProximaNova). Login uses Instrument Serif.
- **AUTH_USERS** is the auth source of truth (env CSV `email:password,…`). `people` table is for the Settings team-roles UI; doesn't gate login.

## Local dev

```bash
# Backend stack
docker-compose up db redis -d

# Migrations
poetry install
poetry run python scripts/migrate.py

# Seed admin (settings UI only — login is gated by AUTH_USERS env)
psql $DATABASE_URL -f scripts/seed-admin.sql

# API
poetry run uvicorn app.main:app --reload --port 8000

# Worker
poetry run celery -A app.tasks.celery_app.celery_app worker --loglevel=info --queues=celery

# Frontend
cd frontend && npm install && npm run dev
# → http://localhost:5173/#/dashboard (or /#/login if not authenticated)
```

## Production deploy

Push to `production` (`johndean/rounds`). Railway auto-deploys:
1. Build Docker image (multi-stage: vite build → python:3.11-slim runtime with ffmpeg)
2. Pre-deploy: `python scripts/migrate.py` runs against Postgres
3. Start: `bash scripts/start.sh api` (uvicorn) and `bash scripts/start.sh worker` (celery)
4. Healthcheck: `GET /v1/health` against the api service

Env vars for production live on Railway. `GCP_KEY_B64` (base64 of the GCP service account JSON) is decoded by `scripts/start.sh` to `/etc/gcp/sa.json` at container start so the Google SDKs can authenticate.
