# Chat & Polls — Demo Questions

Code-verified Q&A for the Chat & Polls module of rounds.vin. Every answer is traceable to source. Personas with nothing code-true to ask are omitted.

---

## User

### Q: How do I attach a chat message or poll to the right spot in the transcript?
- **Verified Answer:** Drag the chat row or poll card from the right-rail Chat/Polls tab onto the transcript segment where it belongs. The card snaps to that segment and shows a `PLACED · Slide NN` pill. You can also click **Place at active** / **Place** to attach it to the currently active segment.
- **Supporting Evidence:** Drag sets MIME `application/vnd.mic.anchor`; drop calls `handleDropOnSegment`; `handlePlaceAtActive` routes the button to the active segment.
- **Source Files:** frontend/src/components/editor/ChatTab.vue:89, PollsTab.vue:44, frontend/src/views/EditorView.vue:700, :715
- **API References:** PATCH `/v1/sessions/{id}/chat/{message_id}`, PATCH `/v1/sessions/{id}/polls/{poll_id}/anchor`
- **Database References:** chat_messages.anchor_segment, polls.anchor_segment

### Q: How do I move or detach an item I already placed?
- **Verified Answer:** Drag the inline anchor block in the transcript to a different segment to re-anchor it (no detach step needed — the backend upserts the anchor). To detach, click **× Remove**; the item returns to the right-rail list as unplaced.
- **Supporting Evidence:** `onAnchorDragStart` re-fires the placement MIME; `handleRemoveAnchor` sets the anchor to null.
- **Source Files:** frontend/src/components/editor/AnchorBlock.vue:63, frontend/src/views/EditorView.vue:686
- **API References:** PATCH `/v1/sessions/{id}/chat/{id}` / `/polls/{id}/anchor` with `anchor_segment: null`
- **Database References:** chat_messages.placed, polls.placed

### Q: Can I reorder the chat or poll lists?
- **Verified Answer:** Yes. Hover a row to reveal the `⇅` grip and drag it to a new position. Reorder uses a separate drag type so it won't accidentally place the item on a segment.
- **Supporting Evidence:** Grip uses MIME `application/vnd.rounds.reorder-chat` / `...reorder-poll`; emits `reorder(ids)`.
- **Source Files:** frontend/src/components/editor/ChatTab.vue:21, :171, PollsTab.vue:15, frontend/src/views/EditorView.vue:724
- **API References:** PATCH `/v1/sessions/{id}/chat/order`, `/polls/order`
- **Database References:** chat_messages.order_index, polls.order_index

### Q: Do I have to place every chat message?
- **Verified Answer:** No. Most chat is context only; the design is to place notable questions and key moments and leave the rest unplaced. An empty/unplaced state is a clean, expected state.
- **Supporting Evidence:** Seed guidance plus the unplaced default (`placed=false`) at ingest and empty-array endpoints.
- **Source Files:** docs/product/polls-chat-resources.md:30, app/api/session_resources.py:4
- **API References:** GET `/v1/sessions/{id}/chat`
- **Database References:** chat_messages.placed (default false)

### Q: Can I edit the text of a chat message or a poll question?
- **Verified Answer:** Partially. A **placed** chat row has an Edit button that saves through the corrections audit. Editing inside the inline transcript anchor block does NOT persist — it shows a "not persisted" warning. Poll options/votes are not editable through any working endpoint.
- **Supporting Evidence:** `handleChatEdit` posts a `chat_edit` correction; `AnchorBlock.save()` only toasts a warning.
- **Source Files:** frontend/src/views/EditorView.vue:760, frontend/src/components/editor/AnchorBlock.vue:45, ChatTab.vue:51
- **API References:** corrections apply (chat_edit) — POST corrections endpoint
- **Database References:** chat_messages (text via correction); no poll-edit table write

---

## Operations

### Q: Polls came in unplaced for an old session — how do I fix them in bulk?
- **Verified Answer:** Run the auto-placement diagnostic. `POST /v1/diag/autoplace-polls/{session_id}` re-runs `auto_place_polls`, which anchors every unplaced poll to the first segment of its declared slide. There is also migration 037 that backfilled this across all sessions at once.
- **Supporting Evidence:** Diagnostic calls `auto_place_polls(engine, session_id)`; migration 037 runs the same algorithm across every session.
- **Source Files:** app/api/diagnostics.py:265, app/services/poll_autoplace.py:84, migrations/037_backfill_poll_anchors.sql:19
- **API References:** POST `/v1/diag/autoplace-polls/{session_id}`
- **Database References:** polls.anchor_segment, polls.placed, polls.metadata->>'slide_n'

