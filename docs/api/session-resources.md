# API Reference — `session_resources`

Router source: [app/api/session_resources.py](../../app/api/session_resources.py)

Mounted in [app/main.py:217](../../app/main.py#L217) via `app.include_router(session_resources_router.router)`.

Router prefix: `/v1/sessions/{session_id}` (declared at [app/api/session_resources.py:21](../../app/api/session_resources.py#L21)). Tag: `sessions`.

This router covers the per-session **sub-resources** consumed by the editor and session-detail views: slides, captioned video, speakers, segment speaker reassignment, sources, media URL, words, chat (+ participants + reorder + anchor), and polls (+ reorder + anchor). It defines **16 endpoints**. Per the module docstring, list endpoints are safe against empty sessions and return `[]` until ingest produces rows ([app/api/session_resources.py:1-8](../../app/api/session_resources.py#L1)).

## Authentication & authorization model (verified)

- **Authentication** = a valid JWT bearer token. Every endpoint takes a `CurrentUser` dependency (`_user` where the email is unused, `user` on the two reorder routes that write `audit_events.actor_email`). Resolution is `get_current_user` ([app/auth.py:172](../../app/auth.py#L172)); missing/invalid token → `401`.
- **Authorization** is **JWT-only for all 16 endpoints**. There is no `require_admin`, no `LEGACY_ADMIN_EMAIL` check, and no `SESSION_TRASH_ALLOWED` gate anywhere in this file — any authenticated user may call any of these. (Role-based auth is scaffold-only repo-wide; see [app/security/roles.py:10-19](../../app/security/roles.py#L10).)
- Most handlers scope writes/reads by `session_id` in the SQL (`WHERE session_id = :sid`), and several validate that a child id belongs to the session before mutating — but that is row-scoping, not authorization. There is **no per-session ownership/ACL check** tying the calling user to the session.

> **Response envelope:** all JSON is wrapped by `EnvelopeMiddleware` into `{success, data, error, meta}` ([app/middleware/envelope.py:196](../../app/middleware/envelope.py#L196)). The schemas below describe the `data` payload. `204 No Content` responses pass through unwrapped ([app/middleware/envelope.py:224](../../app/middleware/envelope.py#L224)).

---

## POST `/v1/sessions/{session_id}/slides/re-extract`

- **Decorator:** [app/api/session_resources.py:39](../../app/api/session_resources.py#L39) — `@router.post("/slides/re-extract")`
- **Method:** POST
- **Purpose:** Re-extract specific PDF pages on operator request (Phase 7h) by enqueueing `slide_extract_selected_pages_task` ([:40-45](../../app/api/session_resources.py#L40)).
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID); body `ReExtractRequest` ([:35](../../app/api/session_resources.py#L35)) — `page_indices: list[int]` (1-based page numbers).
- **Response Schema:** `dict` — `{"enqueued": true, "page_indices": [...]}` on success; `{"enqueued": false, "error": "<ExcClass>: <msg>"}` if enqueue raised ([:53-55](../../app/api/session_resources.py#L53)).
- **Validation Rules:** None beyond Pydantic typing; task dispatched to the `celery` queue.
- **Errors:** No HTTP error raised — enqueue failures are returned in-body as `enqueued: false`.
- **Example:** `POST /v1/sessions/<id>/slides/re-extract` body `{"page_indices":[3,4,5]}`
- **Related Screens:** Editor slide pane (re-extract action).
- **Related Tables:** none directly (enqueues a Celery task; `slides` is written by the task).

---

## GET `/v1/sessions/{session_id}/slides`

- **Decorator:** [app/api/session_resources.py:58](../../app/api/session_resources.py#L58) — `@router.get("/slides", response_model=list[SlideOut])`
- **Method:** GET
- **Purpose:** List slides for a session ordered by `slide_index` ([:58-71](../../app/api/session_resources.py#L58)).
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID).
- **Response Schema:** `list[SlideOut]` ([:25](../../app/api/session_resources.py#L25)) — `id` (UUID), `slide_index` (int), `title` (str|null), `image_uri` (str|null), `start_ms` (int|null), `end_ms` (int|null).
- **Validation Rules:** None.
- **Errors:** None; `[]` when empty.
- **Example:** `GET /v1/sessions/<id>/slides`
- **Related Screens:** Editor / Viewer slide rail.
- **Related Tables:** `slides`.

---

## POST `/v1/sessions/{session_id}/captions/burn`

- **Decorator:** [app/api/session_resources.py:92](../../app/api/session_resources.py#L92) — `@router.post("/captions/burn")`
- **Method:** POST
- **Purpose:** Kick off `burn_captions_task` (Phase 10.1) to produce a captioned MP4 in GCS; frontend listens for the `captioned_video_ready` WS event ([:93-101](../../app/api/session_resources.py#L93)).
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID); body `BurnCaptionsRequest` ([:75](../../app/api/session_resources.py#L75)) — `style_config: dict|null` (ASS-style overrides).
- **Response Schema:** `dict` — `{"enqueued": true, "session_id": str}` ([:125](../../app/api/session_resources.py#L125)).
- **Validation Rules:** Verifies at least one `sources` row with `role='video'` exists before enqueueing ([:104-117](../../app/api/session_resources.py#L104)); dispatched to the `celery` queue.
- **Errors:**
  - `400` — `detail="No video source available — captions can only be burned into video sessions."` when no video source ([:114](../../app/api/session_resources.py#L114)).
  - `500` — `detail="Failed to enqueue burn task: <ExcClass>: <msg>"` if dispatch raises ([:127](../../app/api/session_resources.py#L127)).
- **Example:** `POST /v1/sessions/<id>/captions/burn` body `{"style_config":{"FontSize":28}}`
- **Related Screens:** Editor captions/burn action — [frontend/src/services/api.ts:207](../../frontend/src/services/api.ts#L207).
- **Related Tables:** `sources` (read precondition); `artifacts` written by the task.

---

## GET `/v1/sessions/{session_id}/captioned-video`

- **Decorator:** [app/api/session_resources.py:130](../../app/api/session_resources.py#L130) — `@router.get("/captioned-video", response_model=Optional[CaptionedVideoArtifact])`
- **Method:** GET
- **Purpose:** Return the current captioned-video artifact (or null), regenerating a fresh 1-hour signed URL on every call (Phase 10.1) ([:131-138](../../app/api/session_resources.py#L131)).
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID).
- **Response Schema:** `CaptionedVideoArtifact` or `null` ([:81](../../app/api/session_resources.py#L81)) — `artifact_id` (str), `gcs_uri` (str), `download_url` (str|null, signed 1h), `bytes` (int|null), `version` (int), `is_current` (bool), `generated_at` (ISO|null), `style_config` (dict|null).
- **Validation Rules:** Selects the most recent `artifacts` row where `kind='captioned_video' AND is_current=TRUE`. Signed-URL generation failure is swallowed (`download_url` stays null) ([:162-166](../../app/api/session_resources.py#L162)).
- **Errors:** None; returns `null` when no artifact exists.
- **Example:** `GET /v1/sessions/<id>/captioned-video`
- **Related Screens:** Editor captioned-video download — [frontend/src/services/api.ts:215](../../frontend/src/services/api.ts#L215).
- **Related Tables:** `artifacts`.

---

## GET `/v1/sessions/{session_id}/speakers`

- **Decorator:** [app/api/session_resources.py:206](../../app/api/session_resources.py#L206) — `@router.get("/speakers", response_model=list[SpeakerOut])`
- **Method:** GET
- **Purpose:** List speakers for a session ([:207](../../app/api/session_resources.py#L207)).
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID).
- **Response Schema:** `list[SpeakerOut]` ([:181](../../app/api/session_resources.py#L181)) — `id` (UUID), `short` (str|null, aliased from `name`), `name` (str|null), `role` (str|null), `avatar_color` (str|null).
- **Validation Rules:** Ordered by `name ASC` (the `speakers` table has no `created_at` column — comment at [:208-211](../../app/api/session_resources.py#L208)).
- **Errors:** None; `[]` when empty.
- **Example:** `GET /v1/sessions/<id>/speakers`
- **Related Screens:** Editor speaker roster — [frontend/src/services/api.ts:312](../../frontend/src/services/api.ts#L312).
- **Related Tables:** `speakers`.

---

## POST `/v1/sessions/{session_id}/speakers`

- **Decorator:** [app/api/session_resources.py:228](../../app/api/session_resources.py#L228) — `@router.post("/speakers", response_model=SpeakerOut, status_code=201)`
- **Method:** POST
- **Purpose:** Add a speaker to a session (Phase 9) to fix roster mistakes post-ingest ([:229-234](../../app/api/session_resources.py#L229)).
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID); body `SpeakerCreate` ([:190](../../app/api/session_resources.py#L190)) — `name` (str, required), `role` (str|null), `avatar_color` (str|null).
- **Response Schema:** `SpeakerOut`, HTTP **201**.
- **Validation Rules:** `avatar_color` defaults to `"#2563eb"` when not supplied ([:248](../../app/api/session_resources.py#L248)).
- **Errors:** None handler-raised.
- **Example:** `POST /v1/sessions/<id>/speakers` body `{"name":"Dr. Lee","role":"Presenter"}`
- **Related Screens:** Editor add-speaker — [frontend/src/services/api.ts:315](../../frontend/src/services/api.ts#L315).
- **Related Tables:** `speakers`.

---

## PATCH `/v1/sessions/{session_id}/speakers/{speaker_id}`

- **Decorator:** [app/api/session_resources.py:256](../../app/api/session_resources.py#L256) — `@router.patch("/speakers/{speaker_id}", response_model=SpeakerOut)`
- **Method:** PATCH
- **Purpose:** Edit a speaker; only supplied fields change (omitted preserved via `COALESCE`) (Phase 9) ([:261-262](../../app/api/session_resources.py#L261)).
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID), `speaker_id` (UUID); body `SpeakerPatch` ([:196](../../app/api/session_resources.py#L196)) — all optional: `name`, `role`, `avatar_color`.
- **Response Schema:** `SpeakerOut`.
- **Validation Rules:** Update scoped by both `id` AND `session_id`, so a speaker from another session cannot be edited.
- **Errors:** `404` — `detail="Speaker {speaker_id} not in session {session_id}"` when no row matches ([:287](../../app/api/session_resources.py#L287)).
- **Example:** `PATCH /v1/sessions/<id>/speakers/<sid>` body `{"role":"Moderator"}`
- **Related Screens:** Editor edit-speaker — [frontend/src/services/api.ts:320](../../frontend/src/services/api.ts#L320).
- **Related Tables:** `speakers`.

---

## DELETE `/v1/sessions/{session_id}/speakers/{speaker_id}`

- **Decorator:** [app/api/session_resources.py:292](../../app/api/session_resources.py#L292) — `@router.delete("/speakers/{speaker_id}", status_code=204)`
- **Method:** DELETE
- **Purpose:** Remove a speaker (Phase 9). Segments referencing it have `speaker_id` set NULL via FK `ON DELETE SET NULL` ([:293-302](../../app/api/session_resources.py#L293)).
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID), `speaker_id` (UUID).
- **Response Schema:** **204 No Content** — returns `Response(status_code=204)` ([:315](../../app/api/session_resources.py#L315)); envelope skips 204.
- **Validation Rules:** Delete scoped by both `id` AND `session_id`.
- **Errors:** `404` — `detail="Speaker {speaker_id} not in session {session_id}"` when `rowcount == 0` ([:313](../../app/api/session_resources.py#L313)).
- **Example:** `DELETE /v1/sessions/<id>/speakers/<sid>`
- **Related Screens:** Editor remove-speaker — [frontend/src/services/api.ts:325](../../frontend/src/services/api.ts#L325).
- **Related Tables:** `speakers` (+ `segments.speaker_id` SET NULL).

---

## POST `/v1/sessions/{session_id}/segments/{segment_id}/speaker-reassign`

- **Decorator:** [app/api/session_resources.py:318](../../app/api/session_resources.py#L318) — `@router.post("/segments/{segment_id}/speaker-reassign", response_model=SpeakerOut)`
- **Method:** POST
- **Purpose:** Change which speaker a segment is attributed to (Phase 9), validating both belong to the session ([:319-329](../../app/api/session_resources.py#L319)).
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID), `segment_id` (UUID); body `SpeakerReassignRequest` ([:202](../../app/api/session_resources.py#L202)) — `speaker_id` (UUID, required).
- **Response Schema:** `SpeakerOut` (the target speaker row).
- **Validation Rules:** Verifies the target speaker belongs to the session, then the segment belongs to the session, before updating `segments.speaker_id`. Per the docstring, callers SHOULD also record a `speaker_reassignment` correction in the same flow for undo (not enforced here) ([:326-329](../../app/api/session_resources.py#L326)).
- **Errors:**
  - `404` — `detail="Speaker {speaker_id} not in session {session_id}"` ([:343](../../app/api/session_resources.py#L343)).
  - `404` — `detail="Segment {segment_id} not in session {session_id}"` ([:356](../../app/api/session_resources.py#L356)).
- **Example:** `POST /v1/sessions/<id>/segments/<seg>/speaker-reassign` body `{"speaker_id":"<spk>"}`
- **Related Screens:** Editor segment speaker reassignment — [frontend/src/services/api.ts:330](../../frontend/src/services/api.ts#L330).
- **Related Tables:** `speakers`, `segments`.

---

## GET `/v1/sessions/{session_id}/sources`

- **Decorator:** [app/api/session_resources.py:381](../../app/api/session_resources.py#L381) — `@router.get("/sources", response_model=list[SourceOut])`
- **Method:** GET
- **Purpose:** List uploaded source files for the session ([:382](../../app/api/session_resources.py#L382)).
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID).
- **Response Schema:** `list[SourceOut]` ([:370](../../app/api/session_resources.py#L370)) — `id` (UUID), `role` (str), `filename` (str), `gcs_uri` (str), `content_type` (str|null), `size_bytes` (int|null), `duration_sec` (int|null).
- **Validation Rules:** Ordered by `created_at ASC`.
- **Errors:** None; `[]` when empty.
- **Example:** `GET /v1/sessions/<id>/sources`
- **Related Screens:** Session detail / processing sources list.
- **Related Tables:** `sources`.

---

## GET `/v1/sessions/{session_id}/media-url`

- **Decorator:** [app/api/session_resources.py:406](../../app/api/session_resources.py#L406) — `@router.get("/media-url", response_model=MediaUrlOut)`
- **Method:** GET
- **Purpose:** Return a 24h signed GET URL for the session's primary playback source ([:407-418](../../app/api/session_resources.py#L407)).
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID); query `role` (str, default `"audio"`; pass `video` for the visual track).
- **Response Schema:** `MediaUrlOut` ([:398](../../app/api/session_resources.py#L398)) — `role` (str), `filename` (str|null), `content_type` (str|null), `duration_sec` (int|null), `url` (str, signed v4 GET, 24h TTL).
- **Validation Rules:** Selects `sources` rows with `role IN ('audio','video')`, preferring the requested role then `created_at ASC`; falls through to the other role if the preferred one is missing.
- **Errors:** `404` — `detail="No audio/video source for this session."` when neither exists ([:437](../../app/api/session_resources.py#L437)).
- **Example:** `GET /v1/sessions/<id>/media-url?role=video`
- **Related Screens:** Editor / Viewer media player — [frontend/src/services/api.ts:346](../../frontend/src/services/api.ts#L346).
- **Related Tables:** `sources`.

---

## GET `/v1/sessions/{session_id}/words`

- **Decorator:** [app/api/session_resources.py:461](../../app/api/session_resources.py#L461) — `@router.get("/words", response_model=list[WordOut])`
- **Method:** GET
- **Purpose:** Return real per-word Google STT tokens for the session ordered along the timeline ([:462-469](../../app/api/session_resources.py#L462)).
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID).
- **Response Schema:** `list[WordOut]` ([:450](../../app/api/session_resources.py#L450)) — `id` (UUID), `segment_id` (UUID), `seq` (int), `word` (str), `start_ms` (int), `end_ms` (int), `confidence` (float).
- **Validation Rules:** Joins `words` → `segments`, filtered by `segments.session_id`, ordered by `segments.start_ms ASC, words.seq ASC`. Returns `[]` if STT has not run.
- **Errors:** None; `[]` when empty.
- **Example:** `GET /v1/sessions/<id>/words`
- **Related Screens:** Editor STT/words pane — [frontend/src/services/api.ts:282](../../frontend/src/services/api.ts#L282).
- **Related Tables:** `words`, `segments`.

---

## GET `/v1/sessions/{session_id}/chat`

- **Decorator:** [app/api/session_resources.py:499](../../app/api/session_resources.py#L499) — `@router.get("/chat", response_model=list[ChatMessageOut])`
- **Method:** GET
- **Purpose:** List chat messages for the session, honoring operator reordering ([:500-504](../../app/api/session_resources.py#L500)).
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID).
- **Response Schema:** `list[ChatMessageOut]` ([:489](../../app/api/session_resources.py#L489)) — `id` (UUID), `author` (str), `body` (str), `sent_at_ms` (int), `anchor_segment` (UUID|null), `placed` (bool).
- **Validation Rules:** Ordered by `(order_index IS NULL) ASC, order_index ASC, sent_at_ms ASC` so reordered rows surface in new positions, others chronologically.
- **Errors:** None; `[]` when empty.
- **Example:** `GET /v1/sessions/<id>/chat`
- **Related Screens:** Editor chat pane.
- **Related Tables:** `chat_messages`.

---

## PATCH `/v1/sessions/{session_id}/chat/order`

- **Decorator:** [app/api/session_resources.py:527](../../app/api/session_resources.py#L527) — `@router.patch("/chat/order")`
- **Method:** PATCH
- **Purpose:** Bulk-reorder chat messages by setting `order_index = position` (1-indexed) for every id in the array ([:529-542](../../app/api/session_resources.py#L529)).
- **Authentication:** Required (`user: CurrentUser`; email written to `audit_events.actor_email`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID); body `ReorderRequest` ([:520](../../app/api/session_resources.py#L520)) — `ids: list[UUID]` (new desired order).
- **Response Schema:** `dict` — `{"reordered": <n>, "ids": [str,...]}` ([:591](../../app/api/session_resources.py#L591)).
- **Validation Rules:** All-or-nothing transaction. Every id must already belong to this session's `chat_messages`; renumber done in a single `jsonb_to_recordset` UPDATE; writes a `chat.reorder` row to `audit_events`.
- **Errors:**
  - `400 EMPTY_REORDER` — `detail={"code":"EMPTY_REORDER", "message":…}` when `ids` is empty ([:544](../../app/api/session_resources.py#L544)).
  - `400 UNKNOWN_CHAT_IDS` — `detail={"code":"UNKNOWN_CHAT_IDS", "message":"<n> id(s) not in this session", "ids":[…]}` when any id is foreign ([:558](../../app/api/session_resources.py#L558)).
- **Example:** `PATCH /v1/sessions/<id>/chat/order` body `{"ids":["<m1>","<m2>"]}`
- **Related Screens:** Editor chat reorder — [frontend/src/services/api.ts:385](../../frontend/src/services/api.ts#L385).
- **Related Tables:** `chat_messages`, `audit_events`.

---

## PATCH `/v1/sessions/{session_id}/chat/{message_id}`

- **Decorator:** [app/api/session_resources.py:598](../../app/api/session_resources.py#L598) — `@router.patch("/chat/{message_id}", response_model=ChatMessageOut)`
- **Method:** PATCH
- **Purpose:** Persist drag-to-place — set or clear `anchor_segment` + `placed` flag. Idempotent ([:603-604](../../app/api/session_resources.py#L603)).
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID), `message_id` (UUID); body `AnchorPatch` ([:594](../../app/api/session_resources.py#L594)) — `anchor_segment` (UUID|null; null clears placement).
- **Response Schema:** `ChatMessageOut`.
- **Validation Rules:** Update scoped by `id` AND `session_id`; `placed = (:anc IS NOT NULL)`.
- **Errors:** `404` — `detail="Chat message not found in this session."` when no row matches ([:625](../../app/api/session_resources.py#L625)).
- **Example:** `PATCH /v1/sessions/<id>/chat/<mid>` body `{"anchor_segment":"<seg>"}`
- **Related Screens:** Editor chat drag-to-place — [frontend/src/services/api.ts:372](../../frontend/src/services/api.ts#L372).
- **Related Tables:** `chat_messages`.

---

## GET `/v1/sessions/{session_id}/chat-participants`

- **Decorator:** [app/api/session_resources.py:639](../../app/api/session_resources.py#L639) — `@router.get("/chat-participants", response_model=list[ChatParticipantOut])`
- **Method:** GET
- **Purpose:** Aggregate `chat_messages` by author — one row per distinct speaker with message count + first/last timestamps ([:640-656](../../app/api/session_resources.py#L640)).
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** JWT-only (docstring explicitly: "any authenticated user").
- **Request Schema:** path `session_id` (UUID).
- **Response Schema:** `list[ChatParticipantOut]` ([:631](../../app/api/session_resources.py#L631)) — `speaker` (str), `message_count` (int), `first_seen_ms` (int), `last_seen_ms` (int).
- **Validation Rules:** Grouped by `author`, ordered by `COUNT(*) DESC, author ASC`. Read-only.
- **Errors:** None; `[]` when empty.
- **Example:** `GET /v1/sessions/<id>/chat-participants`
- **Related Screens:** SessionDetailView Chat Participants tally — [frontend/src/services/api.ts:220](../../frontend/src/services/api.ts#L220).
- **Related Tables:** `chat_messages`.

---

## GET `/v1/sessions/{session_id}/polls`

- **Decorator:** [app/api/session_resources.py:704](../../app/api/session_resources.py#L704) — `@router.get("/polls", response_model=list[PollOut])`
- **Method:** GET
- **Purpose:** List polls (with their options) for the session, honoring operator reordering ([:705-708](../../app/api/session_resources.py#L705)).
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID).
- **Response Schema:** `list[PollOut]` ([:684](../../app/api/session_resources.py#L684)) — `id` (UUID), `question` (str), `status` (str), `opened_at_ms` (int), `closed_at_ms` (int|null), `total_votes` (int), `anchor_segment` (UUID|null), `placed` (bool), `metadata` (dict|null — extras2 manifest blob with `slide_n`/`q_n`), `options` (list of `PollOptionOut`: `id` UUID, `label` str, `seq` int, `votes` int) ([:676](../../app/api/session_resources.py#L676)).
- **Validation Rules:** Polls ordered by `(order_index IS NULL) ASC, order_index ASC, opened_at_ms ASC`; options fetched per poll ordered by `seq ASC`.
- **Errors:** None; `[]` when empty.
- **Example:** `GET /v1/sessions/<id>/polls`
- **Related Screens:** Editor polls pane.
- **Related Tables:** `polls`, `poll_options`.

---

## PATCH `/v1/sessions/{session_id}/polls/order`

- **Decorator:** [app/api/session_resources.py:739](../../app/api/session_resources.py#L739) — `@router.patch("/polls/order")`
- **Method:** PATCH
- **Purpose:** Bulk-reorder polls (mirror of `/chat/order`) — sets `order_index = position` (1-indexed) ([:740-748](../../app/api/session_resources.py#L740)).
- **Authentication:** Required (`user: CurrentUser`; email written to `audit_events.actor_email`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID); body `ReorderRequest` — `ids: list[UUID]`.
- **Response Schema:** `dict` — `{"reordered": <n>, "ids": [str,...]}` ([:792](../../app/api/session_resources.py#L792)).
- **Validation Rules:** All-or-nothing; every id must belong to this session's `polls`; single `jsonb_to_recordset` UPDATE; writes a `polls.reorder` row to `audit_events`.
- **Errors:**
  - `400 EMPTY_REORDER` — when `ids` is empty ([:750](../../app/api/session_resources.py#L750)).
  - `400 UNKNOWN_POLL_IDS` — `detail={"code":"UNKNOWN_POLL_IDS", "message":"<n> id(s) not in this session", "ids":[…]}` ([:763](../../app/api/session_resources.py#L763)).
- **Example:** `PATCH /v1/sessions/<id>/polls/order` body `{"ids":["<p1>","<p2>"]}`
- **Related Screens:** Editor polls reorder — [frontend/src/services/api.ts:390](../../frontend/src/services/api.ts#L390).
- **Related Tables:** `polls`, `audit_events`.

---

## PATCH `/v1/sessions/{session_id}/polls/{poll_id}/anchor`

- **Decorator:** [app/api/session_resources.py:795](../../app/api/session_resources.py#L795) — `@router.patch("/polls/{poll_id}/anchor")`
- **Method:** PATCH
- **Purpose:** Persist drag-to-place for polls — set or clear `anchor_segment` + `placed`. Idempotent ([:800-801](../../app/api/session_resources.py#L800)).
- **Authentication:** Required (`_user: CurrentUser`).
- **Authorization:** JWT-only.
- **Request Schema:** path `session_id` (UUID), `poll_id` (UUID); body `AnchorPatch` — `anchor_segment` (UUID|null; null clears).
- **Response Schema:** `dict` — the updated poll row: `id`, `question`, `status`, `opened_at_ms`, `closed_at_ms`, `total_votes`, `anchor_segment`, `placed` ([:810-811](../../app/api/session_resources.py#L810)). No `response_model` (options are not re-returned here).
- **Validation Rules:** Update scoped by `id` AND `session_id`; `placed = (:anc IS NOT NULL)`.
- **Errors:** `404` — `detail="Poll not found in this session."` when no row matches ([:823](../../app/api/session_resources.py#L823)).
- **Example:** `PATCH /v1/sessions/<id>/polls/<pid>/anchor` body `{"anchor_segment":null}`
- **Related Screens:** Editor poll drag-to-place — [frontend/src/services/api.ts:377](../../frontend/src/services/api.ts#L377).
- **Related Tables:** `polls`.

---

## Source Verification
- **Files Used:** app/api/session_resources.py, app/auth.py, app/security/roles.py, app/middleware/envelope.py, app/db.py, app/main.py, frontend/src/services/api.ts
- **Components Used:** none (Vue views consume via api.ts; screen names inferred from service call sites)
- **APIs Used:** POST /slides/re-extract, GET /slides, POST /captions/burn, GET /captioned-video, GET+POST /speakers, PATCH+DELETE /speakers/{id}, POST /segments/{id}/speaker-reassign, GET /sources, GET /media-url, GET /words, GET /chat, PATCH /chat/order, PATCH /chat/{id}, GET /chat-participants, GET /polls, PATCH /polls/order, PATCH /polls/{id}/anchor (all under /v1/sessions/{session_id})
- **Database Tables Used:** slides, artifacts, sources, speakers, segments, words, chat_messages, polls, poll_options, audit_events
- **Permission Logic Used:** JWT presence only — no LEGACY_ADMIN_EMAIL / require_admin / allowlist gate anywhere in this router
- **Confidence Score:** High — all 16 decorators and handler bodies read in source; schemas pulled from the Pydantic models in the same file.
- **Evidence Links:** [app/api/session_resources.py:21](../../app/api/session_resources.py#L21), [app/api/session_resources.py:39](../../app/api/session_resources.py#L39), [app/api/session_resources.py:292](../../app/api/session_resources.py#L292), [app/api/session_resources.py:527](../../app/api/session_resources.py#L527), [app/main.py:217](../../app/main.py#L217)
