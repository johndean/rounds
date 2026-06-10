# Speaker Management — Demo Questions (Code-Verified)

> Module key: `speakers`. Every answer below is traceable to source. Claims that the
> code does not support are stated as "not implemented" rather than implied. Paths are
> relative to this file at `ai-demo-knowledge/demo-questions/`.

---

## User

### Q: How do I fix a speaker's name so it's corrected everywhere in the transcript?
- **Verified Answer:** Open the Speakers panel (Editor right rail), click the
  speaker's name, edit it, and click out (or press Enter). Because every segment points
  at the same speaker row by `speaker_id`, renaming the one row corrects the label on
  every segment that references it. The panel sends a single PATCH and then re-fetches
  the roster.
- **Supporting Evidence:** `renameSpeaker` PATCHes the name on blur/Enter
  ([SpeakerEditPanel.vue:51-63](../../frontend/src/components/editor/SpeakerEditPanel.vue#L51),
  [:101-105](../../frontend/src/components/editor/SpeakerEditPanel.vue#L101)); segments
  reference one speaker row via `segments.speaker_id`
  ([migrations/001_init.sql:86](../../migrations/001_init.sql#L86)); exports read the
  name through that join ([artifact_transformer.py:574-577](../../app/engines/artifact_transformer.py#L574)).
- **Source Files:** frontend/src/components/editor/SpeakerEditPanel.vue, app/api/session_resources.py, app/engines/artifact_transformer.py
- **API References:** PATCH `/v1/sessions/{id}/speakers/{speaker_id}`
- **Database References:** speakers.name, segments.speaker_id

### Q: One segment is attributed to the wrong person. Can I fix just that segment?
- **Verified Answer:** Yes. Reassigning a single segment changes only that segment's
  speaker; the rest are untouched. The backend updates `segments.speaker_id` for that
  one segment and validates the target speaker and the segment both belong to the
  session.
- **Supporting Evidence:** `onReassignSpeakerLive` calls the reassign endpoint
  ([EditorView.vue:994-1019](../../frontend/src/views/EditorView.vue#L994)); the handler
  updates one segment after validation
  ([session_resources.py:318-366](../../app/api/session_resources.py#L318)).
- **Source Files:** frontend/src/views/EditorView.vue, app/api/session_resources.py
- **API References:** POST `/v1/sessions/{id}/segments/{segment_id}/speaker-reassign`
- **Database References:** segments.speaker_id, speakers

### Q: The AI missed a speaker. Can I add one?
- **Verified Answer:** Yes. Click **Add speaker**, type the name, and click **Add**.
  The new speaker is created with role `speaker` and a default avatar color; you can
  toggle the role afterward.
- **Supporting Evidence:** `addSpeaker` POSTs `{ name, role: 'speaker' }`
  ([SpeakerEditPanel.vue:78-89](../../frontend/src/components/editor/SpeakerEditPanel.vue#L78));
  server defaults `avatar_color` to `#2563eb`
  ([session_resources.py:248](../../app/api/session_resources.py#L248)).
- **Source Files:** frontend/src/components/editor/SpeakerEditPanel.vue, app/api/session_resources.py
- **API References:** POST `/v1/sessions/{id}/speakers`
- **Database References:** speakers (name, role, avatar_color)

### Q: What happens to a speaker's segments if I delete that speaker?
- **Verified Answer:** The segments are kept — they just lose their speaker
  attribution. The `speaker_id` foreign key is set to NULL automatically on delete, so
  no transcript text is lost. On the next export, those segments simply have no speaker
  label prefix.
- **Supporting Evidence:** FK `ON DELETE SET NULL`
  ([migrations/001_init.sql:86](../../migrations/001_init.sql#L86)); delete handler
  ([session_resources.py:292-315](../../app/api/session_resources.py#L292)); export
  omits the prefix when `speaker_name` is falsy
  ([artifact_transformer.py:121-124](../../app/engines/artifact_transformer.py#L121)).
- **Source Files:** migrations/001_init.sql, app/api/session_resources.py, app/engines/artifact_transformer.py
- **API References:** DELETE `/v1/sessions/{id}/speakers/{speaker_id}`
- **Database References:** speakers, segments.speaker_id

### Q: I have one person showing up as two speakers. How do I merge them?
- **Verified Answer:** There is no one-click speaker merge. To consolidate, reassign
  each of the duplicate's segments to the speaker you want to keep, then delete the
  duplicate. (Note: the help-center copy mentions "merge," but no speaker-merge endpoint
  exists — the only "merge" in the codebase merges adjacent transcript *segments* of the
  same speaker, not two speaker identities.)
- **Supporting Evidence:** No speaker-merge route exists in the speakers API
  ([session_resources.py:180-366](../../app/api/session_resources.py#L180)); the merge
  service operates on adjacent same-speaker segments
  ([app/services/segment_merge.py:23-68](../../app/services/segment_merge.py#L23));
  help copy referencing "merge" ([app/data/help_content.py:111](../../app/data/help_content.py#L111),
  [:131](../../app/data/help_content.py#L131)).
- **Source Files:** app/api/session_resources.py, app/services/segment_merge.py, app/data/help_content.py
- **API References:** POST `/v1/sessions/{id}/segments/{segment_id}/speaker-reassign` then DELETE `/v1/sessions/{id}/speakers/{speaker_id}`
- **Database References:** speakers, segments.speaker_id

---

## Operations

### Q: When a session finishes processing, are speakers already populated?
- **Verified Answer:** Yes. Ingest seeds the roster. The AI-mode path wipes any existing
  rows for the session and inserts one speaker per unique label (defaulting the label to
  `Presenter` and role to `Instructor`). The legacy STT/align path inserts a single
  `Presenter`/`Instructor` row if none exists. The manifest bridge inserts manifest-named
  speakers idempotently.
- **Supporting Evidence:** [ai_process.py:388-410](../../app/tasks/ai_process.py#L388);
  [align.py:148-152](../../app/tasks/align.py#L150);
  [gcs_upload.py:292-304](../../app/api/gcs_upload.py#L292).
- **Source Files:** app/tasks/ai_process.py, app/tasks/align.py, app/api/gcs_upload.py
- **API References:** none (Celery ingest tasks)
- **Database References:** speakers

### Q: A session was ingested before the speaker roster looked right. Can I re-run speaker detection?
- **Verified Answer:** Not as a standalone action. Speaker detection runs only as part
  of ingest; there is no "re-detect speakers" endpoint or background job. The supported
  recovery is to refine the roster by hand, or re-run the whole ingest pipeline via the
  operator reingest diagnostic (which resets the session and re-seeds speakers along
  with everything else).
- **Supporting Evidence:** No re-detect route in the speakers API
  ([session_resources.py:180-366](../../app/api/session_resources.py#L180)); seeding only
  occurs inside ingest tasks (above). Full reingest is an operator-only diag endpoint
  (`/v1/diag/reingest/{id}`) per project guidance, not a speakers-module feature.
- **Source Files:** app/api/session_resources.py, app/tasks/ai_process.py
- **API References:** none speaker-specific (re-seed only via full reingest)
- **Database References:** speakers

### Q: How does an operator reassign many segments at once to the same speaker?
- **Verified Answer:** There is no bulk endpoint — reassignment is one segment per call.
  Each reassignment is an independent POST to the speaker-reassign route. Reassigning N
  segments is N calls.
- **Supporting Evidence:** Reassign handler operates on a single `segment_id`
  ([session_resources.py:318-366](../../app/api/session_resources.py#L318)); the frontend
  wrapper takes one segment id ([api.ts:328-332](../../frontend/src/services/api.ts#L328)).
- **Source Files:** app/api/session_resources.py, frontend/src/services/api.ts
- **API References:** POST `/v1/sessions/{id}/segments/{segment_id}/speaker-reassign`
- **Database References:** segments.speaker_id

### Q: If a list-speakers call fails in the Editor, does the panel break?
- **Verified Answer:** No. The roster reload is best-effort — a failed list call logs a
  warning and leaves the existing roster in place rather than clearing it or throwing.
- **Supporting Evidence:** `reloadSpeakers` catches the error and returns null without
  mutating the list ([EditorView.vue:539-552](../../frontend/src/views/EditorView.vue#L539)).
- **Source Files:** frontend/src/views/EditorView.vue
- **API References:** GET `/v1/sessions/{id}/speakers`
- **Database References:** speakers

---

## Compliance

### Q: Are speaker changes recorded in the audit ledger?
- **Verified Answer:** No. Adding, renaming, role-toggling, deleting a speaker, and the
  dedicated single-segment speaker-reassign all commit their database change **without**
  writing an `audit_events` row. This is unlike segment text edits, segment slide
  reassignment, and chat/poll reorder, which all write audit events. Speaker mutations
  are therefore not captured in the audit trail today.
- **Supporting Evidence:** No audit insert in any speaker handler
  ([session_resources.py:228-366](../../app/api/session_resources.py#L228)); compare to
  audited paths ([session_resources.py:578-589](../../app/api/session_resources.py#L578)
  reorder, [segments.py:213-219](../../app/api/segments.py#L213) segment edit).
- **Source Files:** app/api/session_resources.py, app/api/segments.py
- **API References:** all speaker routes
- **Database References:** audit_events (no insert), speakers, segments

### Q: Can a speaker reassignment be undone?
- **Verified Answer:** Not through the undo/redo (correction-ledger) system. The
  frontend reassigns by calling the `/speaker-reassign` endpoint, which mutates
  `segments.speaker_id` but writes no correction-ledger row. A `speaker_reassignment`
  correction *type* exists in the allow-list, and the endpoint's own docstring says
  callers "should also" record one so undo works, but the frontend does not, and the
  generic corrections flow does not mutate `speaker_id` for that type. So reassignment is
  outside undo/redo and is reversed only by reassigning again.
- **Supporting Evidence:** Reassign endpoint writes no ledger row
  ([session_resources.py:318-366](../../app/api/session_resources.py#L318)); frontend
  calls only the reassign route ([EditorView.vue:994-1019](../../frontend/src/views/EditorView.vue#L994));
  `speaker_reassignment` allowed but the generic flow only materializes `text_edit` to the
  segment column ([corrections.py:52](../../app/api/corrections.py#L52),
  [:578-593](../../app/api/corrections.py#L578)).
- **Source Files:** app/api/session_resources.py, app/api/corrections.py, frontend/src/views/EditorView.vue
- **API References:** POST `/v1/sessions/{id}/segments/{segment_id}/speaker-reassign`; POST `/v1/sessions/{id}/corrections` (decoupled)
- **Database References:** segments.speaker_id, correction_ledger (no row), audit_events (no row)

### Q: Can a user from one session reassign or edit a speaker belonging to another session?
- **Verified Answer:** No. Edit, delete, and reassign all scope their SQL by the path
  `session_id`, and reassign additionally validates that both the target speaker and the
  segment belong to that session. A mismatched id returns 404 instead of mutating.
- **Supporting Evidence:** Session-scoped statements and 404 guards
  ([session_resources.py:271-272](../../app/api/session_resources.py#L271),
  [:307-313](../../app/api/session_resources.py#L307),
  [:332-356](../../app/api/session_resources.py#L332)).
- **Source Files:** app/api/session_resources.py
- **API References:** PATCH/DELETE `/v1/sessions/{id}/speakers/{speaker_id}`, POST `.../speaker-reassign`
- **Database References:** speakers, segments

---

## Administrator

### Q: Which roles are allowed to edit speakers — is this admin-only?
- **Verified Answer:** It is not role-gated. Every speaker endpoint requires only a valid
  JWT (the `CurrentUser` dependency) and never checks the user's email or role. The only
  admin gate in the product is a client-side router check comparing the logged-in email to
  a hardcoded address, and the Editor route (which hosts the Speakers panel) is not behind
  that flag. So any authenticated user can add, rename, reassign, and delete speakers.
- **Supporting Evidence:** Handlers take `_user: CurrentUser` with no role check
  ([session_resources.py:207](../../app/api/session_resources.py#L207),
  [:230](../../app/api/session_resources.py#L230),
  [:258](../../app/api/session_resources.py#L258),
  [:294](../../app/api/session_resources.py#L294),
  [:321](../../app/api/session_resources.py#L321)); client-only admin gate
  ([frontend/src/router/index.ts:49-66](../../frontend/src/router/index.ts#L49)).
- **Source Files:** app/api/session_resources.py, frontend/src/router/index.ts
- **API References:** all speaker routes
- **Database References:** none (auth via JWT)

### Q: What are the valid role values, and does the UI expose all of them?
- **Verified Answer:** `speakers.role` is a free-text column. The panel's role pill is
  two-state only — it shows `MODERATOR` for any role that lowercases to `moderator`, and
  `SPEAKER` for everything else, and toggling writes exactly `moderator` or `speaker`.
  Ingest writes `Instructor`, which the pill displays as `SPEAKER`. The export engine has a
  special navy-bold style for role `primary`, but neither the UI nor ingest ever produces
  `primary`, so that branch isn't reached by current role values.
- **Supporting Evidence:** Role column is free TEXT
  ([migrations/001_init.sql:73](../../migrations/001_init.sql#L73)); two-state label +
  toggle ([SpeakerEditPanel.vue:39-41](../../frontend/src/components/editor/SpeakerEditPanel.vue#L39),
  [:65-76](../../frontend/src/components/editor/SpeakerEditPanel.vue#L65)); ingest role
  `Instructor` ([ai_process.py:403](../../app/tasks/ai_process.py#L403)); `primary`-only
  navy style ([artifact_transformer.py:187-193](../../app/engines/artifact_transformer.py#L187)).
- **Source Files:** migrations/001_init.sql, frontend/src/components/editor/SpeakerEditPanel.vue, app/tasks/ai_process.py, app/engines/artifact_transformer.py
- **API References:** PATCH `/v1/sessions/{id}/speakers/{speaker_id}`
- **Database References:** speakers.role

### Q: Why does the speaker list sort by name rather than creation order?
- **Verified Answer:** The `speakers` table has no `created_at` column, so the list query
  deliberately orders by `name ASC`. An earlier version referenced `created_at` and 500'd
  on every call; the current query is the fix.
- **Supporting Evidence:** Table has no `created_at`
  ([migrations/001_init.sql:69-76](../../migrations/001_init.sql#L69)); list orders by name
  with an explaining comment ([session_resources.py:208-224](../../app/api/session_resources.py#L208)).
- **Source Files:** migrations/001_init.sql, app/api/session_resources.py
- **API References:** GET `/v1/sessions/{id}/speakers`
- **Database References:** speakers

---

## Power User

### Q: Two endpoints can change a segment's speaker — which one does the Editor use, and what's the difference?
- **Verified Answer:** The Editor uses the dedicated POST `.../speaker-reassign` route
  (via `speakers.reassignSegment`). There is also a general `PATCH .../segments/{id}` that
  accepts `speaker_id` in its body; that PATCH path writes a `corrections` row plus a
  `segment.edit` audit event, whereas the dedicated reassign route writes neither. The
  Editor's segment reassignment therefore leaves no audit/correction trail.
- **Supporting Evidence:** Frontend wrapper hits the dedicated route
  ([api.ts:328-332](../../frontend/src/services/api.ts#L328)); reassign route writes no
  audit/correction ([session_resources.py:318-366](../../app/api/session_resources.py#L318));
  segment PATCH accepts `speaker_id` and writes corrections + audit
  ([segments.py:39](../../app/api/segments.py#L39),
  [:202-219](../../app/api/segments.py#L202)).
- **Source Files:** frontend/src/services/api.ts, app/api/session_resources.py, app/api/segments.py
- **API References:** POST `.../speaker-reassign` vs PATCH `.../segments/{segment_id}`
- **Database References:** segments.speaker_id, corrections, audit_events

### Q: What exactly does the `SpeakerOut.short` field contain?
- **Verified Answer:** It's always identical to `name`. The SQL selects `name AS short,
  name`, so `short` is just an alias of `name`, not a separate abbreviation. The frontend
  `SessionSpeaker` interface carries both fields but they hold the same value.
- **Supporting Evidence:** Query selects `name AS short, name`
  ([session_resources.py:216](../../app/api/session_resources.py#L216),
  [:241](../../app/api/session_resources.py#L241)); interface
  ([api.ts:232-238](../../frontend/src/services/api.ts#L232)).
- **Source Files:** app/api/session_resources.py, frontend/src/services/api.ts
- **API References:** GET/POST `/v1/sessions/{id}/speakers`
- **Database References:** speakers.name

### Q: Does an unattributed segment export as the literal text "(Unknown)"?
- **Verified Answer:** No. Despite a "BR-017 Unknown speaker fallback" mention in the
  export module docstrings, the actual export code emits no `(Unknown)` string — it simply
  omits the speaker prefix when the segment has no speaker. So an unattributed segment
  exports as plain text with no name in front of it.
- **Supporting Evidence:** Docstring mentions BR-017
  ([artifact_transformer.py:11](../../app/engines/artifact_transformer.py#L11)) but
  `to_txt`/`to_docx`/`_build_marked_transcript` gate the prefix on truthiness only, with no
  `(Unknown)` literal ([:121-124](../../app/engines/artifact_transformer.py#L121),
  [:187-193](../../app/engines/artifact_transformer.py#L187),
  [:229-232](../../app/engines/artifact_transformer.py#L229)).
- **Source Files:** app/engines/artifact_transformer.py
- **API References:** export endpoints (consume the transformer)
- **Database References:** segments.speaker_id (null → no prefix), speakers.name

### Q: Is there a WebSocket broadcast when a speaker is added or reassigned?
- **Verified Answer:** No. None of the speaker handlers publish a WS event; the Editor
  keeps its roster in sync by re-fetching after the panel emits a local `changed` event,
  and by an optimistic in-place splice after a segment reassignment.
- **Supporting Evidence:** No WS call in speaker handlers
  ([session_resources.py:228-366](../../app/api/session_resources.py#L228)); panel emits
  `changed` ([SpeakerEditPanel.vue:24](../../frontend/src/components/editor/SpeakerEditPanel.vue#L24));
  splice for reactivity ([EditorView.vue:1012](../../frontend/src/views/EditorView.vue#L1012)).
- **Source Files:** app/api/session_resources.py, frontend/src/components/editor/SpeakerEditPanel.vue, frontend/src/views/EditorView.vue
- **API References:** all speaker routes
- **Database References:** speakers, segments

---

## Source Verification
- **Files Used:** app/api/session_resources.py, app/api/segments.py, app/api/corrections.py, app/engines/artifact_transformer.py, app/tasks/ai_process.py, app/tasks/align.py, app/api/gcs_upload.py, app/services/segment_merge.py, app/data/help_content.py, migrations/001_init.sql, frontend/src/components/editor/SpeakerEditPanel.vue, frontend/src/views/EditorView.vue, frontend/src/services/api.ts, frontend/src/router/index.ts
- **Components Used:** SpeakerEditPanel.vue, EditorView.vue
- **APIs Used:** GET/POST `/v1/sessions/{id}/speakers`, PATCH/DELETE `/v1/sessions/{id}/speakers/{speaker_id}`, POST `/v1/sessions/{id}/segments/{segment_id}/speaker-reassign`, PATCH `/v1/sessions/{id}/segments/{segment_id}`, POST `/v1/sessions/{id}/corrections`
- **Database Tables Used:** speakers, segments, sessions, audit_events (absence), correction_ledger (decoupling), chat_messages (separate tally)
- **Permission Logic Used:** JWT presence only (CurrentUser); no role gate on speaker routes; client-side LEGACY_ADMIN_EMAIL guard does not cover the Editor
- **Confidence Score:** High — answers trace to current code; "(Unknown)" export, speaker merge, and reassignment-undo claims were re-verified and corrected per the actual implementation.
- **Evidence Links:** [session_resources.py:206-366](../../app/api/session_resources.py#L206), [SpeakerEditPanel.vue:51-99](../../frontend/src/components/editor/SpeakerEditPanel.vue#L51), [artifact_transformer.py:121-193](../../app/engines/artifact_transformer.py#L121), [migrations/001_init.sql:69-104](../../migrations/001_init.sql#L69), [corrections.py:52-593](../../app/api/corrections.py#L52)