### Q: When does poll auto-placement run during ingest?
- **Verified Answer:** At ingest completion. The direct-mode task (`ai_process`) and the enhanced-pipeline finalizer (`finalize`) both call `auto_place_polls`. It's wrapped in try/except so a failure logs a warning and the session still completes — polls just stay unplaced for manual drag.
- **Supporting Evidence:** Both tasks import and call `auto_place_polls`; both call sites are non-fatal.
- **Source Files:** app/tasks/ai_process.py:520, app/tasks/finalize.py:113, app/services/poll_autoplace.py:84
- **API References:** none (Celery task path)
- **Database References:** polls, segments, slides

### Q: Why did some polls stay unplaced even after auto-placement ran?
- **Verified Answer:** Auto-place only anchors a poll when its `metadata.slide_n` maps to a slide that has at least one aligned segment (a segment with that `slide_id`). Polls whose slide had no aligned segment, or whose manifest header lacked a slide number, are skipped and stay unplaced for manual drag.
- **Supporting Evidence:** UPDATE filters on `metadata ? 'slide_n'` and the `slide_index + 1 = slide_n` join; service docstring notes skipped-when-no-segment behavior.
- **Source Files:** app/services/poll_autoplace.py:37, :60, app/api/gcs_upload.py:330
- **API References:** GET `/v1/sessions/{id}/polls`
- **Database References:** polls.metadata, slides.slide_index, segments.slide_id

### Q: How does chat get into a session that was uploaded without it?
- **Verified Answer:** Use the add-to-session chat path: `POST /v1/sessions/{id}/add/chat` with the chat `.txt` (multipart or a staged `gcs_uri`). If the session already has chat, you get a 409 with previews; re-send with `?confirm=true` to replace. The file is parsed and inserted as unplaced messages.
- **Supporting Evidence:** `add_chat` intakes the file, conflicts on existing chat unless confirm, deletes then re-inserts.
- **Source Files:** app/api/add_to_session.py:597, :619, :645
- **API References:** POST `/v1/sessions/{id}/add/chat?confirm=true`
- **Database References:** chat_messages

### Q: What chat export formats are supported?
- **Verified Answer:** Two Zoom/webinar formats, auto-detected from the first line: Format 1 (`HH:MM:SS<tab>Speaker:<tab>Message`) and Format 2 (`YYYY-MM-DD HH:MM:SS From Speaker to Recipient:`). Unrecognized input parses to zero messages (never errors). Direct messages are flagged but not excluded.
- **Supporting Evidence:** `parse_chat_file` regex-detects the two formats; logs a warning and returns `[]` otherwise.
- **Source Files:** app/engines/chat_parser.py:25, :35, :40
- **API References:** POST `/v1/sessions/{id}/add/chat`
- **Database References:** chat_messages.author, chat_messages.body, chat_messages.sent_at_ms

---

## Compliance

### Q: Which Chat & Polls actions are written to the audit ledger?
- **Verified Answer:** Reorders are audited — each chat/poll reorder writes an `audit_events` row (`kind = 'chat.reorder'` / `'polls.reorder'`) with the actor email, a count summary, and the first 3 ids. Ingest writes `upload.complete.chat` / `upload.complete.manifest` rows. Drag-placement (set/clear anchor) is NOT written to the audit ledger — only the structured `anchor_segment` column changes.
- **Supporting Evidence:** Reorder handlers INSERT into `audit_events`; the anchor PATCH handlers do not.
- **Source Files:** app/api/session_resources.py:580, :780, :598, :795, app/api/gcs_upload.py:452
- **API References:** PATCH `/chat/order`, `/polls/order`
- **Database References:** audit_events (actor_email, kind, summary, details)

