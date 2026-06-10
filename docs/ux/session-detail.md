# Session Detail Screen

Route: `#/s/:id` (`props: true`, so `id` is a prop). View: [frontend/src/views/SessionDetailView.vue](../../frontend/src/views/SessionDetailView.vue).

## Purpose

The per-session overview/landing page. It presents the session header (status, editable code + title, presenter, review/alignment chips, and links to Editor / Workflow / Audit), a three-column body (meta + downloads, KPI/AI-mode/session-files center, stage-assignments + publishing-links right), a timeline bar, and a row of segment-level widgets (confidence, slide assignment, review queue). It is the hub from which an operator opens the editor, manages stage assignees, and uploads/replaces session files.

## User Types

Any authenticated user. Inline editing of code/title, type/stage reassignment, file uploads, and reset-to-default are all available to every authenticated user — no role-conditional rendering exists in the view.

## Entry Points

- From the Sessions list, a non-`ingesting` row routes here (`/s/:id`) ([SessionsView.vue:98-100](../../frontend/src/views/SessionsView.vue#L98)).
- Direct navigation to `#/s/<id>`.
- Note: dashboard queue cards route to `/e/:id` or `/p/:id` rather than `/s/:id` ([DashboardView.vue:157](../../frontend/src/views/DashboardView.vue#L157)).

## Navigation Paths

- Eyebrow "Sessions" link → `/sessions` ([SessionDetailView.vue:341](../../frontend/src/views/SessionDetailView.vue#L341)).
- Header actions: "Workflow" → `/e/:id/sop`; "Audit" → `/e/:id/audit`; "Open Editor" → `/e/:id` ([SessionDetailView.vue:387-389](../../frontend/src/views/SessionDetailView.vue#L387)).
- "Session not found" state → back link to `/sessions` ([SessionDetailView.vue:350](../../frontend/src/views/SessionDetailView.vue#L350)).

## Components

- **Icon** ([frontend/src/components/shared/Icon.vue](../../frontend/src/components/shared/Icon.vue)) — many (`check`, `branch`, `history`, `edit`, `download`, `alert`, `slide`, `message`, `doc`, `user`).
- **AddFileModal** ([frontend/src/components/session/AddFileModal.vue](../../frontend/src/components/session/AddFileModal.vue)) — the upload/replace dialog for slides/chat/manifest/bios; rendered when a session is loaded ([SessionDetailView.vue:752-760](../../frontend/src/views/SessionDetailView.vue#L752)).
- **SessionTextEdit** ([frontend/src/components/session/SessionTextEdit.vue](../../frontend/src/components/session/SessionTextEdit.vue)) — click-to-edit inline field used for `code` and `title_long` in both the header and meta column ([SessionDetailView.vue:361-368](../../frontend/src/views/SessionDetailView.vue#L361), [:372-380](../../frontend/src/views/SessionDetailView.vue#L372), [:397-416](../../frontend/src/views/SessionDetailView.vue#L397)). It PATCHes the session itself and emits `save` so the parent updates local state.
- **StageBadge** — imported in the prototype lineage but this view uses `SOP_STAGES` directly for the stage-assignment rows; no `StageBadge` render appears in the read template. (The component is not referenced in the template body.)

Major template regions (inside the `v-else` "loaded" branch):
- Header strip: status chip, editable code chip, editable title, presenter, review/alignment chips, action buttons ([SessionDetailView.vue:353-391](../../frontend/src/views/SessionDetailView.vue#L353)).
- `sd-grid` three columns: meta + downloads ([:394-437](../../frontend/src/views/SessionDetailView.vue#L394)); center KPIs + Alignment + Chat Participants + AI Mode + Session files ([:439-528](../../frontend/src/views/SessionDetailView.vue#L439)); right Stage Assignments + Publishing Links ([:530-665](../../frontend/src/views/SessionDetailView.vue#L530)).
- Timeline card ([:668-696](../../frontend/src/views/SessionDetailView.vue#L668)).
- Segment widgets: Segment Confidence, Slide Assignment, Review Queue ([:698-749](../../frontend/src/views/SessionDetailView.vue#L698)).

## Actions

- **Edit code / title inline** — via SessionTextEdit; on save, `onCodeSaved` / `onTitleSaved` patch local `session` state ([SessionDetailView.vue:61-68](../../frontend/src/views/SessionDetailView.vue#L61)). The PATCH itself (`sessionsApi.update`) happens inside SessionTextEdit ([SessionTextEdit.vue:77-78](../../frontend/src/components/session/SessionTextEdit.vue#L77)).
- **Change session Type** — `onTypePickerChange` immediately PATCHes `session_type_id`, then sets `pendingTypeId` to surface the "apply defaults?" banner ([SessionDetailView.vue:131-146](../../frontend/src/views/SessionDetailView.vue#L131), [:535-545](../../frontend/src/views/SessionDetailView.vue#L535)).
- **Apply Type defaults** — `applyTypeDefaults` opens a danger confirm, then POSTs apply-type-defaults and refetches stage assignees ([SessionDetailView.vue:148-168](../../frontend/src/views/SessionDetailView.vue#L148), [:561-565](../../frontend/src/views/SessionDetailView.vue#L561)); "Dismiss" clears the banner ([:170-172](../../frontend/src/views/SessionDetailView.vue#L170), [:566](../../frontend/src/views/SessionDetailView.vue#L566)).
- **Reassign stage assignee** — `openReassign` toggles an inline picker per stage; `selectAssignee` PUTs `{ person_id }` or `{ group_id }` ([SessionDetailView.vue:174-194](../../frontend/src/views/SessionDetailView.vue#L174), [:625-645](../../frontend/src/views/SessionDetailView.vue#L625)).
- **Reset stage to Type default** — `resetStageToDefault` PUTs an empty body (backend resets to the Type matrix) ([SessionDetailView.vue:196-212](../../frontend/src/views/SessionDetailView.vue#L196), [:597-604](../../frontend/src/views/SessionDetailView.vue#L597)).
- **Add / Update session file** — `fileAction(f)` opens AddFileModal with the mapped type; on `success`, toasts and refetches via `load()` ([SessionDetailView.vue:319-327](../../frontend/src/views/SessionDetailView.vue#L319), [:518-522](../../frontend/src/views/SessionDetailView.vue#L518)).
- **Download buttons** — `downloadFile(ext)` only pushes a `warn` toast that export "ships with Phase 10 exports endpoint"; no download occurs ([SessionDetailView.vue:299-304](../../frontend/src/views/SessionDetailView.vue#L299)). `PARTIALLY IMPLEMENTED`.
- **Publishing-link chips** — `pubLink(p)` only pushes a `warn` toast "link not persisted — publishing-link CRUD ships with Phase 10"; no persistence ([SessionDetailView.vue:329-335](../../frontend/src/views/SessionDetailView.vue#L329)). `PARTIALLY IMPLEMENTED`.

## States

- **Loading** — `loading` ref true during `load()` ([SessionDetailView.vue:73](../../frontend/src/views/SessionDetailView.vue#L73), [:93-122](../../frontend/src/views/SessionDetailView.vue#L93)).
- **Error** — `error` set if the `Promise.all` block throws ([SessionDetailView.vue:117-118](../../frontend/src/views/SessionDetailView.vue#L117)).
- **Not found** — `session` is `null` (the `sessionsApi.get` resolves to `null` on failure via `.catch(() => null)`) ([SessionDetailView.vue:98](../../frontend/src/views/SessionDetailView.vue#L98), [:348](../../frontend/src/views/SessionDetailView.vue#L348)).
- **Loaded** — full layout renders ([SessionDetailView.vue:352](../../frontend/src/views/SessionDetailView.vue#L352)).
- **Pending-type banner** — shown when `pendingTypeId` is set ([SessionDetailView.vue:547-567](../../frontend/src/views/SessionDetailView.vue#L547)).
- **Inline reassign picker open** — `reassignStageOpen === st.id` ([SessionDetailView.vue:613-647](../../frontend/src/views/SessionDetailView.vue#L613)).
- Derived chips: `alignedPct`/`alignedChipClass` (green ≥100, amber ≥80, red below, ghost when 0 segments) and `reviewSegs` count ([SessionDetailView.vue:242-250](../../frontend/src/views/SessionDetailView.vue#L242), [:385-386](../../frontend/src/views/SessionDetailView.vue#L385)).

## Empty States

The layout is designed to render intact for never-ingested sessions; many sub-regions have their own empties:
- **Chat Participants** — "No chat yet." when `chatParticipants.length === 0` ([SessionDetailView.vue:471](../../frontend/src/views/SessionDetailView.vue#L471)).
- **Timeline** — "No slides yet — ingest pending." when `slides.length === 0` ([SessionDetailView.vue:688-690](../../frontend/src/views/SessionDetailView.vue#L688)).
- **Segment Confidence** — "No segments yet." when `segConfList.length === 0` ([SessionDetailView.vue:706](../../frontend/src/views/SessionDetailView.vue#L706)).
- **Slide Assignment** — "No slides yet." when `slides.length === 0` ([SessionDetailView.vue:722](../../frontend/src/views/SessionDetailView.vue#L722)).
- **Review Queue** — "No segments flagged for review." when `reviewQueue.length === 0` ([SessionDetailView.vue:738](../../frontend/src/views/SessionDetailView.vue#L738)).
- **Session files** — each file row shows PRESENT/MISSING chips and an Add/Update button based on `hasFile(role)` ([SessionDetailView.vue:508-523](../../frontend/src/views/SessionDetailView.vue#L508)); the card header shows "N missing" or "all present" ([:503-505](../../frontend/src/views/SessionDetailView.vue#L503)).
- **Taxonomy tags** — falls back to a single "untagged" chip when `session.taxonomy` is empty ([SessionDetailView.vue:419](../../frontend/src/views/SessionDetailView.vue#L419)).

## Error States

- **Top-level error** — when not loading and `error` is set, a centered red message shows the error string ([SessionDetailView.vue:347](../../frontend/src/views/SessionDetailView.vue#L347)). Note: every individual fetch in `load()` is wrapped in `.catch(() => default)`, so partial failures degrade silently to empty sub-sections rather than tripping this branch; only an unexpected throw populates `error` ([SessionDetailView.vue:97-122](../../frontend/src/views/SessionDetailView.vue#L97)).
- **Not-found** — "Session not found." with a back link ([SessionDetailView.vue:348-351](../../frontend/src/views/SessionDetailView.vue#L348)).
- **Action errors** — type change, apply-defaults, reassign, and reset failures are toasted via `errMsg(err)` (unwraps `ApiError` detail.message) ([SessionDetailView.vue:143-144](../../frontend/src/views/SessionDetailView.vue#L143), [:163-164](../../frontend/src/views/SessionDetailView.vue#L163), [:189-190](../../frontend/src/views/SessionDetailView.vue#L189), [:207-208](../../frontend/src/views/SessionDetailView.vue#L207), [:214-223](../../frontend/src/views/SessionDetailView.vue#L214)).

## Loading States

- **Top-level** — "Loading session…" centered text while `loading` ([SessionDetailView.vue:346](../../frontend/src/views/SessionDetailView.vue#L346)).
- **Apply-type button** — label toggles to "Applying…" and disables while `applyingType` ([SessionDetailView.vue:563-565](../../frontend/src/views/SessionDetailView.vue#L563)).
- **Reassign picker** — person/group chips are `:disabled="reassignSaving"` with a `progress` cursor while a save is in flight ([SessionDetailView.vue:629-631](../../frontend/src/views/SessionDetailView.vue#L629), [:642-644](../../frontend/src/views/SessionDetailView.vue#L642)).
- AddFileModal has its own internal phase machine (idle → uploading → committing → conflict → done → error) ([AddFileModal.vue:78-79](../../frontend/src/components/session/AddFileModal.vue#L78), [:389-428](../../frontend/src/components/session/AddFileModal.vue#L389)).

## Permissions

Guarded route — requires `isAuthenticated` ([router/index.ts:58-62](../../frontend/src/router/index.ts#L58)). No role gate. Every authenticated user can edit code/title, change Type, reassign/reset stages, and upload files — there is no `LEGACY_ADMIN_EMAIL` or role check in this view or its child components. The backend routes it calls are all JWT-gated via `CurrentUser` with no role enforcement (e.g. update/get/stage-assignees — [app/api/sessions.py:345](../../app/api/sessions.py#L345), [:379](../../app/api/sessions.py#L379), [:498](../../app/api/sessions.py#L498), [:547](../../app/api/sessions.py#L547), [:569](../../app/api/sessions.py#L569)).

## Connected APIs

On mount, `load()` fires nine calls in parallel, each `.catch`-defaulted ([SessionDetailView.vue:97-116](../../frontend/src/views/SessionDetailView.vue#L97)):

- `GET /v1/sessions/{id}` — `sessionsApi.get` ([api.ts:139-140](../../frontend/src/services/api.ts#L139); backend [app/api/sessions.py:547](../../app/api/sessions.py#L547)).
- `GET /v1/sessions/{id}/sources` — raw `http<SourceRow[]>` ([SessionDetailView.vue:99](../../frontend/src/views/SessionDetailView.vue#L99); backend [app/api/session_resources.py:381](../../app/api/session_resources.py#L381)).
- `GET /v1/sessions/{id}/slides` — raw `http<SlideRow[]>` ([SessionDetailView.vue:100](../../frontend/src/views/SessionDetailView.vue#L100); backend [app/api/session_resources.py:58](../../app/api/session_resources.py#L58)).
- `GET /v1/sessions/{id}/segments` — `segmentsApi.list` ([api.ts:618-620](../../frontend/src/services/api.ts#L618); backend [app/api/segments.py:70](../../app/api/segments.py#L70)).
- `GET /v1/sessions/{id}/stage-assignees` — `sessionsApi.stageAssignees` ([api.ts:145-146](../../frontend/src/services/api.ts#L145); backend [app/api/sessions.py:345](../../app/api/sessions.py#L345)).
- `GET /v1/settings/types` — `settingsApi.types` ([api.ts:837](../../frontend/src/services/api.ts#L837)).
- `GET /v1/settings/people` — `settingsApi.people` (filtered to active) ([api.ts:783](../../frontend/src/services/api.ts#L783), [SessionDetailView.vue:114](../../frontend/src/views/SessionDetailView.vue#L114)).
- `GET /v1/settings/groups` — `settingsApi.groups` ([api.ts:790](../../frontend/src/services/api.ts#L790)).
- `GET /v1/sessions/{id}/chat-participants` — `sessionsApi.chatParticipants` ([api.ts:218-221](../../frontend/src/services/api.ts#L218); backend [app/api/session_resources.py:639](../../app/api/session_resources.py#L639)).

Action-triggered calls:
- `PATCH /v1/sessions/{id}` — `sessionsApi.update` (Type change, and via SessionTextEdit for code/title) ([api.ts:143-144](../../frontend/src/services/api.ts#L143); backend [app/api/sessions.py:569](../../app/api/sessions.py#L569)).
- `POST /v1/sessions/{id}/stage-assignees/apply-type-defaults` — `sessionsApi.applyTypeDefaults` ([api.ts:157-163](../../frontend/src/services/api.ts#L157); backend [app/api/sessions.py:498](../../app/api/sessions.py#L498)).
- `PUT /v1/sessions/{id}/stage-assignees/{stage}` — `sessionsApi.setStageAssignee` (reassign + reset) ([api.ts:147-156](../../frontend/src/services/api.ts#L147); backend [app/api/sessions.py:379](../../app/api/sessions.py#L379)).
- AddFileModal: `GET /v1/settings` (read `upload_backend`), then either multipart `POST /v1/sessions/{id}/add/{type}` (railway) or `POST .../add/signed-url` → browser PUT → commit `POST .../add/{type}` (gcs) ([AddFileModal.vue:90-97](../../frontend/src/components/session/AddFileModal.vue#L90), [:143-247](../../frontend/src/components/session/AddFileModal.vue#L143); backend [app/api/add_to_session.py:450](../../app/api/add_to_session.py#L450)).

Note: `downloadFile` and `pubLink` make no API calls (toast-only).

## Data Sources

- Live refs hydrated by `load()`: `session`, `sources`, `slides`, `segments`, `stageAssignments`, `sessionTypes`, `teamPeople`, `teamGroups`, `chatParticipants` ([SessionDetailView.vue:69-83](../../frontend/src/views/SessionDetailView.vue#L69), [:108-116](../../frontend/src/views/SessionDetailView.vue#L108)).
- `SOP_STAGES` fixture — drives the stage-assignment rows ([SessionDetailView.vue:23](../../frontend/src/views/SessionDetailView.vue#L23), [:76](../../frontend/src/views/SessionDetailView.vue#L76), [:569](../../frontend/src/views/SessionDetailView.vue#L569)).
- `slideAccent` from the transcript fixture — colors timeline/segment dots ([SessionDetailView.vue:37](../../frontend/src/views/SessionDetailView.vue#L37), [:282](../../frontend/src/views/SessionDetailView.vue#L282)).
- Computed views: `displayTitle` (title_long → title_short → title cascade) ([:53-59](../../frontend/src/views/SessionDetailView.vue#L53)), `alignedSegs`/`reviewSegs`/`alignedPct` ([:242-244](../../frontend/src/views/SessionDetailView.vue#L242)), `segmentsBySlide` ([:264-269](../../frontend/src/views/SessionDetailView.vue#L264)), `reviewQueue` (top 10 flagged segments) ([:271-278](../../frontend/src/views/SessionDetailView.vue#L271)), `segConfList` (first 31 segments) ([:280-283](../../frontend/src/views/SessionDetailView.vue#L280)), `totalChatMessages` ([:285-287](../../frontend/src/views/SessionDetailView.vue#L285)).
- Hard-coded literals: `publishingLinks`, `downloads`, and the "Avg Confidence — —" KPI ([:225-231](../../frontend/src/views/SessionDetailView.vue#L225), [:443](../../frontend/src/views/SessionDetailView.vue#L443)). The review-queue `assignee` is hard-coded to `'unassigned'` ([:277](../../frontend/src/views/SessionDetailView.vue#L277)).

## Source Verification
- **Files Used:** frontend/src/views/SessionDetailView.vue, frontend/src/components/session/AddFileModal.vue, frontend/src/components/session/SessionTextEdit.vue, frontend/src/components/shared/Icon.vue, frontend/src/services/api.ts, frontend/src/router/index.ts, app/api/sessions.py, app/api/session_resources.py, app/api/segments.py, app/api/add_to_session.py
- **Components Used:** Icon, AddFileModal, SessionTextEdit
- **APIs Used:** GET /v1/sessions/{id}, GET /v1/sessions/{id}/sources, GET /v1/sessions/{id}/slides, GET /v1/sessions/{id}/segments, GET /v1/sessions/{id}/stage-assignees, GET /v1/settings/types, GET /v1/settings/people, GET /v1/settings/groups, GET /v1/sessions/{id}/chat-participants, PATCH /v1/sessions/{id}, POST /v1/sessions/{id}/stage-assignees/apply-type-defaults, PUT /v1/sessions/{id}/stage-assignees/{stage}; (via AddFileModal) GET /v1/settings, POST /v1/sessions/{id}/add/{type}, POST /v1/sessions/{id}/add/signed-url
- **Database Tables Used:** none queried directly by the view
- **Permission Logic Used:** JWT presence (route guard); no role check on view or any wired route
- **Confidence Score:** High — view + both editing child components fully read; all nine load calls and four action calls trace to verified backend routes.
- **Evidence Links:** [SessionDetailView.vue:93-122](../../frontend/src/views/SessionDetailView.vue#L93-L122), [SessionDetailView.vue:131-212](../../frontend/src/views/SessionDetailView.vue#L131-L212), [SessionDetailView.vue:299-335](../../frontend/src/views/SessionDetailView.vue#L299-L335), [api.ts:136-221](../../frontend/src/services/api.ts#L136-L221), [app/api/sessions.py:345-547](../../app/api/sessions.py#L345-L547)
