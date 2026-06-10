# Speaker Management — Technical Spec

> Module key: `speakers`. Code-verified against the rounds.vin repository on 2026-06-08.
> Paths are relative to this file at `docs/technical/`. Uncertainty is tagged with the
> exact strings the audit requires.

## Architecture

Speaker Management is a thin CRUD surface over the per-session `speakers` table plus a
single-segment reassignment endpoint over `segments.speaker_id`. There is no dedicated
"speakers service" module — the logic lives directly in the API router
[app/api/session_resources.py](../../app/api/session_resources.py) (speaker CRUD +
segment speaker-reassign) and the sibling
[app/api/segments.py](../../app/api/segments.py) (slide reassign + inline edits, which
can also set `speaker_id` as part of a segment PATCH).

```
SpeakerEditPanel.vue ──┐
                       ├─ services/api.ts `speakers.*`  ──► /v1/sessions/{id}/speakers*       ──► speakers table
EditorView.vue ────────┘                                                                          │
  onReassignSpeakerLive ─► services/api.ts `speakers.reassignSegment` ─► /.../speaker-reassign ──► segments.speaker_id
ingest tasks (ai_process / align / gcs_upload) ───────────────────────────────────────────────► speakers table (seed)
export (artifact_transformer.load_session_for_export) ◄── LEFT JOIN speakers ────────────────────┘
```

The roster is created by the ingest pipeline and then mutated by the operator through
the API. The export engine reads it back via a `LEFT JOIN speakers` at download time.

## Frontend Components

### `SpeakerEditPanel.vue`
[frontend/src/components/editor/SpeakerEditPanel.vue](../../frontend/src/components/editor/SpeakerEditPanel.vue)