### Q: Is poll/chat edit history preserved?
- **Verified Answer:** Placement state lives in the structured `anchor_segment`/`placed` columns rather than a versioned ledger, so re-anchoring overwrites the prior anchor without a history row. The one persisted text edit (placed chat) goes through the corrections audit. Inline AnchorBlock edits do not persist at all.
- **Supporting Evidence:** Anchor UPDATE overwrites in place; placed-chat edit posts a `chat_edit` correction; AnchorBlock save only warns.
- **Source Files:** app/api/session_resources.py:609, frontend/src/views/EditorView.vue:771, frontend/src/components/editor/AnchorBlock.vue:45
- **API References:** PATCH anchor endpoints; corrections apply
- **Database References:** chat_messages.anchor_segment, corrections (via chat_edit)

### Q: Who can place, reorder, or detach chat and polls?
- **Verified Answer:** Any authenticated user. Every Chat & Polls endpoint requires only a valid JWT (`CurrentUser`). There is no role check — the identity carries only an email and `auth_users.role` is never read for authorization. The repo's hardcoded `johndean@vin.com` admin gate and the client-side `adminOnly` guard (only on `/admin/help`) do not apply here.
- **Supporting Evidence:** Handlers depend on `CurrentUser`; `User` has only `email`; `get_current_user` doesn't load role; router adminOnly is only `/admin/help`.
- **Source Files:** app/api/session_resources.py:18, app/auth.py:37, :172, frontend/src/router/index.ts:63
- **API References:** all `/v1/sessions/{id}/chat*` and `/polls*` endpoints
- **Database References:** auth_users.role (exists but unused for authz)

---

## Administrator

### Q: Is there an admin-only restriction on editing chat or polls?
- **Verified Answer:** No. Role-based auth is scaffold-only in this repo and is not wired into these endpoints. `app.security.roles.is_admin/require_admin` is not imported by `session_resources.py` or `add_to_session.py`. The only admin gate anywhere is the hardcoded `LEGACY_ADMIN_EMAIL` email check used by other modules and one client-side route guard — neither touches Chat & Polls.
- **Supporting Evidence:** No roles import in the module; CurrentUser-only deps; router guard scoped to `/admin/help`.
- **Source Files:** app/api/session_resources.py:18, app/auth.py:172, frontend/src/router/index.ts:63
- **API References:** none gate these routes beyond JWT presence
- **Database References:** none for authz

### Q: How do I re-run poll placement for one session manually?
- **Verified Answer:** Call the operator diagnostic `POST /v1/diag/autoplace-polls/{session_id}` with a logged-in token. It builds a sync engine and calls `auto_place_polls`, returning the count placed. Idempotent — already-placed polls are untouched.
- **Supporting Evidence:** Diagnostic constructs an engine and calls the service; the service UPDATE filters `WHERE anchor_segment IS NULL`.
- **Source Files:** app/api/diagnostics.py:265, app/services/poll_autoplace.py:77
- **API References:** POST `/v1/diag/autoplace-polls/{session_id}`
- **Database References:** polls.anchor_segment, polls.placed

---

## Power User

### Q: How is list order determined when some rows are reordered and some aren't?
- **Verified Answer:** The list query orders by `(order_index IS NULL) ASC, order_index ASC, sent_at_ms/opened_at_ms ASC`. Rows you've reordered get an explicit 1-indexed `order_index` and surface in that order; un-reordered rows (NULL order_index) sort after, in chronological order. The first reorder promotes the whole list to explicit order_index.
- **Supporting Evidence:** ORDER BY clauses in `list_chat`/`list_polls`; reorder sets `order_index=position`.
- **Source Files:** app/api/session_resources.py:511, :716, :570, migrations/052_chat_polls_order_index.sql:9
- **API References:** GET `/chat`, GET `/polls`, PATCH `/chat/order`, `/polls/order`
- **Database References:** chat_messages.order_index, polls.order_index

### Q: What makes the reorder safe against partial failure?
- **Verified Answer:** Every id in the body must already belong to the session (else 400 with the offending ids), the renumber is a single `jsonb_to_recordset`-driven UPDATE, and the whole thing is one transaction. A bad request can't leave a half-renumbered list. The client also aborts if the incoming id set size differs from the current list (concurrent add).
- **Supporting Evidence:** Membership check + single-statement UPDATE + commit; client size-mismatch guard.
- **Source Files:** app/api/session_resources.py:548, :570, frontend/src/views/EditorView.vue:730
- **API References:** PATCH `/chat/order`, `/polls/order`
- **Database References:** chat_messages, polls

