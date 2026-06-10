# Data Model Reference (condensed) — rounds.vin

A demo-AI pointer to the full schema. The authoritative document is
[`docs/data/data-dictionary.md`](../docs/data/data-dictionary.md) — every table,
column, type, index, and constraint there is transcribed directly from the SQL
in [`migrations/`](../migrations/) (48 tables across migrations 001–057). There
is **no ORM** — the `.sql` migrations, applied in filename order by
`scripts/migrate.py`, are the source of truth.

This file is the minimum a demo AI needs: the core entities, how they relate,
and the few "gotchas" that trip people up. For anything not here, read the full
dictionary.

> **Permission reality (applies to every table):** authorization at runtime is
> JWT presence + a hardcoded `johndean@vin.com` (`LEGACY_ADMIN_EMAIL`) gate. The
> `auth_users.role` column (migration 045) exists but is **not read** by
> `get_current_user` — no table is protected by a role tier
> ([app/security/roles.py:10-19](../app/security/roles.py#L10)).

---

## The spine: a session and what hangs off it

`sessions` is the root. Almost every other table FKs to `sessions(id)` with
`ON DELETE CASCADE`.

```
sessions (id)
├── sources                    one row per uploaded file (video/slide/manifest/chat/...)
├── slides ── bullets          slide deck pages + extracted bullet lines
├── speakers                   runtime AI/STT-detected speakers (segments.speaker_id → here)
├── session_speakers           manifest-parsed speaker bios (SEPARATE from speakers)
├── segments ── words          transcript segments + per-token STT timestamps
│     ├── alignments ── validation_results   segment→slide alignment + verdicts
│     ├── normalization_results              IIL/template-rewritten text
│     ├── transcription_discrepancies        per-segment STT-vs-normalized LCS diff
│     ├── correction_ledger / ledger_pointers  append-only edits + undo/redo pointer
│     └── key_points_annotations             key-point extraction
├── chat_messages              session chat (can anchor to a segment)
├── polls ── poll_options      session polls (can anchor to a segment)
├── sop_state                  SOP workflow state (1 row per session)
│     ├── sop_transitions      append-only stage moves
│     ├── sop_checks           per-stage acceptance checks
│     └── sop_approvals        sign-offs (CREATED BUT UNWIRED — see below)
├── session_templates          pipeline routing chosen at upload (1 row per session)
├── session_audit              processing_log state-machine history (1 row per session)
├── session_stage_assignees    per-session stage assignees (from the Type matrix)
├── artifacts                  generated export files (versioned)
└── session_locks              concurrent-edit lock (1 row per session; NO FK to sessions)

audit_events                   global append-only UI-action log (session_id nullable)
```

---

## Core tables a demo AI should know

| Table | One-line role | Key fields | Full entry |
|---|---|---|---|
| `sessions` | Root record per recording | `code`, `title`, `status`, `session_type_id`, `deleted_at` | [data-dictionary.md → sessions](../docs/data/data-dictionary.md) |
| `sources` | Uploaded files | `role` (video/slide/manifest/chat/audio_enhance/other), `gcs_uri` (UNIQUE) | sources |
| `segments` | The editable transcript unit | `seq`, `start_ms`/`end_ms`, `text`, `confidence`, `flags`, `speaker_id`, `slide_id` | segments |
| `speakers` | Runtime speakers | `name`, `role`, `avatar_color` | speakers |
| `slides` | Deck pages | `slide_index`, `image_uri`, `start_ms`/`end_ms`, `full_text` | slides |
| `transcription_discrepancies` | What the Discrepancies tab reads | `ai_text`, `stt_text`, `category`, `is_meaningful` | transcription_discrepancies |
| `correction_ledger` | Append-only edits (undo/redo) | `correction_type`, `old_text`/`new_text`, `action_id`, `sequence_number` | correction_ledger |
| `ledger_pointers` | Undo/redo pointer | `current_pointer` (-1 = before first action) | ledger_pointers |
| `sop_state` | Workflow state machine | `current_stage`, `is_blocked`, `assignees`, `sla_target_hours` | sop_state |
| `session_templates` | Pipeline routing | `ai_pipeline`, `ai_mode`, `ai_model`, `stt_backend`, `template_id`, `iil_config` | session_templates |
| `artifacts` | Export files | `kind`, `bytes`, `version`, `is_current` | artifacts |
| `session_locks` | Single-editor lock | `user_email`, `expires_at` (TTL 90s) | session_locks |
| `audit_events` | Global action log | `kind`, `summary`, `details`, `actor_email` | audit_events |
| `auth_users` | Login users | `email`, `password_hash` (bcrypt), `role` (**stored, not enforced**), `is_active` | auth_users |

---

## Enumerations worth memorizing

- **`sessions.status`** (migration 010 CHECK): `uploading`, `transcribing`,
  `normalizing`, `fusing`, `aligning`, `ready`, `complete`, `failed`.
- **SOP stages** (`sop_state.current_stage`): `prep`, `copy_draft`, `medical`,
  `copy_final`, `cms`, `captions`, `qa`, `complete` — advanced forward-only one
  at a time ([app/api/sop.py:24](../app/api/sop.py#L24)).
- **`correction_ledger.correction_type`** (CHECK enum):
  `slide_reassignment`, `text_edit`, `split`, `merge`, `mark_ok`,
  `chat_insert`, `chat_edit`, `chat_remove`, `poll_insert`, `poll_remove`,
  `speaker_reassignment`.
- **Discrepancy `category`**: `medication`, `terminology`, `filler`,
  `punctuation`, `drift`, `low_confidence`, `other`.
- **`session_templates.ai_mode`**: `transcript`, `summary`, `key-moments`,
  `structured-notes`, `custom-prompt`. **`ai_pipeline`**: `direct`, `enhanced`.

---

## Gotchas — duplicate / lookalike tables

These trip up anyone new to the schema (full notes in the dictionary's
"Cross-cutting notes"):

1. **Two correction systems coexist:** legacy `corrections` (002) and
   `correction_ledger` (029). The ledger backs undo/redo and the captions ETag;
   both are written today, by design.
2. **Two discrepancy tables:** `discrepancies` (002, used to back the endpoint,
   now effectively dead) vs `transcription_discrepancies` (017, what the
   endpoint actually reads). Not interchangeable.
3. **Two speaker tables:** `speakers` (runtime, referenced by
   `segments.speaker_id`) vs `session_speakers` (manifest-parsed bios).
4. **Two reshaped tables:** `email_templates` (006 schema dropped → 048) and
   `prompt_templates` (006 → 047). Only the post-reshape schema is live.
5. **`validation_results` is both a column and a table:** a JSONB column on
   `normalization_results` (012) AND a separate table keyed to `alignment_id`
   (014).
6. **Created-but-unwired:** `sop_approvals` has no read/write path found in
   `app/` ("IMPLEMENTATION NOT FOUND" in the dictionary); `slide_time_ranges`
   and `replay_log` are backend fusion artifacts with no UI read path.
7. **`session_locks.session_id` has no FK** to `sessions` (PK only — verified in
   migration 057).

---

## Where data enters and exits (cross-reference to flows)

- **Ingest writes:** `sources`, `session_speakers`, `polls`/`poll_options`,
  `chat_messages`, `session_slide_resources` via
  `POST /v1/gcs/upload-complete` ([app/api/gcs_upload.py:110-219](../app/api/gcs_upload.py#L110)).
  Pipeline tasks then populate `segments`, `words`, `slides`, `alignments`,
  `normalization_results`, `transcription_discrepancies`, `artifacts`.
- **Editor reads/writes:** `segments` (read), `correction_ledger` +
  `ledger_pointers` (write), `session_locks` (lock), `audit_events` (log).
- **Workflow:** `sop_state` / `sop_transitions` / `sop_checks` /
  `session_stage_assignees`.
- See [common-demo-scenarios.md](common-demo-scenarios.md) for the step-by-step
  flows and [known-limitations.md](known-limitations.md) for the unwired pieces.

---

## Source Verification
- **Files Used:** `docs/data/data-dictionary.md` (the condensed-from source), `migrations/001_init.sql`, `migrations/010_state_machine.sql`, `migrations/017_discrepancies_full.sql`, `migrations/029_corrections.sql`, `migrations/045_auth_users.sql`, `migrations/057_session_locks.sql`, `app/api/sop.py`, `app/api/gcs_upload.py`, `app/api/sessions.py`, `app/security/roles.py`
- **Components Used:** none (frontend view filenames are referenced only via the flow docs)
- **APIs Used:** `POST /v1/gcs/upload-complete`, `GET /v1/sessions/{id}/segments`, `POST /v1/sessions/{id}/corrections`, `GET/POST /v1/sessions/{id}/sop` (for the enum + flow cross-references)
- **Database Tables Used:** the core set — `sessions`, `sources`, `slides`, `bullets`, `speakers`, `session_speakers`, `segments`, `words`, `alignments`, `validation_results`, `normalization_results`, `transcription_discrepancies`, `discrepancies`, `correction_ledger`, `ledger_pointers`, `corrections`, `key_points_annotations`, `chat_messages`, `polls`, `poll_options`, `sop_state`, `sop_transitions`, `sop_checks`, `sop_approvals`, `session_templates`, `session_audit`, `session_stage_assignees`, `artifacts`, `session_locks`, `audit_events`, `auth_users`, `email_templates`, `prompt_templates` (full 48-table catalog in the dictionary)
- **Permission Logic Used:** JWT presence + `LEGACY_ADMIN_EMAIL` gate; `auth_users.role` unwired
- **Confidence Score:** High — this is a faithful condensation of the code-verified data dictionary; all enums/relationships were re-checked against the migration excerpts and the SOP/corrections routers.
- **Evidence Links:** [docs/data/data-dictionary.md](../docs/data/data-dictionary.md), [migrations/029_corrections.sql:88](../migrations/029_corrections.sql#L88), [migrations/045_auth_users.sql:11](../migrations/045_auth_users.sql#L11), [app/api/sop.py:24](../app/api/sop.py#L24), [migrations/057_session_locks.sql:14](../migrations/057_session_locks.sql#L14)
