# Chat & Polls — Product Spec

## Overview

Chat & Polls is the part of the rounds.vin editor that carries the **live-session chat log and audience polls** from the original recorded meeting into the transcript, lets an operator **anchor (place) each item onto the transcript segment where it belongs**, and renders placed items inline in the transcript as bordered "anchor" blocks. It surfaces in the Editor's right rail under two sub-tabs — **Chat** and **Polls** — plus a **Chat Participants** tally widget on the Session Detail view.

Chat messages are parsed from a Zoom/webinar chat `.txt` export ([app/engines/chat_parser.py](../../app/engines/chat_parser.py)). Polls are parsed from the `extras2.txt` session manifest's `Polls` section ([app/services/extras2_parser.py:202](../../app/services/extras2_parser.py#L202)) and bridged into structured `polls` + `poll_options` rows at upload time ([app/api/gcs_upload.py:309](../../app/api/gcs_upload.py#L309)).

The data lands in three tables — `chat_messages`, `polls`, `poll_options` ([migrations/008_chat_polls.sql](../../migrations/008_chat_polls.sql)) — and is served to the frontend through sub-resource endpoints under `/v1/sessions/{id}/` ([app/api/session_resources.py](../../app/api/session_resources.py)).

## Purpose

- Preserve the audience interaction (chat questions, poll results) that happened during the live session so it can be re-attached to the right moment in the published transcript.
- Give the operator a fast, drag-driven way to **place** a chat message or poll onto a transcript segment, **re-anchor** it, or **detach** it.
- Reduce manual placement work for polls by **auto-anchoring** each poll to the first transcript segment of the slide it was opened on ([app/services/poll_autoplace.py](../../app/services/poll_autoplace.py)).
- Let the operator **reorder** chat and poll rows within their lists when arrival-time order is not the order they want.
- Show a per-author **chat participant tally** at a glance.

## User Value

