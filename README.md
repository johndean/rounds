# Rounds

Transcript software for VIN. Successor to MIC (Media Intelligence Console).

**Domain:** [rounds.vin](https://rounds.vin)

**Stack:**
- Frontend: Vue 3 + TypeScript + Vite + Pinia + Vue Router (hash mode)
- Backend: FastAPI + SQLAlchemy (async) + asyncpg + Celery + Redis
- Database: PostgreSQL 15+ with pgvector
- Services: Google Cloud Storage, Cloud Speech-to-Text, Gemini, Vertex AI
- Hosting: Railway

## Spec sources

- **Frontend design:** `docs/IMPLEMENTATION.md` — Transcript Software v4 zero-gap reference (v4.0.0-ssot-r2). Every UX surface documented; pixel-by-pixel target.
- **Backend architecture:** `docs/MIC-AUDIT.md` — Exacting duplication reference from the MIC GCS / Railway / AI-services audit.
- **Build plan:** `docs/plans/2026-05-17-001-feat-rounds-bootstrap-plan.md` — 10 phases, ~70 implementation units.

## Bootstrap (operator checklist)

See plan §7 Phase 9 (Infrastructure Provisioning). Summary:

1. Create GCP project `rounds-prod-*`. Enable Cloud Storage, Speech-to-Text, Vertex AI APIs. Enable billing.
2. Create GCS bucket `rounds-prod-sessions` (uniform access, public access prevention enforced, us-central1).
3. Create service account `rounds-app@…iam.gserviceaccount.com` with bucket-scoped `storage.objectAdmin` + `speech.client` + `aiplatform.user`. Download JSON to `secrets/gcp-key.json`.
4. Get Gemini API key at https://aistudio.google.com.
5. `gh repo create vin-swe/rounds --private` and `gh repo create johndean/rounds`. Configure remotes:
   - `git remote add origin git@github.com:vin-swe/rounds.git`
   - `git remote add production git@github.com:johndean/rounds.git`
6. Railway: create project, add Postgres + Redis plugins, create api + worker services from `johndean/rounds`, set pre-deploy `python scripts/migrate.py`, paste env vars from `.env.example`.
7. DNS: point `rounds.vin` to Railway custom domain.

## Local dev

```bash
# Backend stack
docker-compose up db redis -d

# Migrations
poetry install
poetry run python scripts/migrate.py

# Seed admin
psql $DATABASE_URL -f scripts/seed-admin.sql

# API
poetry run uvicorn app.main:app --reload --port 8000

# Worker
poetry run celery -A app.tasks.celery_app.celery_app worker --loglevel=info --queues=celery

# Frontend
cd frontend && npm install && npm run dev
# → http://localhost:5173/#/dashboard
```

## Conventions

- Two-remote git: `origin=vin-swe/rounds` (dev), `production=johndean/rounds` (Railway auto-deploy).
- Conventional commits: `feat(scope):`, `fix(scope):`, `perf(scope):`, `docs(scope):`.
- Locked processing weights (FUSION_*, ALIGN_*, IIL_*, CELERY_*) — see plan §10. Do not tune without explicit authorization.
- Internal-page aesthetic: dark topbar + sans-serif (ProximaNova). Login screen uses Instrument Serif (VIN convention).