### Q: How are polls turned from the manifest text into structured rows?
- **Verified Answer:** `extras2_parser.parse_polls_section` regex-extracts `Slide N - Poll Question #M` headers, the question line, and `count (pct%) label` options. At upload, `gcs_upload` inserts each into `polls` (`status='closed'`, `opened_at_ms=0`, `total_votes` = sum of option counts, `metadata={slide_n,q_n,source:'extras2'}`) plus `poll_options` rows.
- **Supporting Evidence:** Parser regex + the bridge INSERT loop.
- **Source Files:** app/services/extras2_parser.py:196, :202, app/api/gcs_upload.py:309
- **API References:** POST upload-complete (manifest path); GET `/v1/sessions/{id}/polls`
- **Database References:** polls, poll_options, polls.metadata

### Q: Why is the slide number off-by-one in the data, and how is it reconciled?
- **Verified Answer:** The manifest emits `slide_n` as 1-based ("Slide 7"), but `slides.slide_index` is stored 0-based. Auto-placement and the backfill bridge the two with `slides.slide_index + 1 = poll.metadata.slide_n` in the join.
- **Supporting Evidence:** Convention note + the join predicate in both the service and migration 037.
- **Source Files:** app/services/poll_autoplace.py:30, :79, migrations/037_backfill_poll_anchors.sql:14
- **API References:** none (data layer)
- **Database References:** slides.slide_index, polls.metadata->>'slide_n'

### Q: Where does the Chat Participants tally come from?
- **Verified Answer:** `GET /v1/sessions/{id}/chat-participants` aggregates `chat_messages` by author, returning `message_count`, `first_seen_ms`, `last_seen_ms` per speaker, ordered by count desc then author asc. It's read-only and returns `[]` for sessions without chat.
- **Supporting Evidence:** GROUP BY author with MIN/MAX timestamps; ordered count desc, author asc.
- **Source Files:** app/api/session_resources.py:639, :657, frontend/src/services/api.ts:218
- **API References:** GET `/v1/sessions/{id}/chat-participants`
- **Database References:** chat_messages (author, sent_at_ms)

---

## Source Verification
- **Files Used:** app/api/session_resources.py, app/api/add_to_session.py, app/api/gcs_upload.py, app/api/diagnostics.py, app/services/poll_autoplace.py, app/services/extras2_parser.py, app/engines/chat_parser.py, app/auth.py, app/tasks/ai_process.py, app/tasks/finalize.py, migrations/008_chat_polls.sql, migrations/052_chat_polls_order_index.sql, migrations/037_backfill_poll_anchors.sql, frontend/src/components/editor/ChatTab.vue, PollsTab.vue, AnchorBlock.vue, frontend/src/views/EditorView.vue, frontend/src/services/api.ts, frontend/src/router/index.ts, docs/product/polls-chat-resources.md
- **Components Used:** ChatTab.vue, PollsTab.vue, AnchorBlock.vue, EditorView.vue
- **APIs Used:** GET/PATCH `/v1/sessions/{id}/chat`, `/chat/order`, `/chat/{id}`, `/chat-participants`, `/polls`, `/polls/order`, `/polls/{id}/anchor`; POST `/add/chat`; POST `/v1/diag/autoplace-polls/{id}`
- **Database Tables Used:** chat_messages, polls, poll_options, segments, slides, sessions, audit_events, auth_users (role unused)
- **Permission Logic Used:** JWT presence only (CurrentUser). No role gate; LEGACY_ADMIN_EMAIL + client adminOnly guard do not apply.
- **Confidence Score:** High — every answer maps to a read source line.
- **Evidence Links:** [session_resources.py:527](../../app/api/session_resources.py#L527), [:639](../../app/api/session_resources.py#L639), [:795](../../app/api/session_resources.py#L795), [poll_autoplace.py:84](../../app/services/poll_autoplace.py#L84), [gcs_upload.py:309](../../app/api/gcs_upload.py#L309), [diagnostics.py:265](../../app/api/diagnostics.py#L265), [router/index.ts:63](../../frontend/src/router/index.ts#L63)
