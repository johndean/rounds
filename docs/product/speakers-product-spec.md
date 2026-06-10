# Speaker Management — Product Spec

> Module key: `speakers`. Code-verified against the rounds.vin repository on 2026-06-08.
> Every claim below is traced to source with a file:line link. Unproven behavior is tagged.

## Overview

Speaker Management is the per-session roster of people who spoke during a recorded
session, plus the wiring that attributes each transcript segment to one of those
people. Each session owns its own list of speakers (a row in the `speakers` table
scoped by `session_id`), and each segment carries an optional `speaker_id` foreign
key pointing at one of them. See the table definitions in
[migrations/001_init.sql:68-99](../../migrations/001_init.sql#L68).

The roster is seeded automatically during ingest and then refined by hand in the
Editor's right-rail **Speakers** panel
([frontend/src/components/editor/SpeakerEditPanel.vue](../../frontend/src/components/editor/SpeakerEditPanel.vue)),
which is mounted in the Editor view
([frontend/src/views/EditorView.vue:1467](../../frontend/src/views/EditorView.vue#L1467)).

## Purpose

When a transcript is exported, each segment is rendered with a speaker label prefix
(for example `Dr. Hayes: ...`) when a speaker is attached, and with no prefix when
it is not — see the export logic in
[app/engines/artifact_transformer.py:121-124](../../app/engines/artifact_transformer.py#L121)
(`to_txt`) and
[app/engines/artifact_transformer.py:187-193](../../app/engines/artifact_transformer.py#L187)
(`to_docx`). Speaker Management exists so an operator can correct the AI's first-pass
attribution — rename a speaker, change a speaker's role, remove a stray speaker, add a
missed one, and reassign an individual segment to a different speaker — before the
session is published.

## User Value

- **Rename once, fixed everywhere.** A speaker is a single row referenced by many
  segments via `segments.speaker_id`
  ([migrations/001_init.sql:86](../../migrations/001_init.sql#L86)). Renaming the
  `speakers` row updates the label on every segment that points at it, because the
  export and editor both read the name through the foreign key
  ([app/engines/artifact_transformer.py:574-577](../../app/engines/artifact_transformer.py#L574)).
- **Fix one segment without touching the rest.** A single segment can be re-pointed
  to a different speaker
  ([app/api/session_resources.py:318](../../app/api/session_resources.py#L318)).
- **Add a speaker the AI never detected**
  ([app/api/session_resources.py:228](../../app/api/session_resources.py#L228)).
- **Remove a duplicate or spurious speaker** without losing the affected segments —
  the foreign key uses `ON DELETE SET NULL`, so segments survive with a null speaker
  ([migrations/001_init.sql:86](../../migrations/001_init.sql#L86)).

## Navigation

The Speakers panel lives in the Editor's right rail, rendered by
`SpeakerEditPanel.vue` and mounted at
[frontend/src/views/EditorView.vue:1467-1471](../../frontend/src/views/EditorView.vue#L1467).
The panel header is a collapse/expand toggle showing the speaker count
([SpeakerEditPanel.vue:110-118](../../frontend/src/components/editor/SpeakerEditPanel.vue#L110)).

> The seed doc states the Speakers panel also appears "on the Session Detail page."
> **NOT VERIFIED IN CODE** — `SpeakerEditPanel` is imported and mounted only in
> `EditorView.vue`; a Grep of `frontend/` finds no Session Detail mount.

## Screens

### Speakers panel (right rail of the Editor)

Source: [SpeakerEditPanel.vue:108-186](../../frontend/src/components/editor/SpeakerEditPanel.vue#L108).

- **Header** — `Speakers · {count}` with a chevron that collapses/expands the body
  ([SpeakerEditPanel.vue:116](../../frontend/src/components/editor/SpeakerEditPanel.vue#L116)).
- **Speaker card** (one per speaker) — an avatar circle showing the speaker's
  initials, an inline-editable name field, a role pill, and an `×` remove button
  ([SpeakerEditPanel.vue:121-152](../../frontend/src/components/editor/SpeakerEditPanel.vue#L121)).
  The avatar background uses the speaker's `avatar_color` when set
  ([SpeakerEditPanel.vue:127-130](../../frontend/src/components/editor/SpeakerEditPanel.vue#L127)).
- **Role pill** — a toggle button showing `MODERATOR` or `SPEAKER`
  ([SpeakerEditPanel.vue:139-144](../../frontend/src/components/editor/SpeakerEditPanel.vue#L139)).
  A card whose role resolves to `MODERATOR` gets a left amber border
  ([SpeakerEditPanel.vue:125](../../frontend/src/components/editor/SpeakerEditPanel.vue#L125),
  [:229-232](../../frontend/src/components/editor/SpeakerEditPanel.vue#L229)).
- **Add speaker** — a CTA button that expands into a single-line name entry with an
  `Add` confirm button; the new speaker defaults to role `speaker`
  ([SpeakerEditPanel.vue:154-183](../../frontend/src/components/editor/SpeakerEditPanel.vue#L154),
  add call at [:82](../../frontend/src/components/editor/SpeakerEditPanel.vue#L82)).

### Per-segment speaker reassignment

The segment-level reassign is driven from the transcript area through
`onReassignSpeakerLive`
([EditorView.vue:994-1019](../../frontend/src/views/EditorView.vue#L994)), which calls
`speakers.reassignSegment`
([frontend/src/services/api.ts:328-332](../../frontend/src/services/api.ts#L328)).

## User Flows

### Rename a speaker
1. Click the name field on a speaker card and edit it.
2. On blur (or Enter, which blurs the field), if the text changed,
   `renameSpeaker` fires a PATCH with the trimmed name
   ([SpeakerEditPanel.vue:51-63](../../frontend/src/components/editor/SpeakerEditPanel.vue#L51),
   blur handler at [:101-105](../../frontend/src/components/editor/SpeakerEditPanel.vue#L101)).
3. On success the panel emits `changed`; the Editor re-fetches the roster via
   `reloadSpeakers` ([EditorView.vue:539-552](../../frontend/src/views/EditorView.vue#L539)).

### Toggle a speaker's role (Moderator ↔ Speaker)
1. Click the role pill.
2. `toggleRole` PATCHes `role` to `moderator` if it was `MODERATOR`, else `speaker`
   ([SpeakerEditPanel.vue:65-76](../../frontend/src/components/editor/SpeakerEditPanel.vue#L65)).

### Add a missing speaker
1. Click **Add speaker**, type a name, click **Add** (or press Enter).
2. `addSpeaker` POSTs `{ name, role: 'speaker' }`
   ([SpeakerEditPanel.vue:78-89](../../frontend/src/components/editor/SpeakerEditPanel.vue#L78)).
3. The role can then be toggled on the resulting card.

### Remove a speaker
1. Click the `×` on a card.
2. A native browser `confirm()` asks `Remove "<name>"?`
   ([SpeakerEditPanel.vue:91-99](../../frontend/src/components/editor/SpeakerEditPanel.vue#L91)).
3. On confirm, a DELETE is issued; affected segments have `speaker_id` set to NULL by
   the FK ([app/api/session_resources.py:292-315](../../app/api/session_resources.py#L292)).

### Reassign a single segment to a different speaker
1. From the transcript, `onReassignSpeakerLive` POSTs to
   `/segments/{segment_id}/speaker-reassign`
   ([EditorView.vue:994-996](../../frontend/src/views/EditorView.vue#L994)).
2. The backend validates that both the segment and the target speaker belong to the
   session, then updates `segments.speaker_id`
   ([app/api/session_resources.py:318-366](../../app/api/session_resources.py#L318)).

## Business Rules

- **BR — speaker roster is per-session.** `speakers.session_id` is a non-null FK to
  `sessions` ([migrations/001_init.sql:71](../../migrations/001_init.sql#L71)).
- **BR — deleting a speaker nulls, not deletes, its segments.**
  `segments.speaker_id ... ON DELETE SET NULL`
  ([migrations/001_init.sql:86](../../migrations/001_init.sql#L86)).
- **BR — cross-session reassignment is blocked.** The reassign endpoint 404s if the
  target speaker or the segment does not belong to the path session
  ([app/api/session_resources.py:332-356](../../app/api/session_resources.py#L332)).
- **BR-017 — Unknown speaker fallback (PARTIALLY IMPLEMENTED).** The export module's
  docstring names a "BR-017 (Unknown speaker fallback)"
  ([app/engines/artifact_transformer.py:11](../../app/engines/artifact_transformer.py#L11),
  [app/api/exports.py:14](../../app/api/exports.py#L14)). The actual code does **not**
  emit a literal `(Unknown)` label: `to_txt`, `to_docx`, and `_build_marked_transcript`
  simply omit the speaker prefix when `speaker_name` is falsy
  ([artifact_transformer.py:121-124](../../app/engines/artifact_transformer.py#L121),
  [:187](../../app/engines/artifact_transformer.py#L187),
  [:229](../../app/engines/artifact_transformer.py#L229)). The seed doc's claim that an
  unattributed segment "exports as **(Unknown)**" is **NOT VERIFIED IN CODE** — no
  `(Unknown)` string exists in the export path. (A `(unknown)` string does exist, but
  only as an actor-email fallback in audit logging, unrelated to speaker labels —
  [corrections.py:396](../../app/api/corrections.py#L396).)
- **BR — ingest seeds at least one speaker.** AI-mode ingest deletes existing speaker
  rows for the session, then inserts one row per unique speaker label (defaulting the
  label to `Presenter` and the role to `Instructor`, color `#2563eb`)
  ([app/tasks/ai_process.py:388-410](../../app/tasks/ai_process.py#L388)). The legacy
  STT/align path inserts a single `Presenter`/`Instructor` row when none exists
  ([app/tasks/align.py:148-152](../../app/tasks/align.py#L150)). The manifest-bridge
  path inserts manifest-named speakers idempotently (name de-dup)
  ([app/api/gcs_upload.py:292-304](../../app/api/gcs_upload.py#L292)).

## Validation Rules

- **Add / rename name must be non-empty (client-side).** `addSpeaker` rejects a blank
  name with a warn toast ([SpeakerEditPanel.vue:79-80](../../frontend/src/components/editor/SpeakerEditPanel.vue#L79));
  `renameSpeaker` rejects an empty rename and re-emits `changed` to revert the field
  ([SpeakerEditPanel.vue:52-53](../../frontend/src/components/editor/SpeakerEditPanel.vue#L52)).
- **Server-side name requirement.** `SpeakerCreate.name` is a required `str`
  ([app/api/session_resources.py:190-193](../../app/api/session_resources.py#L190));
  the DB column `speakers.name` is `NOT NULL`
  ([migrations/001_init.sql:72](../../migrations/001_init.sql#L72)). **Note:** the
  server does not trim or reject whitespace-only names — that enforcement is
  client-side only. **PARTIALLY IMPLEMENTED.**
- **Add default color.** When `avatar_color` is omitted on create, the server defaults
  it to `#2563eb` ([app/api/session_resources.py:248](../../app/api/session_resources.py#L248)).
- **Edit is a partial update.** PATCH applies only the supplied fields via `COALESCE`;
  omitted fields are preserved
  ([app/api/session_resources.py:256-289](../../app/api/session_resources.py#L256)).
- **Reassign target validation.** Both speaker and segment must belong to the session
  ([app/api/session_resources.py:332-356](../../app/api/session_resources.py#L332)).

## States

- **No speakers yet** — the list endpoint returns `[]` for a session with no rows; the
  panel renders zero cards and just the Add CTA
  ([app/api/session_resources.py:206-225](../../app/api/session_resources.py#L206)).
- **Saving a card** — `savingId` disables the name field of the card being saved
  ([SpeakerEditPanel.vue:29](../../frontend/src/components/editor/SpeakerEditPanel.vue#L29),
  bound at [:135](../../frontend/src/components/editor/SpeakerEditPanel.vue#L135)).
- **Adding** — `adding` swaps the CTA for the new-speaker entry row
  ([SpeakerEditPanel.vue:28](../../frontend/src/components/editor/SpeakerEditPanel.vue#L28),
  [:154-183](../../frontend/src/components/editor/SpeakerEditPanel.vue#L154)).
- **Collapsed** — `collapsed` hides the body, leaving only the header
  ([SpeakerEditPanel.vue:26](../../frontend/src/components/editor/SpeakerEditPanel.vue#L26),
  [:120](../../frontend/src/components/editor/SpeakerEditPanel.vue#L120)).
- **Role display** — any role string that lowercases to `moderator` renders as
  `MODERATOR`; everything else (including `Instructor`, `Presenter`, null) renders as
  `SPEAKER` ([SpeakerEditPanel.vue:39-41](../../frontend/src/components/editor/SpeakerEditPanel.vue#L39)).
  **Note:** the ingest-seeded role is `Instructor`, which the panel collapses to the
  `SPEAKER` pill — the original role string is preserved in the DB but not surfaced in
  the panel's two-state pill.

## Dependencies

- **Sessions** — every speaker and segment is scoped by `session_id`
  ([migrations/001_init.sql:71](../../migrations/001_init.sql#L71),
  [:84](../../migrations/001_init.sql#L84)).
- **Segments** — carry the `speaker_id` FK that attribution mutates
  ([migrations/001_init.sql:86](../../migrations/001_init.sql#L86)).
- **Ingest pipeline** — seeds the initial roster (`ai_process`, `align`, manifest
  bridge in `gcs_upload`).
- **Export pipeline** — reads `speakers.name` and `speakers.role` for labels and DOCX
  styling ([artifact_transformer.py:574-577](../../app/engines/artifact_transformer.py#L574)).

## Error Handling

- **404 on edit/delete/reassign** when the speaker (or segment) is not in the session
  ([app/api/session_resources.py:285-287](../../app/api/session_resources.py#L285),
  [:312-313](../../app/api/session_resources.py#L312),
  [:342-343](../../app/api/session_resources.py#L342),
  [:355-356](../../app/api/session_resources.py#L355)).
- **Client toasts** — add/edit/remove failures surface as error toasts carrying the
  HTTP status + message when the error is an `ApiError`
  ([SpeakerEditPanel.vue:58-59](../../frontend/src/components/editor/SpeakerEditPanel.vue#L58),
  [:71-72](../../frontend/src/components/editor/SpeakerEditPanel.vue#L71),
  [:86-87](../../frontend/src/components/editor/SpeakerEditPanel.vue#L86),
  [:96-97](../../frontend/src/components/editor/SpeakerEditPanel.vue#L96)).
- **Reassign failure** surfaces as an error toast in the Editor
  ([EditorView.vue:1015-1017](../../frontend/src/views/EditorView.vue#L1015)).
- **Roster reload is non-fatal** — `reloadSpeakers` swallows a failed list call and
  logs a warning ([EditorView.vue:540-543](../../frontend/src/views/EditorView.vue#L540)).

## Permissions

Speaker endpoints require only an authenticated user (the `CurrentUser` dependency) —
there is **no role gate** on any speaker route. Every handler in
`session_resources.py` takes `_user: CurrentUser` and never inspects the user's email
or role ([app/api/session_resources.py:207](../../app/api/session_resources.py#L207),
[:230](../../app/api/session_resources.py#L230),
[:258](../../app/api/session_resources.py#L258),
[:294](../../app/api/session_resources.py#L294),
[:321](../../app/api/session_resources.py#L321)).

Role-based authorization is scaffold-only across the repo: there is no admin check on
speaker routes. The only admin gate in the system is a hardcoded
`auth.email !== 'johndean@vin.com'` comparison in the client-side router guard for
routes flagged `adminOnly` ([frontend/src/router/index.ts:49-66](../../frontend/src/router/index.ts#L49)),
and the Editor / Speakers panel is not behind that flag. Any logged-in user can add,
rename, reassign, and delete speakers.

## Reporting Impacts

- **Transcript exports** render the speaker name as a prefix on each segment when set,
  and omit it when null
  ([artifact_transformer.py:121-124](../../app/engines/artifact_transformer.py#L121) txt,
  [:187-193](../../app/engines/artifact_transformer.py#L187) docx,
  [:229-230](../../app/engines/artifact_transformer.py#L229) CMS-marked).
- **DOCX color styling** — a speaker whose `role` equals the literal string `primary`
  is rendered in navy bold; all other roles (including `Instructor`, `moderator`,
  `guest`, null) render bold-only
  ([artifact_transformer.py:187-193](../../app/engines/artifact_transformer.py#L187)).
  **Note:** the panel's role toggle writes `moderator`/`speaker`, and ingest writes
  `Instructor` — none of these is `primary`, so the navy styling branch is not reached
  by any role value the speaker UI or ingest produces today. **PARTIALLY IMPLEMENTED.**
- **SRT captions** strip speaker labels entirely (captions are plain speech)
  ([artifact_transformer.py:236-258](../../app/engines/artifact_transformer.py#L236)).
- **Chat participants tally** is a *separate* aggregation over `chat_messages.author`,
  not the `speakers` table ([app/api/session_resources.py:639-672](../../app/api/session_resources.py#L639)).

## Audit Requirements

- **Speaker CRUD writes no audit_events row.** `add_speaker`, `edit_speaker`,
  `remove_speaker`, and `reassign_segment_speaker` commit their DB change without an
  `audit_events` insert ([app/api/session_resources.py:228-366](../../app/api/session_resources.py#L228)).
  This contrasts with chat/poll reorder, segment edit, and segment reassign, which all
  write `audit_events` rows ([session_resources.py:578](../../app/api/session_resources.py#L578),
  [segments.py:213](../../app/api/segments.py#L213)). **Speaker changes are therefore
  not currently captured in the audit ledger.**
- **`speaker_reassignment` correction type exists but is decoupled from the reassign
  endpoint.** `speaker_reassignment` is an allowed correction type
  ([corrections.py:52](../../app/api/corrections.py#L52)), and the reassign endpoint's
  docstring says callers "SHOULD ALSO record a speaker_reassignment correction ... so
  undo works" ([session_resources.py:326-329](../../app/api/session_resources.py#L326)).
  In practice the frontend's `onReassignSpeakerLive` calls only the `/speaker-reassign`
  endpoint and does **not** post a correction
  ([EditorView.vue:994-1019](../../frontend/src/views/EditorView.vue#L994)). The generic
  corrections flow only mutates `segments.text` for `text_edit`; it does not mutate
  `segments.speaker_id` for `speaker_reassignment`
  ([corrections.py:578-593](../../app/api/corrections.py#L578)). The seed doc's claim
  that reassignment is recorded "so undo works" is **NOT VERIFIED IN CODE** — speaker
  reassignment is not undoable through the correction ledger today.

## Data Relationships

```
sessions (1) ──< (N) speakers          speakers.session_id → sessions.id  (ON DELETE CASCADE)
sessions (1) ──< (N) segments          segments.session_id → sessions.id  (ON DELETE CASCADE)
speakers (1) ──< (N) segments          segments.speaker_id → speakers.id  (ON DELETE SET NULL)
```

Source: [migrations/001_init.sql:69-99](../../migrations/001_init.sql#L69). The
`speakers` table columns are `id`, `session_id`, `name` (NOT NULL), `role`,
`avatar_color`, `metadata`
([migrations/001_init.sql:69-76](../../migrations/001_init.sql#L69)). There is **no**
`created_at` column on `speakers` — the list query intentionally orders by `name`
([session_resources.py:208-224](../../app/api/session_resources.py#L208)).

## Known Constraints

- **No speaker-identity merge.** There is no endpoint or service that merges two
  `speakers` rows into one. The "merge" code in the repo
  (`app/services/segment_merge.py`) merges adjacent **same-speaker segments**, not
  speakers ([app/services/segment_merge.py:23-68](../../app/services/segment_merge.py#L23)).
  The seed doc's "Merge duplicates" bullet and the help-content "rename, merge, or
  remove speakers" copy ([app/data/help_content.py:111](../../app/data/help_content.py#L111),
  [:131](../../app/data/help_content.py#L131)) describe a feature that **IMPLEMENTATION
  NOT FOUND** for speakers. To consolidate a duplicate today an operator reassigns each
  segment to the kept speaker and deletes the duplicate.
- **No batch reassign.** Reassignment is one segment per call
  ([session_resources.py:318](../../app/api/session_resources.py#L318)); there is no
  bulk-segment reassign endpoint.
- **No re-run of speaker detection from the Editor.** Detection happens during ingest
  only; there is no "re-detect speakers" route.
- **No cross-session speaker identity.** A speaker is a session-scoped row with no
  link to a speaker in another session.
- **No speaker bios/notes surfaced.** The `speakers.metadata` JSONB column exists
  ([migrations/001_init.sql:75](../../migrations/001_init.sql#L75)) but is never read or
  written by the speaker endpoints.
- **Two-state role pill hides real roles.** The panel's role pill only shows
  `MODERATOR` vs `SPEAKER`; ingest-seeded `Instructor` and the export-only `primary`
  role are not selectable from the UI
  ([SpeakerEditPanel.vue:39-41](../../frontend/src/components/editor/SpeakerEditPanel.vue#L39)).

## Source Verification
- **Files Used:** app/api/session_resources.py, app/api/segments.py, app/api/corrections.py, app/engines/artifact_transformer.py, app/api/exports.py, app/tasks/ai_process.py, app/tasks/align.py, app/api/gcs_upload.py, migrations/001_init.sql, frontend/src/components/editor/SpeakerEditPanel.vue, frontend/src/views/EditorView.vue, frontend/src/services/api.ts, frontend/src/router/index.ts, app/data/help_content.py, docs/product/speakers.md (seed)
- **Components Used:** SpeakerEditPanel.vue, EditorView.vue
- **APIs Used:** GET/POST `/v1/sessions/{id}/speakers`, PATCH/DELETE `/v1/sessions/{id}/speakers/{speaker_id}`, POST `/v1/sessions/{id}/segments/{segment_id}/speaker-reassign`
- **Database Tables Used:** speakers, segments, sessions (FKs), chat_messages (separate participants tally), audit_events (absence noted), correction_ledger (decoupling noted)
- **Permission Logic Used:** JWT presence only (CurrentUser) — no role gate on speaker routes; client-side LEGACY_ADMIN_EMAIL guard exists but does not cover the Editor
- **Confidence Score:** High — every behavior traced to current source; seed-doc claims for "(Unknown)" export, speaker merge, and reassignment-undo were re-verified and found inaccurate, and are corrected above.
- **Evidence Links:** [session_resources.py:206-366](../../app/api/session_resources.py#L206), [migrations/001_init.sql:68-99](../../migrations/001_init.sql#L68), [SpeakerEditPanel.vue:51-99](../../frontend/src/components/editor/SpeakerEditPanel.vue#L51), [artifact_transformer.py:121-193](../../app/engines/artifact_transformer.py#L121), [EditorView.vue:994-1019](../../frontend/src/views/EditorView.vue#L994)
