# Rounds Data Dictionary

Code-verified reference for every table created or altered by the SQL migrations in [`migrations/`](../../migrations/). Each migration is a plain `.sql` file applied in filename order by the runner (`scripts/migrate.py`); there is no ORM-defined schema — the migrations are the source of truth.

Scope note: this document covers the **relational schema only**. JSONB columns are documented by their inline comment / observed shape, but the contents of a JSONB blob are not a fixed schema and are tagged where their meaning is not provable from code.

Permission reality (verified, applies to every "Used By APIs" row below): authorization today is **JWT presence** on the request plus a hardcoded `user.email == 'johndean@vin.com'` gate (`LEGACY_ADMIN_EMAIL`) in a handful of endpoints, plus one client-side `adminOnly` route guard. The `auth_users.role` column (migration 045) and `app/security/roles.py` are **not** wired into `get_current_user`. No table below is protected by a role tier at runtime.

---

## Migration numbering & resolved gaps (2026-06-10)

These resolve [`docs/gap-analysis.md`](../gap-analysis.md) §4 at the documentation level (zero risk). Plan: [`docs/plans/2026-06-10-001-zero-risk-gap-remediation.md`](../plans/2026-06-10-001-zero-risk-gap-remediation.md). DB-side mirror: migration `058_schema_comments.sql` (COMMENT-only).

- **Migration numbering is non-contiguous by design.** There is no `007_*.sql` (the sequence runs 006 → 008). The runner keys on slug, not ordinal, so the gap is cosmetic — **never renumber** an applied migration.
- **Legacy `006` `email_templates` / `prompt_templates` are superseded.** `006` still runs on a fresh DB, then `048`/`047` DROP+CREATE the live schema. Read the 047/048 schema as authoritative (see those table sections). Never edit `006`.
- **"Twin" tables are all live and distinct — none is a duplicate to drop:** `corrections` (002) + `correction_ledger` (029); `discrepancies` (002) + `transcription_discrepancies` (017); `speakers` (001) + `session_speakers` (011). See Cross-cutting notes and each section.
- **`validation_results` is two distinct things, both used:** the `validation_results` **table** (014, keyed by `alignment_id`) and the `normalization_results.validation_results` **JSONB column** (012). Naming collision only.
- **`sop_approvals` (003) is RESERVED/UNUSED:** created with a CASCADE FK but zero `app/` readers/writers — empty in every environment. Retained for the planned per-stage sign-off feature.
- **`session_locks.session_id` has no FK by current design (accepted):** lock rows are ephemeral (90s TTL, swept) and the app only writes existing `session_id`s, so the worst case is a stale row that ages out. Optional CASCADE-FK hardening is the plan's Track C2 and is **not** applied here.

---

## Table catalog

| Table | Created in | Domain area |
|---|---|---|
| `sessions` | 001 (+ altered 010, 011, 035, 041, 046) | Core session record |
| `sources` | 001 | Uploaded source files |
| `slides` | 001 (+ altered 016) | Slide deck pages |
| `speakers` | 001 | Runtime detected speakers |
| `segments` | 001 (+ altered 020, 022) | Transcript segments |
| `discrepancies` | 002 | Editor discrepancy tab rows |
| `corrections` | 002 | Legacy inline-edit log |
| `sop_state` | 003 | SOP workflow state (1/session) |
| `sop_transitions` | 003 | SOP stage transition log |
| `sop_checks` | 003 | Per-stage acceptance checks |
| `sop_approvals` | 003 | Per-stage sign-off signatures |
| `audit_events` | 004 | Global append-only event log |
| `improvements` | 005 | Improvement suggestions / wizard |
| `org_settings` | 006 (+ seeded 027, 031, 033) | Key/value org config |
| `people` | 006 (+ seeded 032) | Team directory |
| `groups` | 006 (+ seeded 032) | Team groups |
| `group_members` | 006 (+ seeded 032) | Group membership join |
| `session_types` | 006 (+ altered 038, seeded 031/039) | Session type catalog |
| `stage_assignees` | 006 (+ altered 040, seeded 043) | Per-type stage assignee matrix |
| `email_templates` | 006, **reshaped 048** (+ seeded 048, 051) | Stage email templates |
| `prompt_templates` | 006, **reshaped 047** (+ altered 049, seeded 047/050) | Prompt / processing templates |
| `chat_messages` | 008 (+ altered 052) | Session chat log |
| `polls` | 008 (+ altered 037, 052) | Session polls |
| `poll_options` | 008 | Poll answer options |
| `templates` | 009 (+ altered 012, seeded 009) | Processing pipeline templates |
| `session_templates` | 009 (+ seeded 028) | Per-session pipeline config |
| `session_audit` | 010 (+ altered 024) | Per-session processing log |
| `session_speakers` | 011 | Manifest-parsed speakers |
| `session_slide_resources` | 011 | Manifest @N resource links |
| `normalization_results` | 012 (+ altered 026) | Normalized segment text |
| `slide_time_ranges` | 013 | Fusion slide time ranges |
| `replay_log` | 013 | Fusion replay record |
| `alignments` | 014 | Segment→slide alignment |
| `validation_results` | 014 | Alignment validation verdicts |
| `words` | 015 | Per-token STT timestamps |
| `bullets` | 016 | Slide bullet text |
| `transcription_discrepancies` | 017 (+ altered 029) | STT vs normalized diff |
| `artifacts` | 018 (+ altered 023) | Generated export artifacts |
| `instructor_profiles` | 019 (+ altered 021) | IIL instructor learning |
| `session_instructor_map` | 019 | Session→instructor link |
| `session_patterns` | 019 | Per-session learned patterns |
| `key_points_annotations` | 019 (+ altered 025, 034) | Key-point extraction |
| `correction_ledger` | 029 | Phase-4 append-only correction ledger |
| `ledger_pointers` | 029 | Undo/redo pointer (1/session) |
| `email_attempts` | 030 | Email send audit trail |
| `session_stage_assignees` | 042 (+ seeded 044) | Per-session stage assignee |
| `auth_users` | 045 | DB-backed login users |
| `help_articles` | 053 (+ updated 056, seeded 055) | Help Center articles |
| `help_article_versions` | 054 | Help article version snapshots |
| `session_locks` | 057 | Concurrent-edit lock (1/session) |

`migrations/000_fix_corrections_collision.sql` is a sort-before-001 hotfix that drops orphaned `corrections` / `correction_pointers` state from a prior failed deploy; it creates no tables ([000_fix_corrections_collision.sql](../../migrations/000_fix_corrections_collision.sql)). `migrations/046_perf_indexes.sql` adds indexes only. `migrations/055_help_articles_seed.sql` is data-only.

---

## sessions

