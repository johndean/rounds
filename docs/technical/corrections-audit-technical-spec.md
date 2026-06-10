# Corrections & Audit — Technical Spec

> Module key: `corrections-audit`. Backend: [app/api/corrections.py](../../app/api/corrections.py),
> [app/api/audit.py](../../app/api/audit.py), the three segment services, and `app/engines/diff.py`.
> Frontend: `AuditView.vue`, `AuditLedger.vue`, `AuditTabInline.vue`, `DecisionCard.vue`.

## Architecture

The module is a thin FastAPI layer over raw SQL (`sqlalchemy.text`) plus three
stateless service modules. There is no ORM model layer; every query is hand-written
parameterized SQL against an `AsyncSession` (`DbSession`).

```
Editor (Vue) ──HTTP──> /v1/sessions/{id}/corrections        ┐
              ──HTTP──> /v1/sessions/{id}/find-replace       │  app/api/corrections.py
              ──HTTP──> /v1/sessions/{id}/corrections/undo   │  (router prefix /v1/sessions)
              ──HTTP──> /v1/sessions/{id}/corrections/redo   │
              ──HTTP──> /v1/sessions/{id}/review-queue       ┘
                              │
              split/merge ────┼──> app/services/segment_split.py  (execute_split / invert_split)
                              ├──> app/services/segment_merge.py  (execute_merge / invert_merge)
                              └──> app/services/segment_inverse.py (undo/redo replay dispatch)
                              │
                              ├──> app/services/db_locks.py  (pg advisory locks)
                              └──> app/engines/ws_bridge      (best-effort WS publish)

Audit (Vue) ──HTTP──> /v1/audit                              ┐  app/api/audit.py
            ──HTTP──> /v1/audit/sessions/{id}/corrections     ┘  (router prefix /v1/audit)
```