- **Context without clutter.** Most chat is context only; the operator places the notable questions and key moments and leaves the rest unplaced ([app/api/session_resources.py:7](../../app/api/session_resources.py#L7) — empty/unplaced is a clean state).
- **Polls start placed.** Auto-placement means polls usually arrive already anchored to the right slide's first segment, so the operator only adjusts the ones that look off ([app/services/poll_autoplace.py:16](../../app/services/poll_autoplace.py#L16)).
- **Winner-highlighted poll bars.** Poll cards and inline anchor blocks highlight the option with the most votes ([frontend/src/components/editor/PollsTab.vue:134](../../frontend/src/components/editor/PollsTab.vue#L134), [AnchorBlock.vue:139](../../frontend/src/components/editor/AnchorBlock.vue#L139)).
- **Reversible.** Placement, re-anchor, and detach are all drag actions backed by idempotent PATCH endpoints ([app/api/session_resources.py:598](../../app/api/session_resources.py#L598), [:795](../../app/api/session_resources.py#L795)).

## Navigation

- **Editor right rail → Chat tab** — [ChatTab.vue](../../frontend/src/components/editor/ChatTab.vue), mounted by [EditorView.vue:1481](../../frontend/src/views/EditorView.vue#L1481).
- **Editor right rail → Polls tab** — [PollsTab.vue](../../frontend/src/components/editor/PollsTab.vue), mounted by [EditorView.vue:1492](../../frontend/src/views/EditorView.vue#L1492).
- **Editor transcript pane → inline anchor blocks** — placed chat/poll items render inside the transcript as `AnchorBlock` ([AnchorBlock.vue](../../frontend/src/components/editor/AnchorBlock.vue)), keyed off the `anchorsBySegment` map ([EditorView.vue:668](../../frontend/src/views/EditorView.vue#L668)).
- **Session Detail → Chat Participants widget** — fed by `chatParticipants()` ([frontend/src/services/api.ts:218](../../frontend/src/services/api.ts#L218)) hitting `GET /v1/sessions/{id}/chat-participants`.

The editor route (`#/e/:id`) requires a logged-in user but has no `adminOnly` guard ([frontend/src/router/index.ts:63](../../frontend/src/router/index.ts#L63) — only `/admin/help` is admin-gated).

## Screens

### Chat tab (right rail)
- Section header: `Chat · {count}` with a `{n} placed` count in green ([ChatTab.vue:154](../../frontend/src/components/editor/ChatTab.vue#L154)).
- Rows are grouped under a **slide divider** (`Slide NN · {title}`) for placed messages whose anchor segment belongs to a slide ([ChatTab.vue:64](../../frontend/src/components/editor/ChatTab.vue#L64)).
- Each row shows an avatar, author, **timestamp** (`fmtTime(row.msg.t)`), and body ([ChatTab.vue:178](../../frontend/src/components/editor/ChatTab.vue#L178)). (Seed doc said timestamps are not shown; the code shows them — see Known Constraints.)
- A reorder **grip** (`⇅`) appears on hover ([ChatTab.vue:171](../../frontend/src/components/editor/ChatTab.vue#L171)).
- Placed rows show a `PLACED · Slide NN` pill plus **Edit** and **× Remove** buttons; unplaced rows show `⠿ drag to segment` and a **Place at active** button ([ChatTab.vue:204](../../frontend/src/components/editor/ChatTab.vue#L204)).
- Inline edit textarea with Cancel/Save on a placed row ([ChatTab.vue:183](../../frontend/src/components/editor/ChatTab.vue#L183)).

### Polls tab (right rail)
- Section header: `Polls · {count}` with a `{n} placed` count ([PollsTab.vue:100](../../frontend/src/components/editor/PollsTab.vue#L100)).
- Each poll is a **card** with: a `PLACED · Slide NN` pill or a `Poll · {status}` gold chip, a **Place**/**× Remove** button, the question, option bars (winner-highlighted), and a `Total: {n} votes` footer ([PollsTab.vue:104](../../frontend/src/components/editor/PollsTab.vue#L104)).
- Option bar width and percentage are computed as `votes / total` ([PollsTab.vue:135](../../frontend/src/components/editor/PollsTab.vue#L135)).
- A reorder grip (`⇅`) appears on hover ([PollsTab.vue:114](../../frontend/src/components/editor/PollsTab.vue#L114)).

### Inline anchor block (transcript pane)
- Rendered as a `segment segment--anchor segment--anchor-{kind}` article with `data-anchor-id` ([AnchorBlock.vue:72](../../frontend/src/components/editor/AnchorBlock.vue#L72)).
- Header shows the slide chip (slide number padded to 2 digits), a `Poll`/`Chat` chip, and **Edit**/**Remove** actions ([AnchorBlock.vue:78](../../frontend/src/components/editor/AnchorBlock.vue#L78)).
- Chat blocks show author + text; poll blocks show the question, per-option percentage bars with `is-winner` highlight, and a `{total} responses` line ([AnchorBlock.vue:130](../../frontend/src/components/editor/AnchorBlock.vue#L130)).

### Chat Participants widget (Session Detail)
- One row per distinct author with message count and first/last seen timestamps ([app/api/session_resources.py:639](../../app/api/session_resources.py#L639)); test id `sd-chat-participants` ([frontend/tests/parity-2026-06-05.spec.ts:79](../../frontend/tests/parity-2026-06-05.spec.ts#L79)).

## User Flows

### Place a chat message or poll
1. Operator drags a row from the Chat/Polls tab over a transcript segment. The drag sets MIME `application/vnd.mic.anchor` carrying the item id ([ChatTab.vue:91](../../frontend/src/components/editor/ChatTab.vue#L91), [PollsTab.vue:44](../../frontend/src/components/editor/PollsTab.vue#L44)).
2. The transcript segment's drop handler calls `handleDropOnSegment(itemId, segId)` ([EditorView.vue:700](../../frontend/src/views/EditorView.vue#L700)).
3. The UI updates the `placements` map optimistically, then persists via `chatAnchor` → `PATCH /v1/sessions/{id}/chat/{message_id}` or `pollAnchor` → `PATCH /v1/sessions/{id}/polls/{poll_id}/anchor` with `{anchor_segment}` ([EditorView.vue:705](../../frontend/src/views/EditorView.vue#L705), [api.ts:370](../../frontend/src/services/api.ts#L370)).
4. Backend sets `anchor_segment` and `placed = (anchor IS NOT NULL)` ([app/api/session_resources.py:609](../../app/api/session_resources.py#L609), [:806](../../app/api/session_resources.py#L806)).

### Place at active segment (button)
- Clicking **Place at active** / **Place** calls `handlePlaceAtActive(itemId)`, which routes to `handleDropOnSegment` with the currently active segment ([EditorView.vue:715](../../frontend/src/views/EditorView.vue#L715)).

### Re-anchor a placed item
- Dragging an existing inline `AnchorBlock` re-fires the same placement MIME, so the segment drop handler treats it like a fresh placement and the backend upserts `anchor_segment` — no explicit detach needed ([AnchorBlock.vue:63](../../frontend/src/components/editor/AnchorBlock.vue#L63)).

### Detach (remove placement)
- Clicking **× Remove** on a tab row or the inline anchor block emits `unplace`/`remove`; the parent calls `handleRemoveAnchor(itemId)`, which sets the placement to null and PATCHes `anchor_segment = null` ([EditorView.vue:686](../../frontend/src/views/EditorView.vue#L686), [ChatTab.vue:214](../../frontend/src/components/editor/ChatTab.vue#L214)).

### Reorder a list
1. Operator drags the grip (`⇅`) onto another row. The grip uses a distinct MIME (`application/vnd.rounds.reorder-chat` / `...reorder-poll`) so it can't be consumed by segment-placement drop targets ([ChatTab.vue:21](../../frontend/src/components/editor/ChatTab.vue#L21), [PollsTab.vue:15](../../frontend/src/components/editor/PollsTab.vue#L15)).
2. The tab computes the new id order and emits `reorder` ([ChatTab.vue:139](../../frontend/src/components/editor/ChatTab.vue#L139)).
3. `handleChatReorder` / `handlePollsReorder` optimistically reorders, then PATCHes `chat/order` / `polls/order` with the full id array; reverts on failure ([EditorView.vue:724](../../frontend/src/views/EditorView.vue#L724), [:741](../../frontend/src/views/EditorView.vue#L741)).
4. Backend sets `order_index = position` (1-indexed) for every supplied id in one statement and writes a `chat.reorder` / `polls.reorder` audit event ([app/api/session_resources.py:570](../../app/api/session_resources.py#L570), [:780](../../app/api/session_resources.py#L780)).

### Poll auto-placement (system, not user)
- At ingest completion the pipeline calls `auto_place_polls(engine, session_id)` ([app/tasks/ai_process.py:522](../../app/tasks/ai_process.py#L522), [app/tasks/finalize.py:116](../../app/tasks/finalize.py#L116)). It anchors every unplaced poll whose `metadata.slide_n` matches a slide that has at least one segment, choosing that slide's first segment by `start_ms`, then `seq` ([app/services/poll_autoplace.py:60](../../app/services/poll_autoplace.py#L60)). It emits a `polls_autoplaced` WebSocket event with the count ([app/services/poll_autoplace.py:112](../../app/services/poll_autoplace.py#L112)).

### Inline chat edit (placed only)
- The **Edit** button on a placed chat row opens a textarea. Save emits `editChat`; `handleChatEdit` posts a `chat_edit` correction against the placed segment via the corrections API ([EditorView.vue:760](../../frontend/src/views/EditorView.vue#L760)). Note: the inline `AnchorBlock` Edit/Save path does **not** persist — it shows a "not persisted" warning toast ([AnchorBlock.vue:45](../../frontend/src/components/editor/AnchorBlock.vue#L45)).

## Business Rules

- **Placement is one column, not a ledger.** Rounds stores placement directly in `polls.anchor_segment` / `chat_messages.anchor_segment` with a `placed` boolean, instead of MIC's corrections-row dance ([app/services/poll_autoplace.py:21](../../app/services/poll_autoplace.py#L21)).
- **Auto-place never overwrites a user placement.** The auto-place UPDATE filters `WHERE anchor_segment IS NULL`, so once a poll is placed (by user or a prior run) it is untouched — re-running is a no-op ([app/services/poll_autoplace.py:77](../../app/services/poll_autoplace.py#L77)).
- **Slide indexing bridge.** `extras2` emits `slide_n` as 1-based; `slides.slide_index` is 0-based; the join bridges with `slide_index + 1 = slide_n` ([app/services/poll_autoplace.py:79](../../app/services/poll_autoplace.py#L79)).
- **Reorder is all-or-nothing.** A reorder PATCH validates every id belongs to the session and renumbers in one statement, so a bad request can't leave a half-renumbered list ([app/api/session_resources.py:548](../../app/api/session_resources.py#L548)).
- **List ordering tie-break.** Lists order by `(order_index IS NULL) ASC, order_index ASC, sent_at_ms/opened_at_ms ASC`, so reordered rows surface in their new positions while un-reordered rows stay chronological ([app/api/session_resources.py:511](../../app/api/session_resources.py#L511), [:716](../../app/api/session_resources.py#L716)).
- **Polls bridged from manifest are inserted as `status = 'closed'`** with `opened_at_ms = 0` and `total_votes = sum(option counts)` ([app/api/gcs_upload.py:320](../../app/api/gcs_upload.py#L320)). The schema default for a directly-created poll is `'open'` ([migrations/008_chat_polls.sql:29](../../migrations/008_chat_polls.sql#L29)), but no endpoint creates polls directly.
- **Chat messages are inserted unplaced** (`placed = FALSE`, no anchor) at ingest ([app/api/gcs_upload.py:435](../../app/api/gcs_upload.py#L435)).
- **Primary audio/video cannot be added through the add-to-session chat/manifest path** ([app/api/add_to_session.py:180](../../app/api/add_to_session.py#L180)).

## Validation Rules

- **Reorder body must be non-empty.** Empty `ids` → 400 `EMPTY_REORDER` ([app/api/session_resources.py:543](../../app/api/session_resources.py#L543), [:749](../../app/api/session_resources.py#L749)).
- **Reorder ids must all belong to the session.** Foreign ids → 400 `UNKNOWN_CHAT_IDS` / `UNKNOWN_POLL_IDS` (returns up to 5 offending ids) ([app/api/session_resources.py:557](../../app/api/session_resources.py#L557), [:762](../../app/api/session_resources.py#L762)).
- **Anchor PATCH validates session ownership.** Setting/clearing an anchor on a message/poll not in the session → 404 ([app/api/session_resources.py:623](../../app/api/session_resources.py#L623), [:821](../../app/api/session_resources.py#L821)).
- **Re-uploading chat replaces existing.** `POST /add/chat` with existing chat and no `?confirm=true` → 409 with current/new previews; with confirm it deletes all chat for the session before inserting ([app/api/add_to_session.py:619](../../app/api/add_to_session.py#L619), [:645](../../app/api/add_to_session.py#L645)).
- **Add-chat insert truncation.** Author capped at 500 chars, body at 5000 ([app/api/add_to_session.py:657](../../app/api/add_to_session.py#L657)).
- **Chat parser auto-detects format** (Zoom simple vs verbose); unrecognized first line → `[]` (never raises) ([app/engines/chat_parser.py:35](../../app/engines/chat_parser.py#L35)).
- **Reorder defensive client guard.** If the incoming id set size differs from the current list (concurrent add), the client aborts the reorder with a toast rather than dropping rows ([EditorView.vue:730](../../frontend/src/views/EditorView.vue#L730)).

## States

### Chat message (`chat_messages`)
- **Unplaced** — `placed = false`, `anchor_segment = NULL` (default at ingest) ([migrations/008_chat_polls.sql:14](../../migrations/008_chat_polls.sql#L14)).
- **Placed** — `placed = true`, `anchor_segment` set ([app/api/session_resources.py:610](../../app/api/session_resources.py#L610)).
- **Reordered** — `order_index` non-NULL ([migrations/052_chat_polls_order_index.sql:22](../../migrations/052_chat_polls_order_index.sql#L22)).

### Poll (`polls`)
- **status** `'open'` (schema default) or `'closed'` (manifest-bridged) ([migrations/008_chat_polls.sql:29](../../migrations/008_chat_polls.sql#L29), [app/api/gcs_upload.py:320](../../app/api/gcs_upload.py#L320)).
- **placed / unplaced** as above; **auto-placed** is a placed state set by `auto_place_polls`.
- **closed_at_ms** nullable.

### List-level
- Empty session → endpoints return `[]`, UI shows a clean "no data yet" state ([app/api/session_resources.py:4](../../app/api/session_resources.py#L4)).

## Dependencies

- **Slides + segments must exist** for poll auto-placement and chat slide dividers — the join needs segments with `slide_id` set ([app/services/poll_autoplace.py:65](../../app/services/poll_autoplace.py#L65), [migrations/001_init.sql:85](../../migrations/001_init.sql#L85)).
- **extras2 manifest** drives poll content via `parse_polls_section` ([app/services/extras2_parser.py:202](../../app/services/extras2_parser.py#L202)) → bridged in `gcs_upload` ([app/api/gcs_upload.py:309](../../app/api/gcs_upload.py#L309)).
- **chat_parser** drives chat content ([app/engines/chat_parser.py:25](../../app/engines/chat_parser.py#L25)).
- **GCS** holds the staged chat/manifest files for the add-to-session path ([app/api/add_to_session.py:92](../../app/api/add_to_session.py#L92)).
- **Corrections API** for placed-chat inline edit ([EditorView.vue:771](../../frontend/src/views/EditorView.vue#L771)).
- **WebSocket bridge** for the `polls_autoplaced` event ([app/services/poll_autoplace.py:111](../../app/services/poll_autoplace.py#L111)).
- **Audit ledger** (`audit_events`) for reorder events ([app/api/session_resources.py:580](../../app/api/session_resources.py#L580)).

## Error Handling

- Anchor/reorder validation failures return structured HTTP errors (400/404) as above.
- Auto-placement is wrapped in try/except at every call site — a failure logs a warning and the session still completes ingest; polls just stay unplaced for manual drag ([app/tasks/ai_process.py:520](../../app/tasks/ai_process.py#L520), [app/tasks/finalize.py:113](../../app/tasks/finalize.py#L113)).
- The `polls_autoplaced` WS emit failure is non-fatal (debug log only) ([app/services/poll_autoplace.py:116](../../app/services/poll_autoplace.py#L116)).
- Client-side placement/reorder API failures revert the optimistic state and toast an error ([EditorView.vue:691](../../frontend/src/views/EditorView.vue#L691), [:736](../../frontend/src/views/EditorView.vue#L736)).
- Chat/extras2 parsers never raise — they return `[]` / an empty manifest on any failure ([app/engines/chat_parser.py:40](../../app/engines/chat_parser.py#L40), [app/services/extras2_parser.py:265](../../app/services/extras2_parser.py#L265)).

## Permissions

Every Chat & Polls endpoint depends only on `CurrentUser` — a valid JWT ([app/api/session_resources.py:18](../../app/api/session_resources.py#L18), [app/auth.py:208](../../app/auth.py#L208)). There is **no role-based authorization** on this module:
- `app.security.roles` (`is_admin`/`require_admin`) is not referenced anywhere in `session_resources.py` or `add_to_session.py`.
- The `User` identity carries only `email` ([app/auth.py:37](../../app/auth.py#L37)); `get_current_user` never reads `auth_users.role` ([app/auth.py:172](../../app/auth.py#L172)).
- The only admin gate in the app is the hardcoded `LEGACY_ADMIN_EMAIL = "johndean@vin.com"` used in ~5 other modules and one client-side route guard on `/admin/help` ([frontend/src/router/index.ts:63](../../frontend/src/router/index.ts#L63)) — **neither applies to Chat & Polls**.

Effective rule: any authenticated user can read, place, re-anchor, detach, reorder, and (for placed chat) edit.

## Reporting Impacts

- **Chat Participants tally** is a read-only aggregate: one row per author with `message_count`, `first_seen_ms`, `last_seen_ms`, ordered by count desc then author asc ([app/api/session_resources.py:657](../../app/api/session_resources.py#L657)).
- **Poll results** (option vote counts, percentages, total) are presentation-only — computed client-side from stored `votes`/`total` ([PollsTab.vue:135](../../frontend/src/components/editor/PollsTab.vue#L135)); there is no aggregate poll-results report endpoint in this module (NOT VERIFIED IN CODE beyond `GET /polls`).

## Audit Requirements

- **Reorders are audited.** Each chat/poll reorder writes an `audit_events` row: `kind = 'chat.reorder'` / `'polls.reorder'`, `actor_email = user.email`, summary `"reordered N …"`, details `{count, first_3}` ([app/api/session_resources.py:580](../../app/api/session_resources.py#L580), [:780](../../app/api/session_resources.py#L780)).
- **Ingest writes audit rows** for chat/manifest upload completion (`kind = 'upload.complete.chat'`/`'upload.complete.manifest'`, `actor_email = NULL`) ([app/api/gcs_upload.py:452](../../app/api/gcs_upload.py#L452)).
- **Anchor set/clear (drag placement) is NOT written to `audit_events`** — only the structured `anchor_segment` column changes ([app/api/session_resources.py:598](../../app/api/session_resources.py#L598), [:795](../../app/api/session_resources.py#L795)). PARTIALLY IMPLEMENTED as audit coverage: placement changes are not in the audit ledger.

## Data Relationships

- `chat_messages.session_id → sessions.id` (ON DELETE CASCADE); `chat_messages.anchor_segment → segments.id` (ON DELETE SET NULL) ([migrations/008_chat_polls.sql:9](../../migrations/008_chat_polls.sql#L9)).
- `polls.session_id → sessions.id` (CASCADE); `polls.anchor_segment → segments.id` (SET NULL) ([migrations/008_chat_polls.sql:25](../../migrations/008_chat_polls.sql#L25)).
- `poll_options.poll_id → polls.id` (CASCADE), unique on `(poll_id, seq)` ([migrations/008_chat_polls.sql:42](../../migrations/008_chat_polls.sql#L42)).
- `polls.metadata` JSONB carries `slide_n`, `q_n`, `source` for auto-placement and the editor's anchor inference ([app/api/gcs_upload.py:329](../../app/api/gcs_upload.py#L329), [app/api/session_resources.py:694](../../app/api/session_resources.py#L694)).
- `segments.slide_id → slides.id` is the link auto-placement walks to find a slide's first segment ([migrations/001_init.sql:85](../../migrations/001_init.sql#L85)).

## Known Constraints

- **No create/delete endpoints for chat or polls.** The only writers are ingest (`gcs_upload`) and the add-to-session chat path; the editor can place/reorder/edit-placed-chat but cannot add or delete a chat message or poll from the UI ([app/api/session_resources.py](../../app/api/session_resources.py) exposes only GET/PATCH for chat & polls).
- **Inline `AnchorBlock` edit does not persist** — it warns "not persisted" ([AnchorBlock.vue:45](../../frontend/src/components/editor/AnchorBlock.vue#L45)). Only the ChatTab placed-row Edit path persists (via a `chat_edit` correction) ([EditorView.vue:771](../../frontend/src/views/EditorView.vue#L771)).
- **Poll options/votes are not editable** through any verified endpoint (the AnchorBlock poll-option inputs are present but unwired) ([AnchorBlock.vue:121](../../frontend/src/components/editor/AnchorBlock.vue#L121)).
- **Auto-placement only works when slides+segments exist.** Polls whose `slide_n` has no aligned segment stay unplaced ([app/services/poll_autoplace.py:37](../../app/services/poll_autoplace.py#L37)).
- **Seed-doc discrepancy:** the seed ([docs/product/polls-chat-resources.md:40](./polls-chat-resources.md)) claims "Chat timestamps are not shown in the card." The current `ChatTab.vue` **does** render `fmtTime(row.msg.t)` ([ChatTab.vue:181](../../frontend/src/components/editor/ChatTab.vue#L181)). Corrected here.
- **No "show only placed/unplaced" filter, no bulk placement, no reactions/emoji** — confirmed absent in the components and seed.
- **`metadata.slide_n` may be `null`** if the manifest poll header lacked a slide number; such polls are skipped by auto-place (`metadata ? 'slide_n'` plus a null value fails the int compare) ([app/api/gcs_upload.py:330](../../app/api/gcs_upload.py#L330)).

## Source Verification
- **Files Used:** app/api/session_resources.py, app/api/add_to_session.py, app/api/gcs_upload.py, app/services/poll_autoplace.py, app/services/extras2_parser.py, app/engines/chat_parser.py, app/auth.py, app/tasks/ai_process.py, app/tasks/finalize.py, migrations/008_chat_polls.sql, migrations/052_chat_polls_order_index.sql, migrations/037_backfill_poll_anchors.sql, migrations/001_init.sql, migrations/004_audit.sql, frontend/src/components/editor/ChatTab.vue, PollsTab.vue, AnchorBlock.vue, frontend/src/views/EditorView.vue, frontend/src/services/api.ts, frontend/src/router/index.ts, docs/product/polls-chat-resources.md (seed)
- **Components Used:** ChatTab.vue, PollsTab.vue, AnchorBlock.vue, EditorView.vue (host)
- **APIs Used:** GET/PATCH `/v1/sessions/{id}/chat`, `/chat/order`, `/chat/{id}`, `/chat-participants`, `/polls`, `/polls/order`, `/polls/{id}/anchor`; POST `/v1/sessions/{id}/add/chat`, `/add/manifest`
- **Database Tables Used:** chat_messages, polls, poll_options, segments, slides, sessions, sources, session_speakers, audit_events
- **Permission Logic Used:** JWT presence only (CurrentUser). No role gate; repo-wide LEGACY_ADMIN_EMAIL gate + client-side `adminOnly` guard do not apply to this module.
- **Confidence Score:** High — every claim traced to a read source file with line evidence; one seed discrepancy corrected.
- **Evidence Links:** [session_resources.py:499](../../app/api/session_resources.py#L499), [:527](../../app/api/session_resources.py#L527), [:704](../../app/api/session_resources.py#L704), [:795](../../app/api/session_resources.py#L795), [poll_autoplace.py:60](../../app/services/poll_autoplace.py#L60), [gcs_upload.py:309](../../app/api/gcs_upload.py#L309), [ChatTab.vue:181](../../frontend/src/components/editor/ChatTab.vue#L181), [EditorView.vue:700](../../frontend/src/views/EditorView.vue#L700)