**Created:** [001_init.sql:13](../../migrations/001_init.sql#L13). **Altered:** 010 (status CHECK), 011 (manifest columns), 035 (drop UNIQUE on `code`), 041 (`session_type_id` FK), 046 (perf indexes).

**Purpose:** the root record for one uploaded recording. Everything else hangs off `sessions.id` via FK with `ON DELETE CASCADE`.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `code` | TEXT NOT NULL | human-readable lecture id (e.g. `VIN-2026-001`); **UNIQUE dropped in 035** — multiple sessions may share a code |
| `title` | TEXT NOT NULL | |
| `presenter` | TEXT | |
| `recorded_at` | TIMESTAMPTZ | |
| `duration_sec` | INTEGER | |
| `attendee_count` | INTEGER | |
| `word_count` | INTEGER | |
| `segment_count` | INTEGER | |
| `taxonomy` | JSONB NOT NULL `'[]'` | array of taxonomy strings |
| `status` | TEXT NOT NULL `'ingesting'` | constrained by 010 CHECK (see below) |
| `deleted_at` | TIMESTAMPTZ | soft-delete marker |
| `created_at` / `updated_at` | TIMESTAMPTZ NOT NULL `now()` | |
| `title_long` | TEXT | added 011 — from manifest |
| `title_short` | TEXT | added 011 |
| `ce_broker_id` | TEXT | added 011 |
| `class_id` | TEXT | added 011 |
| `tags` | JSONB NOT NULL `'[]'` | added 011 |
| `publishing_links` | JSONB NOT NULL `'{}'` | added 011 |
| `polls_raw` | TEXT | added 011 — raw manifest poll text |
| `polls_parsed` | JSONB NOT NULL `'[]'` | added 011 |
| `session_type_id` | UUID FK→`session_types(id)` `ON DELETE SET NULL` | added 041; NULL = use org default type |

**Status enum (010 CHECK constraint `sessions_status_check`):** `uploading`, `transcribing`, `normalizing`, `fusing`, `aligning`, `ready`, `complete`, `failed`. Migration 010 normalizes legacy `ingesting`→`uploading` before adding the constraint ([010_state_machine.sql:19](../../migrations/010_state_machine.sql#L19)).

**Indexes:** `sessions_status_idx` (partial, `deleted_at IS NULL`), `sessions_recorded_at_idx` (DESC, partial), `sessions_code_lower_idx` (`lower(code)`), `sessions_code_idx` (035), `sessions_session_type_id_idx` (041), `sessions_created_at_idx` (046, DESC partial), `sessions_title_lower_idx` (046).

**Constraints:** `code` originally UNIQUE (dropped 035); `sessions_status_check` (010).

**Used By Screens:** Dashboard, Sessions list, Session Detail, Editor, Processing, Viewer, SOP, Audit (`DashboardView.vue`, `SessionsView.vue`, `SessionDetailView.vue`, `EditorView.vue`, `ProcessingView.vue`, `ViewerView.vue`, `SopView.vue`, `QueueView.vue`).
**Used By APIs:** `api/sessions.py`, `api/gcs_upload.py`, `api/segments.py`, `api/sop.py`, `api/queue.py`, `api/exports.py`, `api/diagnostics.py`, `api/locks.py`, plus most ingest tasks and `services/session_init.py`.

---

## sources

**Created:** [001_init.sql:36](../../migrations/001_init.sql#L36).

**Purpose:** one row per uploaded artifact for a session (video, slide deck, manifest, supplementary audio).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK→`sessions(id)` CASCADE NOT NULL | |
| `role` | TEXT NOT NULL | `video` \| `slide` \| `manifest` \| `audio_enhance` \| `other` (per inline comment) |
| `filename` | TEXT NOT NULL | |
| `gcs_uri` | TEXT NOT NULL | |
| `content_type` | TEXT | |
| `size_bytes` | BIGINT | |
| `duration_sec` | INTEGER | video/audio only |
| `metadata` | JSONB NOT NULL `'{}'` | |
| `created_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Indexes:** `sources_session_idx`, `sources_session_role_idx`, `sources_gcs_uri_uq` (UNIQUE on `gcs_uri`).
**Constraints:** UNIQUE(`gcs_uri`).

**Used By Screens:** Session Detail (Sources panel), Upload.
**Used By APIs:** `api/gcs_upload.py`, `api/add_to_session.py`, `api/session_resources.py`; ingest tasks (`ingest.py`, `transcribe.py`, `slide_extract.py`, `fusion.py`, etc.).

---

## slides

**Created:** [001_init.sql:54](../../migrations/001_init.sql#L54). **Altered:** 016 (`full_text`, `thumbnail_uri`).

**Purpose:** one row per slide deck page for a session.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK→`sessions(id)` CASCADE NOT NULL | |
| `slide_index` | INTEGER NOT NULL | 0-based |
| `title` | TEXT | |
| `image_uri` | TEXT | GCS path for slide thumb |
| `start_ms` / `end_ms` | INTEGER | inferred from alignment |
| `metadata` | JSONB NOT NULL `'{}'` | |
| `full_text` | TEXT | added 016 |
| `thumbnail_uri` | TEXT | added 016 |

**Indexes:** `slides_session_idx`.
**Constraints:** UNIQUE(`session_id`, `slide_index`).

**Used By Screens:** Editor (slide rail), Viewer, Session Detail.
**Used By APIs:** `api/add_to_session.py`, `api/session_resources.py`; tasks `slide_extract.py`, `align.py`, `fusion.py`, `ingest.py`, `normalize.py`, `kp_task.py`, `finalize.py`; services `extras2_parser.py`, `poll_autoplace.py`.

---

## speakers

**Created:** [001_init.sql:69](../../migrations/001_init.sql#L69).

**Purpose:** runtime AI/STT-detected speakers referenced by `segments.speaker_id`. Distinct from `session_speakers` (manifest-parsed; see below).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK→`sessions(id)` CASCADE NOT NULL | |
| `name` | TEXT NOT NULL | |
| `role` | TEXT | "Instructor", "Q&A", "Moderator", etc. |
| `avatar_color` | TEXT | hex from palette or override |
| `metadata` | JSONB NOT NULL `'{}'` | |

**Indexes:** `speakers_session_idx`. **Constraints:** none beyond PK/FK.

**Used By Screens:** Editor (Speakers panel), Session Detail (Chat Participants).
**Used By APIs:** `api/add_to_session.py`, `api/gcs_upload.py`, `api/session_resources.py`; tasks `ai_process.py`, `align.py`; service `extras2_parser.py`.

---

## segments

**Created:** [001_init.sql:82](../../migrations/001_init.sql#L82). **Altered:** 020 (`content_hash`), 022 (demoted `(session_id, seq)` UNIQUE to plain index).

**Purpose:** one row per transcript segment. The central editable unit of the transcript.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK→`sessions(id)` CASCADE NOT NULL | |
| `slide_id` | UUID FK→`slides(id)` `ON DELETE SET NULL` | |
| `speaker_id` | UUID FK→`speakers(id)` `ON DELETE SET NULL` | |
| `seq` | INTEGER NOT NULL | ordering within session |
| `start_ms` / `end_ms` | INTEGER NOT NULL | |
| `text` | TEXT NOT NULL | |
| `confidence` | REAL | 0..1 |
| `flags` | JSONB NOT NULL `'[]'` | e.g. `["medication","filler"]` |
| `is_anchor` | BOOLEAN NOT NULL FALSE | poll/chat anchor block |
| `anchor_kind` | TEXT | `poll` \| `chat` \| NULL |
| `metadata` | JSONB NOT NULL `'{}'` | |
| `created_at` / `updated_at` | TIMESTAMPTZ NOT NULL `now()` | |
| `content_hash` | TEXT NOT NULL | added 020 — `sha256(session_id + start_ms)` hex; deterministic-id idempotency key |

**Indexes:** `segments_session_idx`, `segments_session_seq_idx`, `segments_session_slide_idx`, `segments_session_speaker_idx`, `segments_session_anchor_idx` (partial `is_anchor = TRUE`), `segments_content_hash_uq` (UNIQUE `session_id`,`content_hash`, 020), `segments_session_seq_idx_v2` (022).
**Constraints:** UNIQUE(`session_id`, `content_hash`) (020). Original UNIQUE(`session_id`, `seq`) **dropped in 022** (collision risk during re-segmentation; uniqueness now lives on `content_hash`).

**Used By Screens:** Editor (transcript pane), Viewer, Session Detail, exports.
**Used By APIs:** `api/segments.py`, `api/corrections.py`, `api/exports.py`, `api/word_alignment.py`, `api/sessions.py`, `api/session_resources.py`, `api/diagnostics.py`; nearly all pipeline tasks; segment services `segment_split.py`, `segment_merge.py`, `segment_inverse.py`.

---

## discrepancies

**Created:** [002_discrepancies.sql:3](../../migrations/002_discrepancies.sql#L3).

**Purpose:** rows shown in the editor's Discrepancies tab, keyed to a segment + slide. Distinct from `transcription_discrepancies` (per-word LCS diff, see 017).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK→`sessions(id)` CASCADE NOT NULL | |
| `segment_id` | UUID FK→`segments(id)` `ON DELETE SET NULL` | |
| `slide_id` | UUID FK→`slides(id)` `ON DELETE SET NULL` | |
| `kind` | TEXT NOT NULL | `medication`\|`name`\|`number`\|`date`\|`terminology`\|`filler`\|`punctuation`\|`style`\|`other` |
| `severity` | TEXT NOT NULL `'flagged'` | `flagged`\|`meaningful`\|`uncertain`\|`drift`\|`low_conf` |
| `ai_text` / `stt_text` | TEXT | |
| `classification` | JSONB NOT NULL `'{}'` | Gemini/Vertex output `{backend, model, confidence,...}` |
| `is_resolved` | BOOLEAN NOT NULL FALSE | |
| `resolved_by` | TEXT | operator email |
| `resolved_at` | TIMESTAMPTZ | |
| `metadata` | JSONB NOT NULL `'{}'` | |
| `created_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Indexes:** `discrepancies_session_idx`, `discrepancies_session_kind_idx`, `discrepancies_open_idx` (partial `NOT is_resolved`). **Constraints:** none beyond PK/FK.

**Used By Screens:** Editor (Discrepancies tab).
**Used By APIs:** `api/discrepancies.py`, `api/corrections.py`, `api/diagnostics.py`; tasks `classify_task.py`, `lcs_discrepancies.py`.

---

## corrections

**Created:** [002_discrepancies.sql:26](../../migrations/002_discrepancies.sql#L26).

**Purpose:** append-only legacy edit-log of every text edit / reassign / speaker change. Coexists with the newer `correction_ledger` (029); per the 029 header, `segments.py`/`audit.py` use both and the legacy schema is preserved verbatim.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK→`sessions(id)` CASCADE NOT NULL | |
| `segment_id` | UUID FK→`segments(id)` `ON DELETE SET NULL` | |
| `actor_email` | TEXT NOT NULL | |
| `kind` | TEXT NOT NULL | `edited`\|`inserted_chat`\|`slide_reassigned`\|`speaker_change`\|`annotation` |
| `was` | JSONB NOT NULL `'{}'` | old state snapshot |
| `now_` | JSONB NOT NULL `'{}'` | new state snapshot (`now` is reserved) |
| `note` | TEXT | |
| `occurred_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Indexes:** `corrections_session_idx` (`session_id`, `occurred_at DESC`), `corrections_segment_idx`. **Constraints:** none beyond PK/FK.

**Used By Screens:** Editor (Audit tab), Audit view.
**Used By APIs:** `api/segments.py`, `api/corrections.py`, `api/audit.py`, `api/exports.py`, `api/locks.py`, `api/session_resources.py`.

---

## sop_state

**Created:** [003_sop.sql:5](../../migrations/003_sop.sql#L5).

**Purpose:** one row per session holding the SOP workflow state machine. Stages per inline comment: `prep · copy_draft · medical · copy_final · cms · captions · qa · complete`.

| Column | Type | Notes |
|---|---|---|
| `session_id` | UUID PK FK→`sessions(id)` CASCADE | |
| `current_stage` | TEXT NOT NULL `'prep'` | |
| `is_blocked` | BOOLEAN NOT NULL FALSE | |
| `blockers` | JSONB NOT NULL `'[]'` | `[{check_id, reason, raised_at}]` |
| `assignees` | JSONB NOT NULL `'{}'` | `{prep:{email,name,role}, ...}` |
| `entered_current_at` | TIMESTAMPTZ NOT NULL `now()` | |
| `sla_target_hours` | JSONB NOT NULL `'{}'` | `{prep:8, copy_draft:24, ...}` |
| `metadata` | JSONB NOT NULL `'{}'` | |
| `updated_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Indexes:** `sop_state_stage_idx`. **Constraints:** PK on `session_id`.

**Used By Screens:** SOP view, Session Detail (Stage Assignments), Dashboard / Queue.
**Used By APIs:** `api/sop.py`, `api/sessions.py`, `api/queue.py`; tasks `sop_tasks.py`, `celery_app.py` (Beat deadline checks).

---

## sop_transitions

**Created:** [003_sop.sql:20](../../migrations/003_sop.sql#L20).

**Purpose:** append-only audit of every SOP stage transition.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK→`sessions(id)` CASCADE NOT NULL | |
| `from_stage` | TEXT | NULL on initial entry |
| `to_stage` | TEXT NOT NULL | |
| `actor_email` | TEXT NOT NULL | |
| `note` | TEXT | |
| `occurred_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Indexes:** `sop_transitions_session_idx` (`session_id`, `occurred_at DESC`).

**Used By Screens:** SOP view.
**Used By APIs:** `api/sop.py`; task `sop_tasks.py`.

---

## sop_checks

**Created:** [003_sop.sql:34](../../migrations/003_sop.sql#L34).

**Purpose:** per-stage acceptance-check rows; each resolved/raised independently.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK→`sessions(id)` CASCADE NOT NULL | |
| `stage` | TEXT NOT NULL | |
| `check_id` | TEXT NOT NULL | e.g. `medical.dosage_review` |
| `label` | TEXT NOT NULL | |
| `is_resolved` | BOOLEAN NOT NULL FALSE | |
| `resolved_by` | TEXT | |
| `resolved_at` | TIMESTAMPTZ | |
| `metadata` | JSONB NOT NULL `'{}'` | |

**Indexes:** `sop_checks_stage_idx`. **Constraints:** UNIQUE(`session_id`, `stage`, `check_id`).

**Used By Screens:** SOP view.
**Used By APIs:** `api/sop.py`.

---

## sop_approvals

**Created:** [003_sop.sql:50](../../migrations/003_sop.sql#L50).

**Purpose:** append-only per-stage sign-off signatures.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK→`sessions(id)` CASCADE NOT NULL | |
| `stage` | TEXT NOT NULL | |
| `actor_email` | TEXT NOT NULL | |
| `signature` | TEXT NOT NULL | arbitrary signoff string |
| `occurred_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Indexes:** `sop_approvals_session_idx`. **Constraints:** none beyond PK/FK.

**Used By Screens:** NOT VERIFIED IN CODE — no `api/`, `tasks/`, or `services/` file references this table in the grep sweep. Table is created but no read/write path was found.

> **RESERVED/UNUSED — resolved 2026-06-10.** Confirmed orphan (zero `app/` references; empty in all environments). Retained for the planned per-stage sign-off feature; labeled in-DB by migration `058`. Do not drop without product sign-off (plan Track C3).
**Used By APIs:** IMPLEMENTATION NOT FOUND — no source reference located.

---

## audit_events

**Created:** [004_audit.sql:3](../../migrations/004_audit.sql#L3).

**Purpose:** global append-only event log for every wired UI action. `session_id` is nullable for non-session events (login, settings).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK→`sessions(id)` `ON DELETE SET NULL` | NULL for global events |
| `actor_email` | TEXT | |
| `kind` | TEXT NOT NULL | e.g. `segment.edit`, `sop.advance`, `settings.save`, `auth.login` |
| `summary` | TEXT | |
| `details` | JSONB NOT NULL `'{}'` | |
| `occurred_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Indexes:** `audit_events_session_idx`, `audit_events_actor_idx`, `audit_events_kind_idx` (all `, occurred_at DESC`).

**Used By Screens:** Audit view, Editor (Audit tab).
**Used By APIs:** Many — `api/audit.py`, `api/sessions.py`, `api/sop.py`, `api/settings.py`, `api/improvements.py`, `api/segments.py`, `api/help.py`, `api/email_templates.py`, `api/gcs_upload.py`, `api/diagnostics.py`, `api/locks.py`, `api/session_resources.py`; tasks `sop_tasks.py`, `align.py`, `help_tasks.py`, `celery_app.py`; services `email.py`, `segment_merge.py`.

---

## improvements

**Created:** [005_improvements.sql:3](../../migrations/005_improvements.sql#L3).

**Purpose:** Improvements master record + 5-step wizard payload (markdown bodies).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `title` | TEXT NOT NULL | |
| `description` | TEXT | |
| `type` | TEXT | `feature`\|`bug`\|`ux`\|etc. |
| `status` | TEXT NOT NULL `'pending'` | `pending`\|`under_review`\|`approved`\|`in_progress`\|`rolled_out`\|`declined`\|`archived` |
| `priority` | TEXT NOT NULL `'medium'` | `low`\|`medium`\|`high`\|`critical` |
| `risk` | TEXT NOT NULL `'low'` | `low`\|`medium`\|`high` |
| `area` | TEXT | `editor`\|`sessions`\|etc. |
| `target_version` | TEXT | |
| `is_security` | BOOLEAN NOT NULL FALSE | |
| `submitted_by` | TEXT NOT NULL | |
| `submitted_at` | TIMESTAMPTZ NOT NULL `now()` | |
| `admin_notes` | TEXT | |
| `requirements_md` | TEXT | wizard step 1 |
| `implementation_md` | TEXT | wizard step 2 |
| `testing_md` | TEXT | wizard step 3 |
| `review_md` | TEXT | wizard step 4 |
| `deleted_at` | TIMESTAMPTZ | soft-delete |
| `updated_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Indexes:** `improvements_status_idx` (partial `deleted_at IS NULL`), `improvements_submitted_at_idx` (DESC, partial).

**Used By Screens:** Improvements view.
**Used By APIs:** `api/improvements.py`; task `help_tasks.py`.

---

## org_settings

**Created:** [006_settings.sql:3](../../migrations/006_settings.sql#L3). **Seeded/updated:** 006 (8 defaults), 027 (flip `upload_backend`→`gcs`, `default_ai_model`→`gemini-2.5-pro`), 033 (reset retired `classify_model`).

**Purpose:** key/value JSONB store for org-wide settings.

| Column | Type | Notes |
|---|---|---|
| `key` | TEXT PK | |
| `value` | JSONB NOT NULL | scalar or object stored as JSONB |
| `updated_by` | TEXT | |
| `updated_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Seeded keys (006):** `org_name`, `default_locale`, `time_zone`, `default_ai_model`, `upload_backend`, `classify_backend`, `classify_model`, `include_key_points`. **Constraints:** PK on `key`.

**Used By Screens:** Settings view.
**Used By APIs:** `api/settings.py`; task `classify_task.py`.

---

## people

**Created:** [006_settings.sql:23](../../migrations/006_settings.sql#L23). **Seeded:** 032 (10 VIN team members).

**Purpose:** team directory (Team & roles section).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `email` | TEXT NOT NULL UNIQUE | |
| `name` | TEXT NOT NULL | |
| `role` | TEXT | "Operator"\|"Editor"\|"Reviewer"\|"Admin" (per comment) — **not** an auth role; see permission note |
| `avatar_color` | TEXT | |
| `is_active` | BOOLEAN NOT NULL TRUE | |
| `created_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Constraints:** UNIQUE(`email`).

**Used By Screens:** Settings (Team & roles), Session Detail / SOP (assignee dropdowns).
**Used By APIs:** `api/settings.py`, `api/sessions.py`.

---

## groups

**Created:** [006_settings.sql:33](../../migrations/006_settings.sql#L33). **Seeded:** 032 (5 groups), 043 (ensures `External`).

**Purpose:** named team groups for stage assignment.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `name` | TEXT NOT NULL UNIQUE | |
| `description` | TEXT | |
| `created_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Constraints:** UNIQUE(`name`).

**Used By Screens:** Settings (Team & roles).
**Used By APIs:** `api/settings.py`, `api/sessions.py`, `api/queue.py`; task `transcribe.py`.

---

## group_members

**Created:** [006_settings.sql:40](../../migrations/006_settings.sql#L40). **Seeded:** 032.

**Purpose:** many-to-many join between `groups` and `people`.

| Column | Type | Notes |
|---|---|---|
| `group_id` | UUID FK→`groups(id)` CASCADE NOT NULL | composite PK |
| `person_id` | UUID FK→`people(id)` CASCADE NOT NULL | composite PK |

**Constraints:** PRIMARY KEY(`group_id`, `person_id`).

**Used By Screens:** Settings (Team & roles).
**Used By APIs:** `api/settings.py`.

---

## session_types

**Created:** [006_settings.sql:47](../../migrations/006_settings.sql#L47). **Altered:** 038 (`is_default` + partial unique index). **Seeded:** 031 / 039 (17 VIN conference rounds).

**Purpose:** catalog of session types; each type drives a stage-assignee matrix.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `code` | TEXT NOT NULL UNIQUE | `default`, `AAFV`, `ABVP`, … (17 seeded) |
| `label` | TEXT NOT NULL | |
| `metadata` | JSONB NOT NULL `'{}'` | |
| `is_default` | BOOLEAN NOT NULL FALSE | added 038; exactly one row TRUE |

**Indexes:** `session_types_is_default_uq` (UNIQUE partial `WHERE is_default = TRUE`, 038).
**Constraints:** UNIQUE(`code`); partial-unique guarantee of one default.

**Used By Screens:** Settings (Types), Upload, Session Detail.
**Used By APIs:** `api/settings.py`, `api/sessions.py`; service `session_init.py`.

---

## stage_assignees

**Created:** [006_settings.sql:54](../../migrations/006_settings.sql#L54). **Altered:** 040 (`person_id`, `group_id` typed FKs + single-assignee CHECK). **Seeded:** 043 (Carla matrix).

**Purpose:** per-type, per-stage default assignee matrix. New sessions copy from this matrix into `session_stage_assignees` at ingest.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `type_id` | UUID FK→`session_types(id)` CASCADE NOT NULL | |
| `stage` | TEXT NOT NULL | one of the 8 SOP stages |
| `assignee_email` | TEXT NOT NULL | legacy free-text (person email or `Group: <name>`) |
| `notify_email` | BOOLEAN NOT NULL TRUE | |
| `person_id` | UUID FK→`people(id)` `ON DELETE SET NULL` | added 040 |
| `group_id` | UUID FK→`groups(id)` `ON DELETE SET NULL` | added 040 |

**Indexes:** `stage_assignees_person_idx`, `stage_assignees_group_idx` (040).
**Constraints:** UNIQUE(`type_id`, `stage`); CHECK `chk_stage_assignees_single_assignee` — `person_id IS NULL OR group_id IS NULL` (040).

**Used By Screens:** Settings (Stage assignee matrix).
**Used By APIs:** `api/settings.py`, `api/sessions.py`; service `session_init.py`.

---

## email_templates

**Created (legacy schema):** [006_settings.sql:64](../../migrations/006_settings.sql#L64). **Reshaped (DROP + CREATE):** [048_email_templates.sql:21](../../migrations/048_email_templates.sql#L21). **Seeded:** 048 (8 stage defaults), 051 (7 `_overdue` variants).

**Purpose (current / 048 schema):** per-Type × per-Stage × per-locale stage-notification HTML email templates. A NULL `session_type_id` row is the default-for-all-types fallback.

> The original 006 schema (`type_id`, `stage`, `subject`, `body_html`, `body_text`, `variables_used`, `enabled`, `updated_by`, `updated_at`) was empty in production and is fully replaced by 048's `DROP TABLE IF EXISTS email_templates CASCADE`. Document the **048 schema** as live.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_type_id` | UUID FK→`session_types(id)` CASCADE | NULL = applies to every Type |
| `stage_id` | TEXT NOT NULL | `prep`\|`copy_draft`\|`medical`\|…\|`complete`; also `<stage>_overdue` variants (051) |
| `locale` | TEXT NOT NULL `'en-US'` | |
| `subject` | TEXT NOT NULL | supports `{{ var }}` substitution |
| `body` | TEXT NOT NULL | HTML |
| `is_active` | BOOLEAN NOT NULL TRUE | soft-delete via FALSE |
| `created_by` | TEXT | |
| `created_at` / `updated_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Indexes:** `email_templates_type_stage_locale_uq` (UNIQUE on `COALESCE(session_type_id::text,'_default_')`, `stage_id`, `locale`), `email_templates_stage_active_idx` (partial), `email_templates_type_active_idx` (partial).
**Constraints:** unique-per-(type-or-default, stage, locale) via the COALESCE index.

**Used By Screens:** Settings (Email templates / EmailBuilder), Email debug.
**Used By APIs:** `api/email_templates.py`, `api/settings.py`, `api/email_debug.py`, `api/help.py`; task `sop_tasks.py` (resolves `<stage>_overdue` for deadline emails).

---

## prompt_templates

**Created (legacy schema):** [006_settings.sql:101](../../migrations/006_settings.sql#L101). **Reshaped (DROP + CREATE):** [047_prompt_templates.sql:28](../../migrations/047_prompt_templates.sql#L28). **Altered:** 049 (`default_for_mode` + CHECK + partial unique). **Seeded:** 047 (6 processing + 2 ai_prompt), 050 (verbatim MIC transcript prompt into the `Transcript` row).

**Purpose (current / 047 schema):** Settings prompt-template catalog. One table for two kinds via JSONB `config`.

> The 006 legacy schema (`name`, `category`, `icon`, `description`, `system_prompt`, `iil_config`, `type`, `updated_at`) was empty in production and is fully replaced by 047's `DROP TABLE IF EXISTS prompt_templates CASCADE`. Document the **047 schema** as live.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `kind` | TEXT NOT NULL | `processing` \| `ai_prompt` |
| `name` | TEXT NOT NULL | unique on `lower(name)` |
| `icon` | TEXT NOT NULL `'📝'` | |
| `description` | TEXT | |
| `category` | TEXT NOT NULL `'Custom'` | `Education`\|`Technical`\|`Conversational`\|`Business`\|`Custom` |
| `config` | JSONB NOT NULL `'{}'` | processing: filler/tone/terminology/etc.; ai_prompt: `{system_prompt}` |
| `is_system` | BOOLEAN NOT NULL FALSE | system rows can be duplicated, not deleted |
| `is_active` | BOOLEAN NOT NULL TRUE | soft-delete |
| `version` | INTEGER NOT NULL 1 | |
| `created_by` | TEXT | |
| `created_at` / `updated_at` | TIMESTAMPTZ NOT NULL `now()` | |
| `default_for_mode` | TEXT | added 049; `transcript`\|`summary`\|`key-moments`\|`structured-notes` (CHECK) — binds a template to an upload ai_mode |

**Indexes:** `prompt_templates_kind_active_idx` (partial), `prompt_templates_name_uq` (UNIQUE `lower(name)`), `prompt_templates_system_idx` (partial), `prompt_templates_default_for_mode_uq` (049, UNIQUE partial — one default per mode), `prompt_templates_default_mode_lookup_idx` (049).
**Constraints:** `prompt_templates_default_for_mode_chk` CHECK (049).

**Used By Screens:** Settings (Prompt templates), Upload (mode selection).
**Used By APIs:** `api/settings.py`; task `ai_process.py` (`app/prompts.py::get_prompt_for_mode` reads `default_for_mode` on each Gemini call per 049 header).

---

## chat_messages

**Created:** [008_chat_polls.sql:7](../../migrations/008_chat_polls.sql#L7). **Altered:** 052 (`order_index`).

**Purpose:** session chat log; backs the editor right-rail Chat tab and inline anchor blocks.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK→`sessions(id)` CASCADE NOT NULL | |
| `author` | TEXT NOT NULL | |
| `body` | TEXT NOT NULL | |
| `sent_at_ms` | INTEGER NOT NULL | ms offset from session start |
| `anchor_segment` | UUID FK→`segments(id)` `ON DELETE SET NULL` | |
| `placed` | BOOLEAN NOT NULL FALSE | |
| `metadata` | JSONB NOT NULL `'{}'` | |
| `created_at` | TIMESTAMPTZ NOT NULL `now()` | |
| `order_index` | INTEGER | added 052; NULL = use `sent_at_ms` order |

**Indexes:** `chat_messages_session_idx`, `chat_messages_anchor_idx`, `chat_messages_session_sent_idx` (046), `chat_messages_order_idx` (052, partial `order_index IS NOT NULL`, built CONCURRENTLY).

**Used By Screens:** Editor (Chat tab / anchor blocks), Session Detail.
**Used By APIs:** `api/add_to_session.py`, `api/gcs_upload.py`, `api/session_resources.py`.

---

## polls

**Created:** [008_chat_polls.sql:23](../../migrations/008_chat_polls.sql#L23). **Altered:** 037 (backfill `anchor_segment`/`placed`), 052 (`order_index`).

**Purpose:** session polls; backs the editor right-rail Polls tab.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK→`sessions(id)` CASCADE NOT NULL | |
| `question` | TEXT NOT NULL | |
| `opened_at_ms` | INTEGER NOT NULL | |
| `closed_at_ms` | INTEGER | |
| `status` | TEXT NOT NULL `'open'` | `open`\|`closed` |
| `total_votes` | INTEGER NOT NULL 0 | |
| `anchor_segment` | UUID FK→`segments(id)` `ON DELETE SET NULL` | |
| `placed` | BOOLEAN NOT NULL FALSE | |
| `metadata` | JSONB NOT NULL `'{}'` | may carry `slide_n` (1-based) used by auto-placement |
| `created_at` | TIMESTAMPTZ NOT NULL `now()` | |
| `order_index` | INTEGER | added 052 |

**Indexes:** `polls_session_idx`, `polls_order_idx` (052, partial, CONCURRENTLY).

**Used By Screens:** Editor (Polls tab).
**Used By APIs:** `api/add_to_session.py`, `api/gcs_upload.py`, `api/session_resources.py`, `api/diagnostics.py`; tasks `ai_process.py`, `finalize.py`; services `extras2_parser.py`, `poll_autoplace.py`.

---

## poll_options

**Created:** [008_chat_polls.sql:40](../../migrations/008_chat_polls.sql#L40).

**Purpose:** answer options for a poll.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `poll_id` | UUID FK→`polls(id)` CASCADE NOT NULL | |
| `label` | TEXT NOT NULL | |
| `seq` | INTEGER NOT NULL | |
| `votes` | INTEGER NOT NULL 0 | |

**Indexes:** `poll_options_poll_idx`. **Constraints:** UNIQUE(`poll_id`, `seq`).

**Used By Screens:** Editor (Polls tab).
**Used By APIs:** `api/gcs_upload.py`, `api/session_resources.py`.

---

## templates

**Created:** [009_session_templates.sql:8](../../migrations/009_session_templates.sql#L8). **Altered:** 012 (`filler_words` + backfill). **Seeded:** 009 (5 templates), 012 (filler word arrays).

**Purpose:** processing-template catalog referenced by `session_templates.template_id`.

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PK | e.g. `lecture_v1` |
| `name` | TEXT NOT NULL | |
| `filler_policy` | TEXT NOT NULL `'medium'` | `light`\|`medium`\|`strict` |
| `structure_extraction` | TEXT NOT NULL `'on'` | `on`\|`off` |
| `key_points` | TEXT NOT NULL `'on'` | `on`\|`off` |
| `tone` | TEXT NOT NULL `'neutral'` | `formal`\|`neutral`\|`conversational` |
| `terminology` | TEXT NOT NULL `'medium'` | `low`\|`medium`\|`high` |
| `rewrite` | TEXT NOT NULL `'minimal'` | `minimal`\|`moderate`\|`aggressive` |
| `filler_words` | JSONB NOT NULL `'[]'` | (also re-declared/backfilled in 012) |
| `created_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Seeded ids:** `lecture_v1`, `training_v1`, `technical_v1`, `podcast_v1`, `sales_v1`. **Constraints:** PK on `id`.

**Used By Screens:** Settings, Upload (pipeline config). NOT VERIFIED IN CODE which exact screen renders these vs. the 047 `prompt_templates` catalog.
**Used By APIs:** `api/settings.py`, `api/email_templates.py`, `api/email_debug.py`; tasks `ai_process.py`, `normalize.py`, `kp_task.py`, `sop_tasks.py`.

---

## session_templates

**Created:** [009_session_templates.sql:32](../../migrations/009_session_templates.sql#L32). **Seeded/updated:** 009 (backfill existing sessions), 028 (`gemini-2.5-flash`→`gemini-2.5-pro`).

**Purpose:** one row per session capturing the pipeline routing chosen at upload.

| Column | Type | Notes |
|---|---|---|
| `session_id` | UUID PK FK→`sessions(id)` CASCADE | |
| `ai_pipeline` | TEXT NOT NULL `'enhanced'` | `direct`\|`enhanced` |
| `ai_mode` | TEXT NOT NULL `'transcript'` | `transcript`\|`summary`\|`key-moments`\|`structured-notes`\|`custom-prompt` |
| `ai_model` | TEXT NOT NULL `'gemini-2.5-pro'` | |
| `prompt_mode` | TEXT NOT NULL `'transcript'` | |
| `custom_prompt` | TEXT | |
| `stt_backend` | TEXT NOT NULL `'google_latest_long'` | |
| `template_id` | TEXT NOT NULL `'lecture_v1'` FK→`templates(id)` | |
| `iil_config` | JSONB NOT NULL `'{"enabled":true,"tier1":true,"tier2":true,"tier3":true}'` | |
| `auto_detected_template_id` | TEXT FK→`templates(id)` | |
| `auto_detected_confidence` | REAL | |
| `created_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Indexes:** `session_templates_template_idx`. **Constraints:** PK on `session_id`; FKs to `templates`.

**Used By Screens:** Upload, Editor (pipeline config), Processing.
**Used By APIs:** `api/sessions.py`; tasks `ai_process.py`, `align.py`, `classify_task.py`, `ingest.py`, `kp_task.py`, `normalize.py`.

---

## session_audit

**Created:** [010_state_machine.sql:31](../../migrations/010_state_machine.sql#L31). **Altered:** 024 (`finalized_at`).

**Purpose:** one row per session; `processing_log` JSONB accumulates `{ts, prev, next, actor, reason}` entries for the pipeline state machine.

| Column | Type | Notes |
|---|---|---|
| `session_id` | UUID PK FK→`sessions(id)` CASCADE | |
| `processing_log` | JSONB NOT NULL `'[]'` | append-only log array |
| `updated_at` | TIMESTAMPTZ NOT NULL `now()` | |
| `finalized_at` | TIMESTAMPTZ | added 024; set when session reaches ready |

**Indexes:** `session_audit_updated_idx` (DESC), `session_audit_finalized_idx` (024, partial, DESC).

**Used By Screens:** Processing, Session Detail (ready timestamp).
**Used By APIs:** `api/sessions.py`, `api/diagnostics.py`; task `upload_watchdog.py`.

---

## session_speakers

**Created:** [011_manifest.sql:22](../../migrations/011_manifest.sql#L22).

**Purpose:** speakers parsed from the manifest, independent of the runtime `speakers` table.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK→`sessions(id)` CASCADE NOT NULL | |
| `role` | TEXT NOT NULL | `moderator`\|`primary`\|`guest` |
| `name` | TEXT NOT NULL | |
| `credentials` | TEXT | |
| `bio` | TEXT | |
| `sort_order` | INTEGER NOT NULL 0 | |
| `created_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Indexes:** `session_speakers_session_idx` (`session_id`, `sort_order`). **Constraints:** none beyond PK/FK.

**Used By Screens:** Session Detail / Editor (speaker bios). NOT VERIFIED IN CODE which exact panel renders bios.
**Used By APIs:** `api/add_to_session.py`, `api/gcs_upload.py`; tasks `kp_task.py`, `sop_tasks.py`.

---

## session_slide_resources

**Created:** [011_manifest.sql:36](../../migrations/011_manifest.sql#L36).

**Purpose:** `@N`-anchored resource links from the manifest's Additional Resources block.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK→`sessions(id)` CASCADE NOT NULL | |
| `slide_number` | INTEGER NOT NULL | |
| `label` | TEXT | |
| `url` | TEXT NOT NULL | |
| `sort_order` | INTEGER NOT NULL 0 | |
| `created_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Indexes:** `session_slide_resources_session_idx` (`session_id`, `slide_number`). **Constraints:** none beyond PK/FK.

**Used By Screens:** Editor / Viewer (slide resource links). NOT VERIFIED IN CODE which exact view renders these.
**Used By APIs:** `api/add_to_session.py`, `api/gcs_upload.py`.

---

## normalization_results

**Created:** [012_normalize.sql:21](../../migrations/012_normalize.sql#L21). **Altered:** 026 (`repair_applied`, `repair_attempts`).

**Purpose:** normalized (IIL/template-rewritten) text for each segment.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK→`sessions(id)` CASCADE NOT NULL | |
| `segment_id` | UUID FK→`segments(id)` CASCADE NOT NULL | |
| `normalized_text` | TEXT NOT NULL | |
| `template_id` | TEXT FK→`templates(id)` NOT NULL | |
| `validation_results` | JSONB NOT NULL `'{}'` | MIC-style `check1..check4` = `pass`\|`fail`\|`repaired` (026 comment) |
| `created_at` | TIMESTAMPTZ NOT NULL `now()` | |
| `repair_applied` | BOOLEAN NOT NULL FALSE | added 026 |
| `repair_attempts` | INTEGER NOT NULL 0 | added 026 |

**Indexes:** `normalization_session_idx`, `normalization_results_repair_idx` (026, partial `repair_applied`), `normalization_results_raw_fallback_idx` (026, partial `repair_attempts = 2 AND repair_applied = FALSE`).
**Constraints:** UNIQUE(`session_id`, `segment_id`).

**Used By Screens:** Editor (raw-fallback flag chip). NOT VERIFIED IN CODE exact UI element.
**Used By APIs:** `api/segments.py`, `api/corrections.py`; tasks `normalize.py`, `align.py`, `kp_task.py`, `lcs_discrepancies.py`.

---

## slide_time_ranges

**Created:** [013_fusion.sql:6](../../migrations/013_fusion.sql#L6).

**Purpose:** fusion-engine slide time-range output per session.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK→`sessions(id)` CASCADE NOT NULL | |
| `slide_id` | UUID FK→`slides(id)` CASCADE | |
| `start_time` / `end_time` | REAL NOT NULL | |
| `slide_soft_start` / `slide_soft_end` | REAL NOT NULL | |
| `confidence` | REAL NOT NULL CHECK 0..1 | |
| `sources` | JSONB NOT NULL | `{visual, anchor, semantic}` contributions |
| `status` | TEXT NOT NULL | |
| `attempt_number` | INTEGER NOT NULL 1 | |
| `created_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Indexes:** `slide_time_ranges_session_idx` (`session_id`, `start_time`). **Constraints:** CHECK `confidence >= 0.0 AND <= 1.0`.

**Used By Screens:** none directly — backend fusion artifact. NOT VERIFIED IN CODE that any view reads this.
**Used By APIs:** none. **Used by tasks:** `fusion.py`, `align.py`.

---

## replay_log

**Created:** [013_fusion.sql:23](../../migrations/013_fusion.sql#L23).

**Purpose:** append-only fusion replay record (determinism/replay audit per locked-weights rule).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK→`sessions(id)` CASCADE NOT NULL | |
| `input_hash` | TEXT NOT NULL | |
| `fusion_inputs` | JSONB NOT NULL | |
| `fusion_output` | JSONB NOT NULL | |
| `created_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Indexes:** `replay_log_session_idx` (`session_id`, `created_at DESC`).

**Used By Screens:** none. **Used By APIs:** none. **Used by tasks:** `fusion.py`.

---

## alignments

**Created:** [014_align.sql:6](../../migrations/014_align.sql#L6).

**Purpose:** per-segment alignment to a slide with confidence + signal breakdown.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK→`sessions(id)` CASCADE NOT NULL | |
| `segment_id` | UUID FK→`segments(id)` CASCADE NOT NULL | |
| `slide_id` | UUID FK→`slides(id)` | (no cascade clause) |
| `confidence` | REAL NOT NULL CHECK 0..1 | |
| `signals` | JSONB NOT NULL | `{semantic, coverage, temporal, sequential}` |
| `sources` | JSONB NOT NULL | `{visual, anchor, semantic}` pass-through |
| `drift_flag` | BOOLEAN NOT NULL FALSE | |
| `anchor_hit` | BOOLEAN NOT NULL FALSE | |
| `uncertain_flag` | BOOLEAN NOT NULL FALSE | |
| `status` | TEXT NOT NULL CHECK | `assigned`\|`uncertain`\|`review` |
| `attempt_number` | INTEGER NOT NULL 1 | |
| `created_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Indexes:** `alignments_session_idx`, `alignments_session_seg_idx`, `alignments_uncertain_idx` (partial `uncertain_flag`).
**Constraints:** UNIQUE(`session_id`, `segment_id`); CHECK on `confidence`; CHECK on `status`.

**Used By Screens:** Editor (drift/uncertain chips). NOT VERIFIED IN CODE exact element.
**Used By APIs:** `api/corrections.py`; tasks `align.py`, `ai_process.py`, `finalize.py`, `kp_task.py`, `lcs_discrepancies.py`; services `segment_inverse.py`, `segment_merge.py`.

---

## validation_results

**Created:** [014_align.sql:27](../../migrations/014_align.sql#L27).

**Purpose:** validation verdict per alignment row.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `alignment_id` | UUID FK→`alignments(id)` CASCADE NOT NULL | |
| `verdict` | TEXT NOT NULL CHECK | `APPROVE`\|`REVIEW`\|`ESCALATE` |
| `details` | JSONB NOT NULL `'{}'` | |
| `created_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Constraints:** CHECK on `verdict`. (No FK index declared.)

> Note: `normalize.py` and `kp_task.py` also reference the string `validation_results`, but `normalization_results.validation_results` is a JSONB **column** (012), distinct from this table. This table is keyed to `alignment_id`.

**Used By Screens:** none directly. **Used By APIs:** none. **Used by tasks:** `align.py` (writer); `kp_task.py`/`normalize.py` references may target the JSONB column rather than this table — NOT FULLY VERIFIED.

---

## words

**Created:** [015_words.sql:10](../../migrations/015_words.sql#L10).

**Purpose:** per-token STT timestamps + confidence within a segment.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `segment_id` | UUID FK→`segments(id)` CASCADE NOT NULL | |
| `seq` | INTEGER NOT NULL | ordering within segment |
| `word` | TEXT NOT NULL | |
| `start_ms` / `end_ms` | INTEGER NOT NULL | |
| `confidence` | REAL NOT NULL `0.85` CHECK 0..1 | |

**Indexes:** `words_segment_idx`. **Constraints:** UNIQUE(`segment_id`, `seq`); CHECK on `confidence`.

**Used By Screens:** Editor / Viewer (per-word highlight via `word_alignment`).
**Used By APIs:** `api/sessions.py`, `api/session_resources.py`; tasks `transcribe.py`, `ai_process.py`, `normalize.py`, `lcs_discrepancies.py`, `burn_captions.py`, `help_tasks.py`.

---

## bullets

**Created:** [016_bullets.sql:9](../../migrations/016_bullets.sql#L9).

**Purpose:** extracted bullet lines per slide.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `slide_id` | UUID FK→`slides(id)` CASCADE NOT NULL | |
| `text` | TEXT NOT NULL | |
| `position` | INTEGER NOT NULL | |
| `created_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Indexes:** `bullets_slide_idx` (`slide_id`, `position`). **Constraints:** UNIQUE(`slide_id`, `position`).

**Used By Screens:** Editor / Viewer (slide bullets). NOT VERIFIED IN CODE exact element.
**Used By APIs:** none directly. **Used by tasks:** `slide_extract.py`, `align.py`, `ingest.py`, `kp_task.py`, `normalize.py`.

---

## transcription_discrepancies

**Created:** [017_discrepancies_full.sql:9](../../migrations/017_discrepancies_full.sql#L9). **Altered:** 029 (`resolved`, `resolution_correction_id` FK→`correction_ledger`, `resolved_at`).

**Purpose:** per-segment LCS-detected diff between raw STT and normalized text. Distinct from `discrepancies` (002).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK→`sessions(id)` CASCADE NOT NULL | |
| `segment_id` | UUID FK→`segments(id)` CASCADE | |
| `ai_text` | TEXT | normalized version |
| `stt_text` | TEXT | raw STT version |
| `category` | TEXT | `medication`\|`terminology`\|`filler`\|`punctuation`\|`drift`\|`low_confidence`\|`other` |
| `is_meaningful` | BOOLEAN | NULL until classify runs |
| `classifier_model` | TEXT | |
| `classified_at` | TIMESTAMPTZ | |
| `created_at` | TIMESTAMPTZ NOT NULL `now()` | |
| `resolved` | BOOLEAN NOT NULL FALSE | added 029 |
| `resolution_correction_id` | UUID FK→`correction_ledger(id)` `ON DELETE SET NULL` | added 029 |
| `resolved_at` | TIMESTAMPTZ | added 029 |

**Indexes:** `transcription_discrepancies_session_idx`, `transcription_discrepancies_unclassified_idx` (partial `is_meaningful IS NULL`), `transcription_discrepancies_unresolved_idx` (029, partial `resolved = FALSE`).

**Used By Screens:** Editor (Discrepancies tab).
**Used By APIs:** `api/discrepancies.py`, `api/corrections.py`; tasks `lcs_discrepancies.py`, `classify_task.py`, `ai_process.py`.

---

## artifacts

**Created:** [018_artifacts.sql:6](../../migrations/018_artifacts.sql#L6). **Altered:** 023 (`version`, `is_current`, `style_config`; dropped UNIQUE(`session_id`,`kind`); added partial unique-current index).

**Purpose:** generated export files per session, now versioned.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK→`sessions(id)` CASCADE NOT NULL | |
| `kind` | TEXT NOT NULL | `docx`\|`srt`\|`vtt`\|`txt`\|`zip`\|`captioned_video` (+ `html` per Help content) |
| `gcs_uri` | TEXT | |
| `bytes` | BIGINT | |
| `generated_by` | TEXT | |
| `generated_at` | TIMESTAMPTZ NOT NULL `now()` | |
| `version` | INTEGER NOT NULL 1 | added 023 |
| `is_current` | BOOLEAN NOT NULL TRUE | added 023 |
| `style_config` | JSONB NOT NULL `'{}'` | added 023 |

**Indexes:** `artifacts_session_idx`, `artifacts_unique_current_idx` (UNIQUE partial `is_current = TRUE`, 023), `artifacts_session_kind_version_idx` (023, `version DESC`).
**Constraints:** original UNIQUE(`session_id`, `kind`) **dropped in 023**; replaced by unique-current-per-kind partial index.

**Used By Screens:** Editor / Session Detail (Export menu).
**Used By APIs:** `api/exports.py`, `api/session_resources.py`; task `burn_captions.py`.

---

## instructor_profiles

**Created:** [019_iil_learning.sql:5](../../migrations/019_iil_learning.sql#L5). **Altered:** 021 (`filler_words`, `avg_compression_ratio`).

**Purpose:** IIL (instructor-informed learning) profile accumulated across sessions.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `name` | TEXT NOT NULL UNIQUE | |
| `credentials` | TEXT | |
| `bio` | TEXT | |
| `avg_filler_rate` | REAL | |
| `avg_session_min` | INTEGER | |
| `preferred_template_id` | TEXT FK→`templates(id)` | |
| `sample_count` | INTEGER NOT NULL 0 | |
| `created_at` / `updated_at` | TIMESTAMPTZ NOT NULL `now()` | |
| `filler_words` | JSONB NOT NULL `'[]'` | added 021 |
| `avg_compression_ratio` | REAL | added 021 |

**Indexes:** `instructor_profiles_name_lower_idx` (`lower(name)`). **Constraints:** UNIQUE(`name`).

**Used By Screens:** none directly. NOT VERIFIED IN CODE that any view reads instructor profiles.
**Used By APIs:** none. **Used by tasks:** `kp_task.py`.

---

## session_instructor_map

**Created:** [019_iil_learning.sql:19](../../migrations/019_iil_learning.sql#L19).

**Purpose:** links a session to its matched instructor profile.

| Column | Type | Notes |
|---|---|---|
| `session_id` | UUID PK FK→`sessions(id)` CASCADE | |
| `instructor_id` | UUID FK→`instructor_profiles(id)` NOT NULL | |
| `matched_by` | TEXT NOT NULL | `manifest`\|`manual`\|`auto` |
| `confidence` | REAL NOT NULL 1.0 | |
| `created_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Constraints:** PK on `session_id`; FK to `instructor_profiles`.

**Used By Screens:** none directly. **Used By APIs:** none. **Used by tasks:** `kp_task.py`.

---

## session_patterns

**Created:** [019_iil_learning.sql:27](../../migrations/019_iil_learning.sql#L27).

**Purpose:** per-session learned pattern counts (IIL).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK→`sessions(id)` CASCADE NOT NULL | |
| `pattern_name` | TEXT NOT NULL | |
| `frequency` | INTEGER NOT NULL 1 | |
| `metadata` | JSONB NOT NULL `'{}'` | |
| `created_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Indexes:** `session_patterns_session_idx`. **Constraints:** UNIQUE(`session_id`, `pattern_name`).

**Used By Screens:** Improvements view (suggestion patterns) — NOT VERIFIED IN CODE that the Improvements UI reads this exact table vs. `improvements`.
**Used By APIs:** none. **Used by tasks:** `kp_task.py`.

---

## key_points_annotations

**Created:** [019_iil_learning.sql:37](../../migrations/019_iil_learning.sql#L37). **Altered:** 025 (`key_points`, `explanation`, `available`, `extraction_confidence`; `label`/`score` made nullable), 034 (non-partial unique index).

**Purpose:** key-point extraction per segment.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK→`sessions(id)` CASCADE NOT NULL | |
| `segment_id` | UUID FK→`segments(id)` CASCADE | |
| `label` | TEXT | NOT NULL originally; **made nullable in 025** |
| `score` | REAL `0.5` | legacy, kept for back-compat |
| `metadata` | JSONB NOT NULL `'{}'` | |
| `created_at` | TIMESTAMPTZ NOT NULL `now()` | |
| `key_points` | JSONB NOT NULL `'[]'` | added 025 — array, max 5 items |
| `explanation` | TEXT NOT NULL `''` | added 025 |
| `available` | BOOLEAN NOT NULL FALSE | added 025 — FALSE → UI shows "not available" |
| `extraction_confidence` | REAL NOT NULL 0.0 | added 025 |

**Indexes:** `key_points_annotations_session_idx`, `key_points_annotations_unique` (025 created partial → **034 replaced with non-partial** UNIQUE(`session_id`, `segment_id`) so `ON CONFLICT` works).
**Constraints:** UNIQUE(`session_id`, `segment_id`) (034).

**Used By Screens:** Editor / Viewer (key points). NOT VERIFIED IN CODE exact element.
**Used By APIs:** none directly. **Used by tasks:** `kp_task.py`; services `segment_split.py`, `segment_merge.py`, `segment_inverse.py`.

---

## correction_ledger

**Created:** [029_corrections.sql:88](../../migrations/029_corrections.sql#L88).

**Purpose:** Phase-4 MIC-parity append-only correction ledger (UPDATE/DELETE forbidden by design). Coexists with the legacy `corrections` table (002).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK→`sessions(id)` CASCADE NOT NULL | |
| `segment_id` | UUID FK→`segments(id)` CASCADE NOT NULL | |
| `correction_type` | TEXT NOT NULL CHECK | enum below |
| `old_slide_id` | UUID FK→`slides(id)` `ON DELETE SET NULL` | |
| `new_slide_id` | UUID FK→`slides(id)` `ON DELETE SET NULL` | |
| `old_text` / `new_text` | TEXT | |
| `applied_by` | TEXT NOT NULL `'operator'` | |
| `applied_at` | TIMESTAMPTZ NOT NULL `now()` | |
| `action_id` | UUID NOT NULL | groups multiple ledger rows into one undoable action |
| `sequence_number` | INTEGER NOT NULL | |

**`correction_type` CHECK enum:** `slide_reassignment`, `text_edit`, `split`, `merge`, `mark_ok`, `chat_insert`, `chat_edit`, `chat_remove`, `poll_insert`, `poll_remove`, `speaker_reassignment`.

**Indexes:** `correction_ledger_session_idx`, `correction_ledger_session_seq_idx`, `correction_ledger_session_action_idx`, `correction_ledger_segment_idx`.
**Constraints:** CHECK `correction_ledger_type_enum`.

**Used By Screens:** Editor (undo/redo + Audit tab).
**Used By APIs:** `api/corrections.py`, `api/segments.py`, `api/audit.py`, `api/exports.py`; service `segment_inverse.py`.

---

## ledger_pointers

**Created:** [029_corrections.sql:132](../../migrations/029_corrections.sql#L132).

**Purpose:** one row per session tracking the undo/redo pointer into `correction_ledger`.

| Column | Type | Notes |
|---|---|---|
| `session_id` | UUID PK FK→`sessions(id)` CASCADE | |
| `current_pointer` | INTEGER NOT NULL `-1` | -1 = before first action |
| `updated_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Constraints:** PK on `session_id`.

**Used By Screens:** Editor (undo/redo state).
**Used By APIs:** `api/corrections.py`, `api/segments.py`, `api/audit.py`.

---

## email_attempts

**Created:** [030_email_attempts.sql:16](../../migrations/030_email_attempts.sql#L16).

**Purpose:** audit trail for every email send attempt (stage-notify, debug-test, template-test).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `attempted_at` | TIMESTAMPTZ NOT NULL `now()` | |
| `from_address` | TEXT NOT NULL | |
| `to_address` | TEXT NOT NULL | |
| `subject` | TEXT | |
| `trigger` | TEXT NOT NULL CHECK | `stage_notification`\|`debug_test`\|`template_test` |
| `sop_session_id` | UUID FK→`sessions(id)` `ON DELETE SET NULL` | |
| `stage` | TEXT | |
| `result` | TEXT NOT NULL CHECK | `sent`\|`failed` |
| `error_code` | TEXT | |
| `error_message` | TEXT | |
| `latency_ms` | INTEGER | |
| `smtp_log` | TEXT | raw SMTP wire log |
| `operator_email` | TEXT | |

**Indexes:** `email_attempts_attempted_at_idx` (DESC), `email_attempts_to_address_idx`, `email_attempts_session_idx`, `email_attempts_result_idx`.
**Constraints:** CHECK `chk_email_attempts_result`, CHECK `chk_email_attempts_trigger`.

**Used By Screens:** Settings (Email debug).
**Used By APIs:** `api/email_debug.py`.

---

## session_stage_assignees

**Created:** [042_session_stage_assignees.sql:20](../../migrations/042_session_stage_assignees.sql#L20). **Seeded:** 044 (backfill from each session's type matrix).

**Purpose:** per-session, per-stage assignee shown in the editor Admin chip + SOP stepper. Copied from the chosen Type's `stage_assignees` matrix at ingest; operators can override per stage.

| Column | Type | Notes |
|---|---|---|
| `session_id` | UUID FK→`sessions(id)` CASCADE NOT NULL | composite PK |
| `stage` | TEXT NOT NULL | composite PK |
| `person_id` | UUID FK→`people(id)` `ON DELETE SET NULL` | |
| `group_id` | UUID FK→`groups(id)` `ON DELETE SET NULL` | |
| `notify_email` | BOOLEAN NOT NULL TRUE | |
| `source` | TEXT NOT NULL `'manual'` | `default` (auto from type matrix) \| `manual` (operator override) |
| `assigned_by` | TEXT | |
| `assigned_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Indexes:** `session_stage_assignees_person_idx`, `session_stage_assignees_group_idx`.
**Constraints:** PRIMARY KEY(`session_id`, `stage`); CHECK `chk_session_stage_assignees_single_assignee` — `person_id IS NULL OR group_id IS NULL`.

**Used By Screens:** Editor (Admin chip), SOP view, Session Detail (Stage Assignments).
**Used By APIs:** `api/sessions.py`, `api/diagnostics.py`; service `session_init.py`.

---

## auth_users

**Created:** [045_auth_users.sql:11](../../migrations/045_auth_users.sql#L11).

**Purpose:** DB-backed login users with bcrypt-hashed passwords. Seeded at boot from the `AUTH_USERS` env CSV if the table is empty (per migration header).

> Permission reality: the `role` column exists but is **NOT read by `get_current_user`**. Runtime admin gating is the hardcoded `johndean@vin.com` (`LEGACY_ADMIN_EMAIL`) check, not this column. See `app/security/roles.py` (scaffold, unwired).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `email` | TEXT NOT NULL | unique on `lower(email)` |
| `password_hash` | TEXT NOT NULL | bcrypt `$2b$…` |
| `role` | TEXT NOT NULL `'user'` | `admin`\|`user` — **stored but not enforced at runtime** |
| `is_active` | BOOLEAN NOT NULL TRUE | |
| `last_login_at` | TIMESTAMPTZ | |
| `password_reset_at` | TIMESTAMPTZ | last admin-initiated reset |
| `created_at` / `updated_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Indexes:** `auth_users_email_lower_uq` (UNIQUE `lower(email)`), `auth_users_active_idx` (partial `is_active = TRUE`).
**Constraints:** unique on `lower(email)`.

**Used By Screens:** Login, Settings (Auth Users management — admin gated by `LEGACY_ADMIN_EMAIL`).
**Used By APIs:** `api/settings.py`, `api/diagnostics.py`, `api/help.py`; service `auth_users.py`; task `help_tasks.py`.

---

## help_articles

**Created:** [053_help_articles.sql:20](../../migrations/053_help_articles.sql#L20). **Seeded:** 055 (~70 articles). **Updated:** 056 (3-step procedural bodies + version bumps).

**Purpose:** Help Center articles backing the admin CMS surface and the in-app Help panel.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `slug` | TEXT NOT NULL UNIQUE | stable seed identifier (e.g. `editor-user-0`) |
| `title` | TEXT NOT NULL | |
| `summary` | TEXT NOT NULL `''` | |
| `category` | TEXT NOT NULL `'general'` | |
| `audience` | TEXT NOT NULL `'users'` | |
| `feature_tags` | JSONB NOT NULL `'[]'` | |
| `steps` | JSONB NOT NULL `'[]'` | array of `{title, body}` step objects |
| `related_article_ids` | JSONB NOT NULL `'[]'` | |
| `display_order` | INTEGER NOT NULL 0 | |
| `is_published` | BOOLEAN NOT NULL FALSE | |
| `content_domain` | TEXT NOT NULL `'general'` | |
| `workflow_slug` | TEXT | |
| `version` | INTEGER NOT NULL 1 | bumped on each edit |
| `last_edited_by` | TEXT NOT NULL `''` | |
| `created_at` / `updated_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Indexes:** `help_articles_published_idx`, `help_articles_content_domain_idx`, `help_articles_audience_idx`, `help_articles_feature_tags_gin_idx` (GIN), `help_articles_domain_order_idx`.
**Constraints:** UNIQUE(`slug`).

**Used By Screens:** Help panel / Help Center, Settings (Help article CMS — admin gated).
**Used By APIs:** `api/help.py`; task `help_tasks.py` (bulk-AI authoring).

---

## help_article_versions

**Created:** [054_help_article_versions.sql:22](../../migrations/054_help_article_versions.sql#L22).

**Purpose:** append-only version snapshots of `help_articles`. Each PATCH snapshots prior state here before applying. There is no DELETE path (restore is a fresh PATCH).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `article_id` | UUID FK→`help_articles(id)` CASCADE NOT NULL | |
| `version` | INTEGER NOT NULL | |
| `snapshot` | JSONB NOT NULL | full prior article state |
| `edited_by` | TEXT NOT NULL `''` | |
| `edited_at` | TIMESTAMPTZ NOT NULL `now()` | |

**Indexes:** `help_article_versions_article_edited_at_idx` (`article_id`, `edited_at DESC`).
**Constraints:** UNIQUE(`article_id`, `version`).

**Used By Screens:** Settings / Help CMS (Version History dialog — admin gated).
**Used By APIs:** `api/help.py`; task `help_tasks.py`.

---

## session_locks

**Created:** [057_session_locks.sql:14](../../migrations/057_session_locks.sql#L14).

**Purpose:** one row per session actively being edited, to prevent silent concurrent-edit overwrites. Heartbeat keeps the lock alive (TTL 90s = 3 missed heartbeats); stale locks can be force-taken.

| Column | Type | Notes |
|---|---|---|
| `session_id` | UUID PK | (no FK declared in migration) |
| `user_email` | TEXT NOT NULL | |
| `acquired_at` | TIMESTAMPTZ NOT NULL `now()` | |
| `heartbeat_at` | TIMESTAMPTZ NOT NULL `now()` | |
| `expires_at` | TIMESTAMPTZ NOT NULL `now() + 90s` | |

**Indexes:** `idx_session_locks_expires_at` (stale-lock sweep helper, not UNIQUE).
**Constraints:** PK on `session_id`. Note: `session_id` has **no foreign key** to `sessions` in this migration (verified — only PK declared).

> **Accepted by design — resolved 2026-06-10.** The missing FK is low-impact: lock rows are ephemeral (90s TTL, swept) and the app only writes existing session IDs, so the worst case is a stale row that self-expires. Every sibling SOP table cascades, so optional CASCADE-FK hardening (`DELETE` orphans → `NOT VALID` → `VALIDATE`) is available as plan Track C2 — **opt-in, not applied.**

**Used By Screens:** Editor (concurrent-edit lock banner).
**Used By APIs:** `api/locks.py`.

---

## Cross-cutting notes

- **Two `corrections`-family schemas coexist:** legacy `corrections` (002, edit-log: `actor_email`/`kind`/`was`/`now_`/`occurred_at`) and `correction_ledger` (029, MIC-parity: `correction_type`/`action_id`/`sequence_number`). Both are referenced by `api/segments.py`, `api/corrections.py`, `api/audit.py`. The 029 header states they intentionally coexist.
- **Two discrepancy tables:** `discrepancies` (002, editor tab, segment+slide keyed) vs `transcription_discrepancies` (017, per-segment STT-vs-normalized diff). Not interchangeable.
- **Two speaker tables:** `speakers` (001, runtime AI/STT, referenced by `segments.speaker_id`) vs `session_speakers` (011, manifest-parsed bios).
- **Two reshaped tables:** `email_templates` and `prompt_templates` each had a legacy 006 schema fully dropped and recreated (048 / 047 respectively). Only the post-reshape schema is live.
- **JSONB `validation_results` appears in two places:** as a column on `normalization_results` (012) and as a table name (014). They are distinct.

## Source Verification
- **Files Used:** [migrations/000_fix_corrections_collision.sql](../../migrations/000_fix_corrections_collision.sql), [001_init.sql](../../migrations/001_init.sql), [002_discrepancies.sql](../../migrations/002_discrepancies.sql), [003_sop.sql](../../migrations/003_sop.sql), [004_audit.sql](../../migrations/004_audit.sql), [005_improvements.sql](../../migrations/005_improvements.sql), [006_settings.sql](../../migrations/006_settings.sql), [008_chat_polls.sql](../../migrations/008_chat_polls.sql), [009_session_templates.sql](../../migrations/009_session_templates.sql), [010_state_machine.sql](../../migrations/010_state_machine.sql), [011_manifest.sql](../../migrations/011_manifest.sql), [012_normalize.sql](../../migrations/012_normalize.sql), [013_fusion.sql](../../migrations/013_fusion.sql), [014_align.sql](../../migrations/014_align.sql), [015_words.sql](../../migrations/015_words.sql), [016_bullets.sql](../../migrations/016_bullets.sql), [017_discrepancies_full.sql](../../migrations/017_discrepancies_full.sql), [018_artifacts.sql](../../migrations/018_artifacts.sql), [019_iil_learning.sql](../../migrations/019_iil_learning.sql), [020_segment_content_hash.sql](../../migrations/020_segment_content_hash.sql), [021_iil_features.sql](../../migrations/021_iil_features.sql), [022_segment_seq_index.sql](../../migrations/022_segment_seq_index.sql), [023_artifact_versions.sql](../../migrations/023_artifact_versions.sql), [024_session_audit_finalized.sql](../../migrations/024_session_audit_finalized.sql), [025_kp_annotations_kp04.sql](../../migrations/025_kp_annotations_kp04.sql), [026_validation_repair_columns.sql](../../migrations/026_validation_repair_columns.sql), [027_default_gcs_upload_backend.sql](../../migrations/027_default_gcs_upload_backend.sql), [028_session_templates_default_pro.sql](../../migrations/028_session_templates_default_pro.sql), [029_corrections.sql](../../migrations/029_corrections.sql), [030_email_attempts.sql](../../migrations/030_email_attempts.sql), [031_seed_settings_types.sql](../../migrations/031_seed_settings_types.sql), [032_seed_people_and_groups.sql](../../migrations/032_seed_people_and_groups.sql), [033_fix_deprecated_classify_model.sql](../../migrations/033_fix_deprecated_classify_model.sql), [034_fix_kp_annotations_unique.sql](../../migrations/034_fix_kp_annotations_unique.sql), [035_drop_sessions_code_unique.sql](../../migrations/035_drop_sessions_code_unique.sql), [036_word_alignment.sql](../../migrations/036_word_alignment.sql), [037_backfill_poll_anchors.sql](../../migrations/037_backfill_poll_anchors.sql), [038_session_types_is_default.sql](../../migrations/038_session_types_is_default.sql), [039_seed_session_types.sql](../../migrations/039_seed_session_types.sql), [040_stage_assignees_typed_fk.sql](../../migrations/040_stage_assignees_typed_fk.sql), [041_session_type_link.sql](../../migrations/041_session_type_link.sql), [042_session_stage_assignees.sql](../../migrations/042_session_stage_assignees.sql), [043_seed_carla_matrix.sql](../../migrations/043_seed_carla_matrix.sql), [044_backfill_session_stage_assignees.sql](../../migrations/044_backfill_session_stage_assignees.sql), [045_auth_users.sql](../../migrations/045_auth_users.sql), [046_perf_indexes.sql](../../migrations/046_perf_indexes.sql), [047_prompt_templates.sql](../../migrations/047_prompt_templates.sql), [048_email_templates.sql](../../migrations/048_email_templates.sql), [049_prompt_templates_default_for_mode.sql](../../migrations/049_prompt_templates_default_for_mode.sql), [050_seed_mic_transcript_prompt.sql](../../migrations/050_seed_mic_transcript_prompt.sql), [051_email_templates_overdue_seeds.sql](../../migrations/051_email_templates_overdue_seeds.sql), [052_chat_polls_order_index.sql](../../migrations/052_chat_polls_order_index.sql), [053_help_articles.sql](../../migrations/053_help_articles.sql), [054_help_article_versions.sql](../../migrations/054_help_article_versions.sql), [055_help_articles_seed.sql](../../migrations/055_help_articles_seed.sql), [056_help_articles_steps_content.sql](../../migrations/056_help_articles_steps_content.sql), [057_session_locks.sql](../../migrations/057_session_locks.sql). Table→source cross-reference via grep over `app/api/`, `app/tasks/`, `app/services/`.
- **Components Used:** none (frontend `views/*.vue` filenames confirmed via glob; specific data-binding within each view NOT line-verified — "Used By Screens" rows are inferred from migration comments + view names and tagged where uncertain).
- **APIs Used:** `app/api/` modules: sessions, gcs_upload, segments, corrections, audit, sop, queue, settings, discrepancies, improvements, exports, email_templates, email_debug, word_alignment, add_to_session, session_resources, help, locks, diagnostics, auth.
- **Database Tables Used:** all 48 tables created/altered across migrations 001–057 (catalog above).
- **Permission Logic Used:** JWT presence + hardcoded `LEGACY_ADMIN_EMAIL` (`johndean@vin.com`) gate (`app/api/sessions.py`, `app/api/help.py`, `app/api/diagnostics.py`); `auth_users.role` + `app/security/roles.py` exist but are unwired. No table-level role enforcement.
- **Confidence Score:** High — every table/column/type/index/constraint is transcribed directly from the migration SQL; "Used By APIs" is grep-verified. "Used By Screens" is the only inferred field and is tagged where uncertain.
- **Evidence Links:** [001_init.sql:13](../../migrations/001_init.sql#L13) (sessions), [010_state_machine.sql:21](../../migrations/010_state_machine.sql#L21) (status CHECK), [029_corrections.sql:88](../../migrations/029_corrections.sql#L88) (correction_ledger enum), [047_prompt_templates.sql:28](../../migrations/047_prompt_templates.sql#L28) + [048_email_templates.sql:21](../../migrations/048_email_templates.sql#L21) (reshaped tables), [045_auth_users.sql:11](../../migrations/045_auth_users.sql#L11) (role column unwired).