Routers are registered in [app/main.py:218](../../app/main.py#L218) (corrections) and
[app/main.py:224](../../app/main.py#L224) (audit).

Two storage models coexist:
- **`correction_ledger` + `ledger_pointers`** — the Phase 4 append-only ledger
  with pointer-based undo/redo (created in migration 029).
- **`audit_events`** — a flat system-wide append log (migration 004).

## Frontend Components

| Component | Role | Key source |
|---|---|---|
| `AuditView.vue` | Global vs per-session WTC screen; mode chosen by presence of `id` prop | [frontend/src/views/AuditView.vue:46](../../frontend/src/views/AuditView.vue#L46) |
| `EditorAuditView.vue` | Wrapper that injects the `id` prop into `AuditView` | [frontend/src/views/EditorAuditView.vue:7-14](../../frontend/src/views/EditorAuditView.vue#L7-L14) |
| `AuditLedger.vue` | Shared table renderer (Time/Type/Segment/Actor/Delta/Note) | [frontend/src/components/audit/AuditLedger.vue:41-82](../../frontend/src/components/audit/AuditLedger.vue#L41-L82) |
| `AuditTabInline.vue` | Editor Audit tab: Decisions/Ledger toggle + CSV export | [frontend/src/components/editor/AuditTabInline.vue:35-60](../../frontend/src/components/editor/AuditTabInline.vue#L35-L60) |
| `DecisionCard.vue` | WAS/NOW two-panel card with word-level diff for text edits | [frontend/src/components/editor/DecisionCard.vue:54-94](../../frontend/src/components/editor/DecisionCard.vue#L54-L94) |
| `SegmentText.vue` | Issues split/merge calls + maps structural error codes | [frontend/src/components/editor/SegmentText.vue:314-411](../../frontend/src/components/editor/SegmentText.vue#L314-L411) |

Data fetch:
- Session WTC: `Promise.all([sessionsApi.get(id), auditApi.corrections(id)])`
  ([frontend/src/views/AuditView.vue:57-62](../../frontend/src/views/AuditView.vue#L57-L62)).
- Global feed: `auditApi.list({ limit: 500 })`, then adapted to the `Correction`
  shape ([frontend/src/views/AuditView.vue:66-79](../../frontend/src/views/AuditView.vue#L66-L79)).
- API client surface lives in [frontend/src/services/api.ts:508-600](../../frontend/src/services/api.ts#L508-L600) (corrections)
  and [frontend/src/services/api.ts:941-945](../../frontend/src/services/api.ts#L941-L945) (audit).

## Backend Services

### `app/api/corrections.py`
The router (prefix `/v1/sessions`, tag `corrections`) and the heart of the module.
Notable internal helpers:
- `_is_noop_correction` — short-circuits text/slide-unchanged corrections
  ([app/api/corrections.py:74-86](../../app/api/corrections.py#L74-L86)).
- `_ensure_pointer` — UPSERTs the `ledger_pointers` row (default `-1`)
  ([app/api/corrections.py:132-150](../../app/api/corrections.py#L132-L150)).
- `_next_seq` — takes a `FOR UPDATE` lock on the pointer row to serialize all
  ledger writes, then returns `MAX(sequence_number)+1`
  ([app/api/corrections.py:153-185](../../app/api/corrections.py#L153-L185)).
- `_truncate_redo_tail` — DELETEs rows past the pointer
  ([app/api/corrections.py:188-198](../../app/api/corrections.py#L188-L198)).
- `_materialize_segments_for_session` — replays latest `text_edit` per segment
  into `segments.text` up to a given pointer ([app/api/corrections.py:211-245](../../app/api/corrections.py#L211-L245)).
- `_replay_existing` — `action_id` idempotency: returns the cached response for a
  prior split/merge, reconstructing the original response shape from the stored
  invert payload ([app/api/corrections.py:262-328](../../app/api/corrections.py#L262-L328)).

### `app/services/segment_split.py`
`execute_split` locks the segment `FOR UPDATE`, computes `split_ms` from word
alignment timing (falling back to proportional position), rebuilds the two text
halves by whitespace tokenization, shifts later segments' `seq` up by 1, INSERTs
the new right-half segment with a UUID-mixed `content_hash`, reparents
`word_alignment` (resequencing `gemini_idx`), and clones any `key_points_annotations`
row. Returns `{affected_segment_ids, invert_payload}`
([app/services/segment_split.py:22-216](../../app/services/segment_split.py#L22-L216)). `invert_split` reverses it
([app/services/segment_split.py:219-261](../../app/services/segment_split.py#L219-L261)).

### `app/services/segment_merge.py`
`execute_merge` locks left, finds the right neighbor via row-value comparison
`(seq, start_ms) > (left_seq, left_start_ms) ORDER BY seq, start_ms LIMIT 1`,
validates expected id / same speaker / not anchor, concatenates text, unions flags,
reparents `word_alignment`, merges `key_points_annotations` (cap 5), DELETEs right,
and returns `{affected_segment_ids, deleted_segment_id, invert_payload}`
([app/services/segment_merge.py:23-279](../../app/services/segment_merge.py#L23-L279)). `invert_merge` re-inserts the
deleted right row and rolls left back ([app/services/segment_merge.py:282-389](../../app/services/segment_merge.py#L282-L389)).

### `app/services/segment_inverse.py`
Undo/redo dispatch. Reads the JSON invert payload off `correction_ledger.new_text`
and drives symmetric raw-SQL mutations. `apply_inverse_for_correction` →
`invert_split`/`invert_merge`; `apply_forward_for_correction` → `_redo_split`/
`_redo_merge` (re-execution does NOT call back into the executors to avoid
re-validating a mutated DB) ([app/services/segment_inverse.py:46-201](../../app/services/segment_inverse.py#L46-L201)).

### `app/engines/diff.py`
LCS word-diff used at ingest by `lcs_discrepancies_task` (not called directly by
this module's routes). `diff_words` emits per-word delete/insert/replace `WordDiff`
entries; `align_words` emits one `WordPair` per Gemini token for word-highlight
anchoring ([app/engines/diff.py:67-171](../../app/engines/diff.py#L67-L171)). The discrepancies it produces are
what `text_edit`/`mark_ok` later auto-resolve.

### `app/api/audit.py`
Two read-only endpoints. `list_events` builds a dynamic `WHERE` over
`session_id`/`actor_email`/`kind` with `limit`/`offset` against `audit_events`
([app/api/audit.py:18-42](../../app/api/audit.py#L18-L42)). `list_corrections` reads `correction_ledger`
filtered by the undo pointer and maps to the editor's
`{id,t,type,actor,seg,prior,next,note}` shape ([app/api/audit.py:45-83](../../app/api/audit.py#L45-L83)).

## APIs

| Method | Path | Body / params | Returns | Source |
|---|---|---|---|---|
| POST | `/v1/sessions/{id}/corrections` | `CorrectionRequest` | correction row (or `noop`/`stale`/`deduped` variants) | [corrections.py:332-454](../../app/api/corrections.py#L332-L454) |
| POST | `/v1/sessions/{id}/find-replace` | `FindReplaceRequest` | matches + inserted corrections | [corrections.py:653-828](../../app/api/corrections.py#L653-L828) |
| GET | `/v1/sessions/{id}/corrections` | — | `{current_pointer, corrections[]}` | [corrections.py:832-879](../../app/api/corrections.py#L832-L879) |
| POST | `/v1/sessions/{id}/corrections/undo` | — | `{pointer}` (or `nothing_to_undo`) | [corrections.py:883-924](../../app/api/corrections.py#L883-L924) |
| POST | `/v1/sessions/{id}/corrections/redo` | — | `{pointer}` (or `nothing_to_redo`) | [corrections.py:928-974](../../app/api/corrections.py#L928-L974) |
| GET | `/v1/sessions/{id}/review-queue` | — | `{count, items[]}` priority-sorted | [corrections.py:978-1033](../../app/api/corrections.py#L978-L1033) |
| GET | `/v1/audit` | `session_id?, actor?, kind?, limit=100, offset=0` | `audit_events[]` | [audit.py:18-42](../../app/api/audit.py#L18-L42) |
| GET | `/v1/audit/sessions/{id}/corrections` | `limit=200` | active corrections (editor shape) | [audit.py:45-83](../../app/api/audit.py#L45-L83) |

`CorrectionRequest` fields: `segment_id`, `correction_type`, `old_slide_id`,
`new_slide_id`, `old_text`, `new_text`, `action_id`, `after_word_index`,
`expected_right_segment_id`, `expected_content_hash`
([app/api/corrections.py:90-112](../../app/api/corrections.py#L90-L112)).

`/v1/audit` caps `limit` at 500; `/v1/audit/sessions/{id}/corrections` caps at 1000
([app/api/audit.py:27](../../app/api/audit.py#L27), [app/api/audit.py:69](../../app/api/audit.py#L69)).

## Data Models

### `correction_ledger` ([migrations/029_corrections.sql:88-129](../../migrations/029_corrections.sql#L88-L129))
`id`, `session_id` (FK CASCADE), `segment_id` (FK CASCADE), `correction_type`
(TEXT + CHECK enum of 11 types), `old_slide_id`/`new_slide_id` (FK SET NULL),
`old_text`, `new_text`, `applied_by` (default `'operator'`), `applied_at`,
`action_id` (NOT NULL), `sequence_number` (NOT NULL). Indexes on `session_id`,
`(session_id, sequence_number)`, `(session_id, action_id)`, `segment_id`.

> Note: structural ops store their JSON invert payload in `new_text`
> ([app/api/corrections.py:408-409](../../app/api/corrections.py#L408-L409)); `segment_inverse._parse_payload` reads it
> back ([app/services/segment_inverse.py:35-43](../../app/services/segment_inverse.py#L35-L43)).

### `ledger_pointers` ([migrations/029_corrections.sql:132-136](../../migrations/029_corrections.sql#L132-L136))
`session_id` (PK, FK CASCADE), `current_pointer` (INT, default `-1`), `updated_at`.

### `audit_events` ([migrations/004_audit.sql:3-15](../../migrations/004_audit.sql#L3-L15))
`id`, `session_id` (FK SET NULL, NULLable for non-session events), `actor_email`,
`kind` (NOT NULL), `summary`, `details` (JSONB default `{}`), `occurred_at`.
Indexes on `(session_id, occurred_at DESC)`, `(actor_email, occurred_at DESC)`,
`(kind, occurred_at DESC)`.

### `transcription_discrepancies` (augmented by migration 029)
Gains `resolved BOOL`, `resolution_correction_id` (FK → `correction_ledger`,
SET NULL), `resolved_at`, plus a partial index on unresolved rows
([migrations/029_corrections.sql:143-152](../../migrations/029_corrections.sql#L143-L152)).

### Migration ordering hazard (resolved)
`000_fix_corrections_collision.sql` sorts before `001` and cleans up partial state
from an earlier 029 that collided with migration 002's legacy `corrections` table:
it drops a Phase-4-shaped `corrections` table, an orphan `correction_pointers`
table, and stale discrepancy columns ([migrations/000_fix_corrections_collision.sql:26-76](../../migrations/000_fix_corrections_collision.sql#L26-L76)).
029 repeats the same cleanup defensively ([migrations/029_corrections.sql:26-80](../../migrations/029_corrections.sql#L26-L80)).
Migration 002 still creates the **legacy** `corrections` table
(`actor_email/kind/was/now_/occurred_at`) which this module no longer reads
([migrations/002_discrepancies.sql:26-39](../../migrations/002_discrepancies.sql#L26-L39)).

## Events

WebSocket events are published best-effort via `_emit_ws` (wraps
`app.engines.ws_bridge.publish_ws_event_sync`, never raises)
([app/api/corrections.py:123-129](../../app/api/corrections.py#L123-L129)):

| Event `type` | When | Source |
|---|---|---|
| `correction_applied` | after any single correction / find-replace / split / merge | [corrections.py:438-443](../../app/api/corrections.py#L438-L443), [corrections.py:624-629](../../app/api/corrections.py#L624-L629), [corrections.py:810-815](../../app/api/corrections.py#L810-L815) |
| `correction_applied` (action_id `"undo"`/`"redo"`) | after pointer move | [corrections.py:923](../../app/api/corrections.py#L923), [corrections.py:973](../../app/api/corrections.py#L973) |
| `discrepancy_resolved` | when a `text_edit`/`mark_ok` closes a discrepancy | [corrections.py:630-634](../../app/api/corrections.py#L630-L634) |

Audit-event **writes** in this module: `execute_merge` inserts a
`merge.slide_mismatch` row into `audit_events` on a cross-slide merge
([app/services/segment_merge.py:74-88](../../app/services/segment_merge.py#L74-L88)). (Other `audit_events` kinds —
SOP, settings, improvements — are written by other modules and only *read* here.)

## State Management

- **Server-authoritative undo state**: a single integer `current_pointer` per
  session in `ledger_pointers`. Undo/redo are pointer arithmetic plus structural
  replay; the ledger rows are immutable history
  ([app/api/corrections.py:883-974](../../app/api/corrections.py#L883-L974)).
- **`active` derivation**: `sequence_number <= current_pointer`
  ([app/api/corrections.py:875](../../app/api/corrections.py#L875)).
- **Frontend feature-flag store**: `featureFlags.splitMergeEnabled` (Pinia) hydrated
  at app mount from `/v1/version`'s `split_merge_enabled`
  ([frontend/src/components/AppHeader.vue:53-62](../../frontend/src/components/AppHeader.vue#L53-L62),
  [frontend/src/stores/featureFlags.ts:22-28](../../frontend/src/stores/featureFlags.ts#L22-L28)); `SegmentText.vue` gates the
  split/merge UI on it ([frontend/src/components/editor/SegmentText.vue:96-97](../../frontend/src/components/editor/SegmentText.vue#L96-L97)).
- **Local view state**: `AuditView` holds `filter`, `corrections`, `loading`, `session`;
  `AuditTabInline` holds `view` (`decisions`/`ledger`). No global store for audit data.

## Validation

- Pydantic: `FindReplaceRequest.find` `min_length=1, max_length=512`; `replace`
  `max_length=512` ([app/api/corrections.py:115-119](../../app/api/corrections.py#L115-L119)).
- Type guard: `correction_type ∈ ALLOWED_CORRECTION_TYPES` else `400`
  ([app/api/corrections.py:49-53](../../app/api/corrections.py#L49-L53), [app/api/corrections.py:345-346](../../app/api/corrections.py#L345-L346)); DB CHECK
  constraint enforces the same enum ([migrations/029_corrections.sql:109-122](../../migrations/029_corrections.sql#L109-L122)).
- Existence: `_session_exists`, `_segment_belongs`
  ([app/api/corrections.py:201-258](../../app/api/corrections.py#L201-L258)).
- No-op guard before any write ([app/api/corrections.py:460-469](../../app/api/corrections.py#L460-L469)).
- Structural validation inside executors (word index bounds, anchor, neighbor,
  speaker) — see the Error Handling table below.
- Optimistic-concurrency: optional `expected_content_hash` drives a conditional
  `UPDATE ... WHERE content_hash = :expected_hash`; a 0-row result drops the
  autosave as stale ([app/api/corrections.py:482-525](../../app/api/corrections.py#L482-L525)).

## Security

- **AuthN**: every endpoint depends on `CurrentUser` (or `_u: CurrentUser` for reads)
  → `get_current_user` decodes the HS256 JWT and verifies the user is active
  (DB lookup with env-CSV fallback) ([app/auth.py:172-208](../../app/auth.py#L172-L208)).
- **SQL injection**: all queries are parameterized `sqlalchemy.text` binds; no string
  interpolation of user values. The only f-string in SQL is `audit.py`'s WHERE-clause
  assembly, which interpolates only fixed column predicates (`session_id = :s`,
  `actor_email = :a`, `kind = :k`) — values stay bound ([app/api/audit.py:34-38](../../app/api/audit.py#L34-L38)).
- **Concurrency safety**: `_next_seq` `FOR UPDATE` lock prevents duplicate
  `sequence_number`; structural ops + undo/redo hold a transaction-scoped advisory
  lock keyed on `(session_id, "split_merge")` ([app/services/db_locks.py:94-149](../../app/services/db_locks.py#L94-L149)).
- **Idempotency**: split/merge dedup on `action_id` inside the lock so two identical
  concurrent requests don't both execute ([app/api/corrections.py:368-371](../../app/api/corrections.py#L368-L371)).
- **Error leakage**: the structured `SPLIT_MERGE_EXEC_ERROR` 500 returns the
  exception class + truncated message to the client for diagnostics
  ([app/api/corrections.py:429-437](../../app/api/corrections.py#L429-L437)).

## Permissions

No role or admin gate exists in this module. Grep of [app/api/corrections.py](../../app/api/corrections.py)
and [app/api/audit.py](../../app/api/audit.py) returns zero `require_admin` / `is_admin` /
`LEGACY_ADMIN_EMAIL` matches. Authorization = **JWT presence only**.

Repo-wide, `app/security/roles.py` (`is_admin`/`require_admin`) is explicitly
"scaffold only — not yet wired into any endpoint" ([app/security/roles.py:10-19](../../app/security/roles.py#L10-L19)),
and `auth_users.role` (migration 045) is not read by `get_current_user`
([app/auth.py:172-205](../../app/auth.py#L172-L205)). The one client-side `adminOnly` guard
(`auth.email === 'johndean@vin.com'`) protects `#/admin/help`, not any audit screen
([frontend/src/router/index.ts:63](../../frontend/src/router/index.ts#L63)).

## Integrations

- **WS bridge** — `app.engines.ws_bridge.publish_ws_event_sync` (best-effort, lazy
  import) ([app/api/corrections.py:126-127](../../app/api/corrections.py#L126-L127)).
- **Advisory locks** — `app.services.db_locks` (Postgres `pg_try_advisory_xact_lock`)
  ([app/services/db_locks.py:94-149](../../app/services/db_locks.py#L94-L149)).
- **Export pipeline** — `text_edit` materialization keeps `segments.text` in sync so
  `artifact_transformer.load_session_for_export` reads corrected text
  ([app/api/corrections.py:573-596](../../app/api/corrections.py#L573-L596)).
- **Normalization layer** — find/replace reads `normalization_results` when present,
  tolerating its absence ([app/api/corrections.py:694-708](../../app/api/corrections.py#L694-L708)).
- **Ingest diff** — `app/engines/diff.py` feeds `transcription_discrepancies` /
  `word_alignment` that this module resolves and reparents.

## Background Jobs

This module exposes no Celery tasks. All endpoints are synchronous request/response
handlers; mutations commit within the request transaction
(`await db.commit()`). Structural work is done inline under an advisory lock rather
than deferred to a worker.

> Note: `app/engines/diff.py` is consumed by the ingest-side `lcs_discrepancies_task`
> (Celery), but that task lives outside the assigned Corrections & Audit source set;
> referenced here only for the discrepancy lifecycle this module closes.

## Error Handling

| Layer | Behavior | Source |
|---|---|---|
| Type/existence | `400`/`404` HTTPExceptions before any write | [corrections.py:345-353](../../app/api/corrections.py#L345-L353) |
| Split/merge dispatch | wrapped try/except: HTTPException propagates, other exceptions → rollback + structured `500 SPLIT_MERGE_EXEC_ERROR` with full `_log.exception` traceback | [corrections.py:383-437](../../app/api/corrections.py#L383-L437) |
| Stale autosave | conditional UPDATE 0-row → log warning, commit, return `stale: true` (no ledger row) | [corrections.py:506-525](../../app/api/corrections.py#L506-L525) |
| WS publish | swallowed (`except Exception: pass`) | [corrections.py:124-129](../../app/api/corrections.py#L124-L129) |
| Normalization read | swallowed; falls back to empty map | [corrections.py:707-708](../../app/api/corrections.py#L707-L708) |
| Invert payload parse | `_parse_payload` returns `None` on bad JSON → replay no-ops | [segment_inverse.py:35-43](../../app/services/segment_inverse.py#L35-L43) |
| Frontend | `SegmentText.handleApiError` maps `409 BUSY`→retry, `409 NEIGHBOR_CHANGED`→reload, `503 DISABLED`→toast | [SegmentText.vue:314-333](../../frontend/src/components/editor/SegmentText.vue#L314-L333) |

Structural executor error codes: `SPLIT_INVALID_WORD_INDEX`, `SPLIT_NO_WORD_ALIGNMENT`,
`SPLIT_SEGMENT_NOT_FOUND`, `SPLIT_ANCHOR_SEGMENT`, `MERGE_NO_NEIGHBOR`,
`MERGE_LEFT_NOT_FOUND`, `MERGE_NEIGHBOR_CHANGED`, `MERGE_SPEAKER_MISMATCH`,
`MERGE_ANCHOR_SEGMENT`, `MERGE_ANCHOR_NEIGHBOR`
([app/services/segment_split.py:26-59](../../app/services/segment_split.py#L26-L59),
[app/services/segment_merge.py:26-70](../../app/services/segment_merge.py#L26-L70)).

## Performance Considerations

- **Serialization cost**: every ledger write blocks on a `FOR UPDATE` of the single
  `ledger_pointers` row for the session — serializes concurrent autosave + split for
  that session, deliberately ([app/api/corrections.py:165-174](../../app/api/corrections.py#L165-L174)).
- **Advisory locks are RAM-cheap** (~50µs acquire), transaction-scoped, auto-released
  at COMMIT/ROLLBACK; no explicit unlock to avoid pooled-connection leakage
  ([app/services/db_locks.py:94-149](../../app/services/db_locks.py#L94-L149)).
- **Indexes** support the hot paths: `(session_id, sequence_number)` for next-seq /
  active filtering, `(session_id, action_id)` for dedup
  ([migrations/029_corrections.sql:126-129](../../migrations/029_corrections.sql#L126-L129)); `audit_events` has
  `occurred_at DESC` composite indexes for the feed
  ([migrations/004_audit.sql:13-15](../../migrations/004_audit.sql#L13-L15)).
- **Find/replace** loads all segments + active text_edits + normalization rows for
  the session into memory and runs a compiled regex per segment — O(segments) with
  no pagination ([app/api/corrections.py:710-738](../../app/api/corrections.py#L710-L738)).
- **Split shift** does one bulk `UPDATE segments SET seq = seq + 1 WHERE seq > orig`
  per split (noted negligible) ([app/services/segment_split.py:118-123](../../app/services/segment_split.py#L118-L123)).
- **LCS diff** is O(n·m) DP over token counts ([app/engines/diff.py:77-83](../../app/engines/diff.py#L77-L83)); run at
  ingest, not per request.
- **Materialization** uses a single `DISTINCT ON` CTE per undo/redo to roll all
  segments to the pointer in one statement ([app/api/corrections.py:228-245](../../app/api/corrections.py#L228-L245)).

## Source Verification
- **Files Used:** app/api/corrections.py, app/api/audit.py, app/services/segment_split.py, app/services/segment_merge.py, app/services/segment_inverse.py, app/services/db_locks.py, app/engines/diff.py, app/config.py, app/auth.py, app/security/roles.py, app/main.py, migrations/029_corrections.sql, migrations/000_fix_corrections_collision.sql, migrations/004_audit.sql, migrations/002_discrepancies.sql, frontend/src/views/AuditView.vue, frontend/src/views/EditorAuditView.vue, frontend/src/components/audit/AuditLedger.vue, frontend/src/components/editor/AuditTabInline.vue, frontend/src/components/editor/DecisionCard.vue, frontend/src/components/editor/SegmentText.vue, frontend/src/components/AppHeader.vue, frontend/src/stores/featureFlags.ts, frontend/src/router/index.ts, frontend/src/services/api.ts
- **Components Used:** AuditView.vue, EditorAuditView.vue, AuditLedger.vue, AuditTabInline.vue, DecisionCard.vue, SegmentText.vue, AppHeader.vue
- **APIs Used:** POST /v1/sessions/{id}/corrections, POST /v1/sessions/{id}/find-replace, GET /v1/sessions/{id}/corrections, POST /v1/sessions/{id}/corrections/undo, POST /v1/sessions/{id}/corrections/redo, GET /v1/sessions/{id}/review-queue, GET /v1/audit, GET /v1/audit/sessions/{id}/corrections
- **Database Tables Used:** correction_ledger, ledger_pointers, audit_events, transcription_discrepancies, segments, word_alignment, key_points_annotations, alignments, slides, normalization_results, corrections (legacy)
- **Permission Logic Used:** JWT presence only (CurrentUser); no admin/role gate in this module
- **Confidence Score:** High — all routes, SQL, services, and error codes traced to assigned source; background-job and feature-flag claims cross-checked against config and frontend.
- **Evidence Links:** [corrections.py:332-1033](../../app/api/corrections.py#L332-L1033), [audit.py:18-83](../../app/api/audit.py#L18-L83), [segment_inverse.py:46-201](../../app/services/segment_inverse.py#L46-L201), [db_locks.py:94-149](../../app/services/db_locks.py#L94-L149), [029_corrections.sql:88-152](../../migrations/029_corrections.sql#L88-L152), [config.py:134](../../app/config.py#L134)