- **Props:** `sessionId: string`, `liveSpeakers: readonly SessionSpeaker[]`
  ([:19-22](../../frontend/src/components/editor/SpeakerEditPanel.vue#L19)).
- **Emits:** `changed` — fired after every successful mutation so the parent re-fetches
  ([:24](../../frontend/src/components/editor/SpeakerEditPanel.vue#L24)).
- **Local state:** `collapsed`, `adding`, `newName`, `savingId`
  ([:26-29](../../frontend/src/components/editor/SpeakerEditPanel.vue#L26)).
- **Derived `cards`** computed — maps each live speaker to a render model with computed
  `initials` and a two-state `role` label (`MODERATOR`/`SPEAKER`)
  ([:31-49](../../frontend/src/components/editor/SpeakerEditPanel.vue#L31)).
- **Actions:** `renameSpeaker` (PATCH name), `toggleRole` (PATCH role),
  `addSpeaker` (POST), `removeSpeaker` (DELETE + native `confirm`)
  ([:51-99](../../frontend/src/components/editor/SpeakerEditPanel.vue#L51)).
- **`data-test-id`s:** `speaker-remove-{id}`, `speaker-add-open`, `speaker-add-confirm`
  ([:148](../../frontend/src/components/editor/SpeakerEditPanel.vue#L148),
  [:155](../../frontend/src/components/editor/SpeakerEditPanel.vue#L155),
  [:179](../../frontend/src/components/editor/SpeakerEditPanel.vue#L179)).

### `EditorView.vue`
[frontend/src/views/EditorView.vue](../../frontend/src/views/EditorView.vue)

- Imports and mounts `SpeakerEditPanel` in the right rail
  ([:44](../../frontend/src/views/EditorView.vue#L44),
  [:1467-1471](../../frontend/src/views/EditorView.vue#L1467)).
- Holds the canonical roster in `SPEAKERS_API` (`ref<ApiSpeaker[]>`)
  ([:91-92](../../frontend/src/views/EditorView.vue#L91)); also passed to the transcript
  area's `:live-speakers` ([:1345](../../frontend/src/views/EditorView.vue#L1345)).
- `reloadSpeakers()` re-fetches the roster on the panel's `changed` event; failures are
  swallowed and logged ([:539-552](../../frontend/src/views/EditorView.vue#L539)).
- `onReassignSpeakerLive(segId, beforeSpeakerId, afterSpeakerId)` reassigns one
  segment's speaker, then splices the segment in place for reactivity
  ([:994-1019](../../frontend/src/views/EditorView.vue#L994)).

## Backend Services

There is no `app/services/speakers.py`. All speaker logic is inline in
[app/api/session_resources.py](../../app/api/session_resources.py):

| Function | Lines | Operation |
|---|---|---|
| `list_speakers` | [206-225](../../app/api/session_resources.py#L206) | `SELECT ... ORDER BY name ASC` |
| `add_speaker` | [228-253](../../app/api/session_resources.py#L228) | `INSERT ... RETURNING`, color default `#2563eb` |
| `edit_speaker` | [256-289](../../app/api/session_resources.py#L256) | `UPDATE ... SET name/role/avatar_color = COALESCE(...)` |
| `remove_speaker` | [292-315](../../app/api/session_resources.py#L292) | `DELETE ... RETURNING id`, 204 on success |
| `reassign_segment_speaker` | [318-366](../../app/api/session_resources.py#L318) | validate both belong to session, then `UPDATE segments SET speaker_id` |

Ingest-side speaker seeding (separate from this module's CRUD):
- [app/tasks/ai_process.py:388-410](../../app/tasks/ai_process.py#L388) — wipe + insert
  one row per unique speaker label (default name `Presenter`, role `Instructor`).
- [app/tasks/align.py:148-152](../../app/tasks/align.py#L150) — insert a single
  `Presenter`/`Instructor` row when none exists.
- [app/api/gcs_upload.py:292-304](../../app/api/gcs_upload.py#L292) — manifest bridge,
  idempotent insert keyed on name.

## APIs

All under the router prefix `/v1/sessions/{session_id}`
([app/api/session_resources.py:21](../../app/api/session_resources.py#L21)).

### `GET /v1/sessions/{session_id}/speakers`
List speakers, ordered by name. Returns `list[SpeakerOut]`. Empty list for a session
with no rows. [session_resources.py:206-225](../../app/api/session_resources.py#L206).

### `POST /v1/sessions/{session_id}/speakers`
Create a speaker. Body `SpeakerCreate` `{ name: str, role?: str, avatar_color?: str }`.
Returns `SpeakerOut`, status `201`. `avatar_color` defaults to `#2563eb` when omitted.
[session_resources.py:228-253](../../app/api/session_resources.py#L228).

### `PATCH /v1/sessions/{session_id}/speakers/{speaker_id}`
Partial update. Body `SpeakerPatch` `{ name?, role?, avatar_color? }`; each field is
`COALESCE`d so omitted fields are preserved. `404` if not in session.
[session_resources.py:256-289](../../app/api/session_resources.py#L256).

### `DELETE /v1/sessions/{session_id}/speakers/{speaker_id}`
Delete a speaker. Returns `204 No Content` (uses `Response(status_code=204)`). `404` if
not in session. Segments referencing the row are nulled by the FK `ON DELETE SET NULL`.
[session_resources.py:292-315](../../app/api/session_resources.py#L292).

### `POST /v1/sessions/{session_id}/segments/{segment_id}/speaker-reassign`
Reassign one segment to a target speaker. Body `SpeakerReassignRequest`
`{ speaker_id: UUID }`. Validates the speaker belongs to the session (`404` else) and
the segment belongs to the session (`404` else), then
`UPDATE segments SET speaker_id = ..., updated_at = now()`. Returns the target
`SpeakerOut`. [session_resources.py:318-366](../../app/api/session_resources.py#L318).

> **Adjacent endpoint:** `PATCH /v1/sessions/{session_id}/segments/{segment_id}`
> ([app/api/segments.py:120-221](../../app/api/segments.py#L120)) also accepts
> `speaker_id` in its `SegmentPatch` body
> ([segments.py:39](../../app/api/segments.py#L39)) and will write it to the segment,
> recording a `corrections` row + `segment.edit` audit event. The `speakers.reassignSegment`
> frontend wrapper uses the dedicated `/speaker-reassign` route, not this one
> ([frontend/src/services/api.ts:328-332](../../frontend/src/services/api.ts#L328)).

### Frontend API client
[frontend/src/services/api.ts:310-333](../../frontend/src/services/api.ts#L310) exposes
`speakers.list/add/edit/remove/reassignSegment`. `SessionSpeaker` interface:
`{ id, short, name, role, avatar_color? }`
([api.ts:232-238](../../frontend/src/services/api.ts#L232)).

## Data Models

### `speakers` table
[migrations/001_init.sql:69-78](../../migrations/001_init.sql#L69)

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `session_id` | UUID NOT NULL | FK → `sessions(id)` `ON DELETE CASCADE` |
| `name` | TEXT NOT NULL | |
| `role` | TEXT | e.g. `Instructor`, `Q&A`, `Moderator` |
| `avatar_color` | TEXT | hex |
| `metadata` | JSONB NOT NULL DEFAULT `{}` | not read/written by speaker endpoints |

Index `speakers_session_idx` on `(session_id)`
([migrations/001_init.sql:78](../../migrations/001_init.sql#L78)). There is **no
`created_at`** column — list ordering uses `name` deliberately
([session_resources.py:208-211](../../app/api/session_resources.py#L208)).

### `segments.speaker_id`
[migrations/001_init.sql:86](../../migrations/001_init.sql#L86) —
`UUID REFERENCES speakers(id) ON DELETE SET NULL`. Index
`segments_session_speaker_idx` on `(session_id, speaker_id)`
([migrations/001_init.sql:104](../../migrations/001_init.sql#L104)).

### Pydantic schemas
[session_resources.py:181-204](../../app/api/session_resources.py#L181) — `SpeakerOut`
(`id, short, name, role, avatar_color`; `short` is aliased from `name` in SQL),
`SpeakerCreate`, `SpeakerPatch`, `SpeakerReassignRequest`. Note `short` is always equal
to `name` because the query selects `name AS short, name`
([session_resources.py:216](../../app/api/session_resources.py#L216)).

## Events

- **No WebSocket event is emitted for speaker CRUD or speaker-reassign.** None of the
  five handlers call `_emit_ws` / the WS bridge
  ([session_resources.py:228-366](../../app/api/session_resources.py#L228)). (The
  corrections handler emits `correction_applied` for split/merge, but that path is not
  used by speaker reassignment — [corrections.py:438-443](../../app/api/corrections.py#L438).)
- **No `audit_events` row** is written by speaker CRUD or speaker-reassign — see Error
  Handling / the product spec's Audit section.
- Client-side, the only "event" is the Vue `changed` emit from the panel
  ([SpeakerEditPanel.vue:24](../../frontend/src/components/editor/SpeakerEditPanel.vue#L24)),
  consumed by `reloadSpeakers` ([EditorView.vue:1470](../../frontend/src/views/EditorView.vue#L1470)).

## State Management

There is no Pinia/Vuex store for speakers. The roster lives in component-local refs:

- `SPEAKERS_API` in `EditorView.vue` is the single source of truth, hydrated on load
  ([EditorView.vue:392](../../frontend/src/views/EditorView.vue#L392)) and refreshed by
  `reloadSpeakers` ([:539-552](../../frontend/src/views/EditorView.vue#L539)).
- `SpeakerEditPanel` receives `liveSpeakers` as a read-only prop and never mutates it
  directly — it calls the API and emits `changed` to trigger a parent re-fetch
  ([SpeakerEditPanel.vue:19-24](../../frontend/src/components/editor/SpeakerEditPanel.vue#L19)).
- Segment-level reassignment updates the segment row optimistically via `splice`
  ([EditorView.vue:1012](../../frontend/src/views/EditorView.vue#L1012)).

## Validation

| Rule | Where | Layer |
|---|---|---|
| Non-empty name on add | [SpeakerEditPanel.vue:79-80](../../frontend/src/components/editor/SpeakerEditPanel.vue#L79) | client |
| Non-empty name on rename | [SpeakerEditPanel.vue:52-53](../../frontend/src/components/editor/SpeakerEditPanel.vue#L52) | client |
| `name` required | [session_resources.py:191](../../app/api/session_resources.py#L191) (Pydantic) + DB NOT NULL [001_init.sql:72](../../migrations/001_init.sql#L72) | server |
| PATCH partial update via COALESCE | [session_resources.py:267-274](../../app/api/session_resources.py#L267) | server |
| Reassign: speaker in session | [session_resources.py:332-343](../../app/api/session_resources.py#L332) | server |
| Reassign: segment in session | [session_resources.py:345-356](../../app/api/session_resources.py#L345) | server |

> Whitespace-only names are trimmed/rejected on the client only; the server accepts any
> non-null string. **PARTIALLY IMPLEMENTED** server-side trimming.

## Security

- Every speaker route depends on `CurrentUser` (`app.auth.CurrentUser`), i.e. a valid
  JWT is required ([session_resources.py:18](../../app/api/session_resources.py#L18),
  per-handler [207](../../app/api/session_resources.py#L207),
  [230](../../app/api/session_resources.py#L230),
  [258](../../app/api/session_resources.py#L258),
  [294](../../app/api/session_resources.py#L294),
  [321](../../app/api/session_resources.py#L321)).
- **Session-scoping is the only tenancy boundary.** Reassign validates that both the
  speaker and segment belong to the path session before mutating
  ([session_resources.py:332-356](../../app/api/session_resources.py#L332)). CRUD
  edit/delete scope every statement by `session_id` so a speaker id from another
  session 404s ([:271-272](../../app/api/session_resources.py#L271),
  [:307-308](../../app/api/session_resources.py#L307)). Rounds has no per-session
  membership model (single-tenant operator pool) — see the note at
  [segments.py:124-132](../../app/api/segments.py#L124).
- All queries use bound parameters (`sqlalchemy.text` with `:params`); no string
  interpolation of user input into SQL.

## Permissions

No role-based authorization is enforced on any speaker endpoint — handlers take
`_user: CurrentUser` and never read `user.email` or any role. Role-based auth is
scaffold-only repo-wide: `app/security/roles.py` is not wired into endpoints, and
`get_current_user` does not read `auth_users.role`. The only admin gate in the product
is the client-side router guard comparing `auth.email` to the hardcoded
`LEGACY_ADMIN_EMAIL = 'johndean@vin.com'`
([frontend/src/router/index.ts:49-66](../../frontend/src/router/index.ts#L49)); the
Editor route (and therefore the Speakers panel) is **not** flagged `adminOnly`, so any
authenticated user can perform all speaker operations.

## Integrations

- **Ingest pipeline** (Celery): `ai_process`, `align`, and the manifest bridge in
  `gcs_upload` create the initial roster (see Backend Services).
- **Export engine** `app/engines/artifact_transformer.py`:
  `load_session_for_export` joins `speakers` to provide `speaker_name` + `speaker_role`
  per segment ([artifact_transformer.py:568-583](../../app/engines/artifact_transformer.py#L568)),
  consumed by `to_txt`/`to_docx`/`_build_marked_transcript`. SRT strips speaker labels
  ([:236-258](../../app/engines/artifact_transformer.py#L236)).
- **No external integration** (no third-party diarization API call in this module).

## Background Jobs

This module has no Celery task of its own. The only background work touching the
`speakers` table is roster *seeding* during ingest
([ai_process.py:388-410](../../app/tasks/ai_process.py#L388),
[align.py:148-152](../../app/tasks/align.py#L150)). There is **no** background
re-detection/re-diarization job that can be triggered after ingest.
**IMPLEMENTATION NOT FOUND** for a re-run-speaker-detection task.

## Error Handling

- **404** from edit/delete/reassign when the row is not in the session
  ([session_resources.py:285-287](../../app/api/session_resources.py#L285),
  [:312-313](../../app/api/session_resources.py#L312),
  [:342-343](../../app/api/session_resources.py#L342),
  [:355-356](../../app/api/session_resources.py#L355)).
- **Client** surfaces failures as toasts, preferring the `ApiError` status + message
  ([SpeakerEditPanel.vue:58-59](../../frontend/src/components/editor/SpeakerEditPanel.vue#L58),
  [:71-72](../../frontend/src/components/editor/SpeakerEditPanel.vue#L71),
  [:86-87](../../frontend/src/components/editor/SpeakerEditPanel.vue#L86),
  [:96-97](../../frontend/src/components/editor/SpeakerEditPanel.vue#L96),
  [EditorView.vue:1015-1017](../../frontend/src/views/EditorView.vue#L1015)).
- **Roster reload** is best-effort: a failed `speakers.list` logs a warning and returns
  without clearing the existing list ([EditorView.vue:540-543](../../frontend/src/views/EditorView.vue#L540)).
- No `audit_events` row and no WS broadcast accompany speaker mutations (see Events).

## Performance Considerations

- **List** is a single indexed scan on `speakers_session_idx`, ordered by `name`
  ([session_resources.py:206-224](../../app/api/session_resources.py#L206)); roster
  cardinality is small (one row per detected/added speaker).
- **Reassign** does two validation `SELECT`s plus one `UPDATE`
  ([session_resources.py:332-364](../../app/api/session_resources.py#L332)); the
  `segments_session_speaker_idx` index supports speaker-filtered reads but the reassign
  `UPDATE` is keyed by segment `id` (PK).
- **No N+1** on the speaker path; the optimistic `splice` in the Editor avoids a full
  segment re-fetch after a single reassignment
  ([EditorView.vue:1012](../../frontend/src/views/EditorView.vue#L1012)).
- **Bulk reassignment is not supported** — reassigning many segments is N HTTP calls.

## Source Verification
- **Files Used:** app/api/session_resources.py, app/api/segments.py, app/api/corrections.py, app/engines/artifact_transformer.py, app/tasks/ai_process.py, app/tasks/align.py, app/api/gcs_upload.py, migrations/001_init.sql, frontend/src/components/editor/SpeakerEditPanel.vue, frontend/src/views/EditorView.vue, frontend/src/services/api.ts, frontend/src/router/index.ts
- **Components Used:** SpeakerEditPanel.vue, EditorView.vue
- **APIs Used:** GET/POST `/v1/sessions/{id}/speakers`, PATCH/DELETE `/v1/sessions/{id}/speakers/{speaker_id}`, POST `/v1/sessions/{id}/segments/{segment_id}/speaker-reassign`, PATCH `/v1/sessions/{id}/segments/{segment_id}` (adjacent)
- **Database Tables Used:** speakers, segments (speaker_id), sessions (FK parent)
- **Permission Logic Used:** JWT presence only (CurrentUser) on all speaker routes; no role gate; client-side LEGACY_ADMIN_EMAIL guard does not cover the Editor
- **Confidence Score:** High — all endpoints, schemas, and the DB table read directly from current source; absence of audit/WS/store and of speaker-merge confirmed by Grep.
- **Evidence Links:** [session_resources.py:181-366](../../app/api/session_resources.py#L181), [migrations/001_init.sql:69-104](../../migrations/001_init.sql#L69), [api.ts:310-333](../../frontend/src/services/api.ts#L310), [SpeakerEditPanel.vue:19-99](../../frontend/src/components/editor/SpeakerEditPanel.vue#L19), [EditorView.vue:539-1019](../../frontend/src/views/EditorView.vue#L539)
