# Chat & Polls — Technical Spec

## Architecture

Chat & Polls is a read-mostly sub-resource feature of the session editor. Data originates at ingest, is parsed by pure-Python parsers, persisted to three tables, served by raw-SQL FastAPI endpoints, and consumed by three Vue components hosted in `EditorView.vue` (plus a Session Detail tally widget).

```
                 ┌─────────────────────────── ingest / add-to-session ────────────────────────────┐
chat .txt  ──▶ chat_parser.parse_chat_file ──▶ INSERT chat_messages (placed=FALSE)
extras2.txt ─▶ extras2_parser.parse_polls_section ─▶ INSERT polls + poll_options (status='closed')
slides+segments aligned ──▶ auto_place_polls(engine, sid) ──▶ UPDATE polls SET anchor_segment, placed
                 └────────────────────────────────────────────────────────────────────────────────┘
                                              │
                       chat_messages / polls / poll_options (Postgres)
                                              │
        session_resources.py  GET /chat /polls /chat-participants · PATCH /chat/{id} /polls/{id}/anchor /chat/order /polls/order
                                              │
                       api.ts  placements.* · sessions.chatParticipants
                                              │
        ChatTab.vue · PollsTab.vue · AnchorBlock.vue  (hosted by EditorView.vue)
```

- **Backend module:** [app/api/session_resources.py](../../app/api/session_resources.py) — router prefix `/v1/sessions/{session_id}`, tag `sessions`.
- **Write paths:** [app/api/gcs_upload.py](../../app/api/gcs_upload.py) (ingest) and [app/api/add_to_session.py](../../app/api/add_to_session.py) (operator add).
- **Auto-placement service:** [app/services/poll_autoplace.py](../../app/services/poll_autoplace.py).
- **Parsers:** [app/engines/chat_parser.py](../../app/engines/chat_parser.py), [app/services/extras2_parser.py](../../app/services/extras2_parser.py).

## Frontend Components

### `ChatTab.vue` ([frontend/src/components/editor/ChatTab.vue](../../frontend/src/components/editor/ChatTab.vue))
- **Props:** `chat: ChatMessage[]`, `slides: Slide[]`, `segmentsById: Map`, `placements: Record<string, string|null>`.
- **Emits:** `unplace(id)`, `placeAtActive(id)`, `reorder(ids[])`, `editChat(id, newText)`.
- Computes a `grouped` row list interleaving slide dividers with message rows ([ChatTab.vue:64](../../frontend/src/components/editor/ChatTab.vue#L64)).
- Two drag mechanisms: whole-row placement (MIME `application/vnd.mic.anchor`) and grip-handle reorder (MIME `application/vnd.rounds.reorder-chat`) ([ChatTab.vue:21](../../frontend/src/components/editor/ChatTab.vue#L21), [:89](../../frontend/src/components/editor/ChatTab.vue#L89)).
- Inline edit state (`editingId`, `editDraft`) — only one row editable at a time ([ChatTab.vue:41](../../frontend/src/components/editor/ChatTab.vue#L41)).

### `PollsTab.vue` ([frontend/src/components/editor/PollsTab.vue](../../frontend/src/components/editor/PollsTab.vue))
- **Props:** `polls: Poll[]`, `segmentsById`, `slides`, `placements`. **Emits:** `unplace`, `placeAtActive`, `reorder`.
- Same dual-drag pattern; reorder MIME `application/vnd.rounds.reorder-poll` ([PollsTab.vue:15](../../frontend/src/components/editor/PollsTab.vue#L15)).
- `maxVotes(p)` + `is-winner` class highlight the top option; bar width = `votes/total` ([PollsTab.vue:40](../../frontend/src/components/editor/PollsTab.vue#L40), [:135](../../frontend/src/components/editor/PollsTab.vue#L135)).

### `AnchorBlock.vue` ([frontend/src/components/editor/AnchorBlock.vue](../../frontend/src/components/editor/AnchorBlock.vue))
- Renders a placed chat/poll inline in the transcript as `segment--anchor`. **Props:** `item`, `kind`, `slide`. **Emits:** `remove(id)`.
- Re-anchor-by-drag sets the same placement MIME ([AnchorBlock.vue:63](../../frontend/src/components/editor/AnchorBlock.vue#L63)).
- `save()` is a no-op persistence-wise — it warns "not persisted" ([AnchorBlock.vue:45](../../frontend/src/components/editor/AnchorBlock.vue#L45)).

### Host: `EditorView.vue`
- Owns the `placements` ref, `anchorsBySegment` computed map, and all handler functions ([EditorView.vue:664](../../frontend/src/views/EditorView.vue#L664), [:668](../../frontend/src/views/EditorView.vue#L668)).
- Mounts `ChatTab`/`PollsTab` and wires `@reorder`, `@unplace`, `@placeAtActive` ([EditorView.vue:1481](../../frontend/src/views/EditorView.vue#L1481)).

## Backend Services

- **`auto_place_polls(engine_or_conn, session_id) -> int`** ([app/services/poll_autoplace.py:84](../../app/services/poll_autoplace.py#L84)) — single-statement CTE+UPDATE. Accepts an `Engine` (opens its own txn) or a `Connection` (joins the caller's txn) so ingest tasks can fold it into their `engine.begin()` block. Returns count placed; emits `polls_autoplaced` WS event when >0.
- **`parse_chat_file(content, start_time_override) -> list[dict]`** ([app/engines/chat_parser.py:25](../../app/engines/chat_parser.py#L25)) — auto-detects Zoom Format 1 (`HH:MM:SS\tSpeaker:\tMessage`) vs Format 2 (`YYYY-MM-DD HH:MM:SS From X to Y:`). Returns dicts with `timestamp, speaker, recipient, message, is_private, is_reply, reply_context`. Format 2 computes ms offset from the "to Everyone" start time.
- **`parse_polls_section(text) -> list[dict]`** ([app/services/extras2_parser.py:202](../../app/services/extras2_parser.py#L202)) — regex headers `Slide N - Poll Question #M`; options `count (pct%) label`. Returns `{idx, slide_n, q_n, question, options[], status:'extracted'}`.
- **Poll bridge** ([app/api/gcs_upload.py:309](../../app/api/gcs_upload.py#L309)) — for each parsed poll, INSERT `polls` (`status='closed'`, `opened_at_ms=0`, `total_votes=sum(counts)`, `metadata={slide_n,q_n,source:'extras2'}`) + `poll_options` (`ON CONFLICT (poll_id, seq) DO NOTHING`).
- **Chat insert** ([app/api/gcs_upload.py:428](../../app/api/gcs_upload.py#L428), [app/api/add_to_session.py:649](../../app/api/add_to_session.py#L649)) — INSERT `chat_messages` (`placed=FALSE`, `sent_at_ms = round(timestamp*1000)`).

## APIs

All under prefix `/v1/sessions/{session_id}`; all require `CurrentUser`.

| Method | Path | Handler | Notes |
|---|---|---|---|
| GET | `/chat` | `list_chat` | Orders `(order_index IS NULL) ASC, order_index ASC, sent_at_ms ASC` ([session_resources.py:499](../../app/api/session_resources.py#L499)) |
| PATCH | `/chat/order` | `reorder_chat` | Body `{ids: UUID[]}`; sets `order_index=position`; audits `chat.reorder` ([:527](../../app/api/session_resources.py#L527)) |
| PATCH | `/chat/{message_id}` | `patch_chat_anchor` | Body `{anchor_segment: UUID|null}`; sets `placed=(anchor IS NOT NULL)`; idempotent; 404 if not in session ([:598](../../app/api/session_resources.py#L598)) |
| GET | `/chat-participants` | `list_chat_participants` | Aggregate by author; order count desc, author asc ([:639](../../app/api/session_resources.py#L639)) |
| GET | `/polls` | `list_polls` | Includes `metadata` JSONB + nested `options[]`; same order tie-break ([:704](../../app/api/session_resources.py#L704)) |
| PATCH | `/polls/order` | `reorder_polls` | Mirror of `/chat/order`; audits `polls.reorder` ([:739](../../app/api/session_resources.py#L739)) |
| PATCH | `/polls/{poll_id}/anchor` | `patch_poll_anchor` | Body `{anchor_segment}`; idempotent; 404 if not in session ([:795](../../app/api/session_resources.py#L795)) |
| POST | `/add/chat` | `add_chat` (in add_to_session.py) | Multipart `chat_file` OR `{gcs_uri}`; `?confirm=true` to replace; `?start_time=` override ([add_to_session.py:597](../../app/api/add_to_session.py#L597)) |
| POST | `/add/manifest` | `add_manifest` | Parses extras2; bridges polls in gcs_upload (not here) — manifest add updates session fields + speakers + resources ([add_to_session.py:711](../../app/api/add_to_session.py#L711)) |

**Frontend client** ([frontend/src/services/api.ts:369](../../frontend/src/services/api.ts#L369)):
- `placements.chatAnchor(sessionId, chatId, anchorSegment)` → `PATCH /chat/{id}`
- `placements.pollAnchor(sessionId, pollId, anchorSegment)` → `PATCH /polls/{id}/anchor`
- `placements.chatReorder(sessionId, ids)` → `PATCH /chat/order`
- `placements.pollsReorder(sessionId, ids)` → `PATCH /polls/order`
- `sessions.chatParticipants(id)` → `GET /chat-participants` ([api.ts:218](../../frontend/src/services/api.ts#L218))

## Data Models

### `chat_messages` ([migrations/008_chat_polls.sql:7](../../migrations/008_chat_polls.sql#L7))
`id UUID PK`, `session_id UUID NOT NULL → sessions(id) CASCADE`, `author TEXT`, `body TEXT`, `sent_at_ms INTEGER` (ms offset from session start), `anchor_segment UUID → segments(id) SET NULL`, `placed BOOLEAN DEFAULT false`, `metadata JSONB DEFAULT '{}'`, `created_at TIMESTAMPTZ`. Plus `order_index INTEGER NULL` ([migrations/052_chat_polls_order_index.sql:22](../../migrations/052_chat_polls_order_index.sql#L22)).
Indexes: `chat_messages_session_idx`, `chat_messages_anchor_idx`, partial `chat_messages_order_idx (session_id, order_index) WHERE order_index IS NOT NULL`.

### `polls` ([migrations/008_chat_polls.sql:23](../../migrations/008_chat_polls.sql#L23))
`id`, `session_id → sessions CASCADE`, `question TEXT`, `opened_at_ms INTEGER`, `closed_at_ms INTEGER NULL`, `status TEXT DEFAULT 'open'` (open|closed), `total_votes INTEGER DEFAULT 0`, `anchor_segment → segments SET NULL`, `placed BOOLEAN DEFAULT false`, `metadata JSONB DEFAULT '{}'`, `created_at`. Plus `order_index INTEGER NULL`. Index `polls_session_idx`, partial `polls_order_idx`.

### `poll_options` ([migrations/008_chat_polls.sql:40](../../migrations/008_chat_polls.sql#L40))
`id`, `poll_id → polls CASCADE`, `label TEXT`, `seq INTEGER`, `votes INTEGER DEFAULT 0`, `UNIQUE (poll_id, seq)`. Index `poll_options_poll_idx`.

### API response shapes ([app/api/session_resources.py:489](../../app/api/session_resources.py#L489))
- `ChatMessageOut`: `id, author, body, sent_at_ms, anchor_segment?, placed`.
- `PollOut`: `id, question, status, opened_at_ms, closed_at_ms?, total_votes, anchor_segment?, placed, metadata?, options[]`.
- `PollOptionOut`: `id, label, seq, votes`.
- `ChatParticipantOut`: `speaker, message_count, first_seen_ms, last_seen_ms`.

### `polls.metadata` keys
`slide_n` (1-based slide), `q_n`, `source:'extras2'` ([app/api/gcs_upload.py:329](../../app/api/gcs_upload.py#L329)). Used by auto-place and the editor's client `_inferAnchor()` fallback ([app/api/session_resources.py:694](../../app/api/session_resources.py#L694)).

## Events

- **`polls_autoplaced`** — WebSocket event `{type:'polls_autoplaced', count}` published synchronously by `auto_place_polls` when ≥1 poll is placed ([app/services/poll_autoplace.py:112](../../app/services/poll_autoplace.py#L112)).
- **`chat.reorder` / `polls.reorder`** — `audit_events` rows on every reorder PATCH ([app/api/session_resources.py:580](../../app/api/session_resources.py#L580), [:780](../../app/api/session_resources.py#L780)).
- **`upload.complete.chat` / `upload.complete.manifest`** — `audit_events` rows at ingest ([app/api/gcs_upload.py:452](../../app/api/gcs_upload.py#L452), [:386](../../app/api/gcs_upload.py#L386)).
- Anchor set/clear (drag placement) emits **no** event.

## State Management

- `EditorView.vue` holds `placements: ref<Record<string, string|null>>` ([EditorView.vue:664](../../frontend/src/views/EditorView.vue#L664)), seeded from chat/poll initial anchors ([EditorView.vue:408](../../frontend/src/views/EditorView.vue#L408)).
- `anchorsBySegment` computed groups placed chat/poll items by `placements[id]`, sorted by `t` ([EditorView.vue:668](../../frontend/src/views/EditorView.vue#L668)).
- **Optimistic mutation pattern:** placement/reorder mutate local state first, then call the API; on failure they revert and toast ([EditorView.vue:701](../../frontend/src/views/EditorView.vue#L701), [:735](../../frontend/src/views/EditorView.vue#L735)).
- Reorder operates on the flat list id sequence, not the visually grouped rows ([ChatTab.vue:95](../../frontend/src/components/editor/ChatTab.vue#L95)).

## Validation

- Reorder: non-empty `ids` (`EMPTY_REORDER`); all ids must belong to session (`UNKNOWN_CHAT_IDS`/`UNKNOWN_POLL_IDS`, ≤5 returned) ([app/api/session_resources.py:543](../../app/api/session_resources.py#L543), [:557](../../app/api/session_resources.py#L557)).
- Anchor PATCH: session ownership enforced via `WHERE id=:id AND session_id=:sid`; no match → 404 ([app/api/session_resources.py:623](../../app/api/session_resources.py#L623)).
- Add-chat: existing-chat conflict → 409 unless `?confirm=true`; replace deletes all session chat first ([app/api/add_to_session.py:619](../../app/api/add_to_session.py#L619)).
- Add-chat insert: author ≤500, body ≤5000 chars ([app/api/add_to_session.py:657](../../app/api/add_to_session.py#L657)).
- Add-to-session rejects primary A/V MIME on chat/manifest path ([app/api/add_to_session.py:180](../../app/api/add_to_session.py#L180)).
- Client reorder size-mismatch guard ([EditorView.vue:730](../../frontend/src/views/EditorView.vue#L730)).
- Pydantic enforces request bodies: `ReorderRequest.ids: list[UUID]`, `AnchorPatch.anchor_segment: Optional[UUID]` ([app/api/session_resources.py:520](../../app/api/session_resources.py#L520), [:594](../../app/api/session_resources.py#L594)).

## Security

- All endpoints take `CurrentUser` (JWT) ([app/api/session_resources.py:18](../../app/api/session_resources.py#L18), [app/auth.py:172](../../app/auth.py#L172)). Token decode failure → 401.
- Add-to-session signed PUT URLs are scoped to the session's `…/staging/phase6/` prefix (R7 invariant); leaked URL has 1h TTL + session-scoped path ([app/api/add_to_session.py:17](../../app/api/add_to_session.py#L17), [:97](../../app/api/add_to_session.py#L97)).
- All SQL uses bound parameters with explicit `CAST(:x AS uuid/jsonb)` — no string interpolation of user data (the reorder UPDATE column list is positional, fixed).
- Reorder audit captures `actor_email` for accountability ([app/api/session_resources.py:585](../../app/api/session_resources.py#L585)).

## Permissions

No role-based access control. `User` carries only `email` ([app/auth.py:37](../../app/auth.py#L37)); `get_current_user` does not read `auth_users.role` ([app/auth.py:172](../../app/auth.py#L172)). `app.security.roles.is_admin/require_admin` is not imported by either `session_resources.py` or `add_to_session.py`. The repo-wide `LEGACY_ADMIN_EMAIL = "johndean@vin.com"` gate and the client-side `adminOnly` route guard (only on `/admin/help`, [frontend/src/router/index.ts:63](../../frontend/src/router/index.ts#L63)) do not touch this module. Effective: any authenticated user can perform every Chat & Polls action.

## Integrations

- **Google Cloud Storage** — staged chat/manifest files for `add/chat` + `add/manifest` ([app/api/add_to_session.py:102](../../app/api/add_to_session.py#L102)).
- **WebSocket bridge** (`app.engines.ws_bridge.publish_ws_event_sync`) — `polls_autoplaced` ([app/services/poll_autoplace.py:111](../../app/services/poll_autoplace.py#L111)).
- **Corrections API** — placed-chat inline edit posts a `chat_edit` correction ([EditorView.vue:771](../../frontend/src/views/EditorView.vue#L771)).
- **Celery ingest tasks** — `ai_process` (direct) and `finalize` (enhanced) call `auto_place_polls` ([app/tasks/ai_process.py:522](../../app/tasks/ai_process.py#L522), [app/tasks/finalize.py:116](../../app/tasks/finalize.py#L116)).
- **Diagnostics** — `POST /v1/diag/autoplace-polls/{id}` re-runs `auto_place_polls` for a session ([app/api/diagnostics.py:265](../../app/api/diagnostics.py#L265)).

## Background Jobs

- **`auto_place_polls`** runs once at ingest completion inside the ingest task transaction; wrapped in try/except so a failure logs a warning and the session still completes ([app/tasks/ai_process.py:520](../../app/tasks/ai_process.py#L520), [app/tasks/finalize.py:113](../../app/tasks/finalize.py#L113)).
- **Migration 037** (`037_backfill_poll_anchors.sql`) runs the same algorithm across every session at once — idempotent backfill for sessions ingested before auto-place landed ([migrations/037_backfill_poll_anchors.sql:19](../../migrations/037_backfill_poll_anchors.sql#L19)).
- No recurring Celery Beat job specific to Chat & Polls (NOT VERIFIED IN CODE — no such schedule found).

## Error Handling

- Parsers never raise: `parse_chat_file` returns `[]` on unrecognized format ([app/engines/chat_parser.py:40](../../app/engines/chat_parser.py#L40)); `parse_extras2`/`parse_polls_section` return empty on any failure ([app/services/extras2_parser.py:265](../../app/services/extras2_parser.py#L265), [:203](../../app/services/extras2_parser.py#L203)).
- `auto_place_polls` call sites swallow exceptions (non-fatal); WS emit failure is debug-logged ([app/services/poll_autoplace.py:116](../../app/services/poll_autoplace.py#L116)).
- API: 400 (validation), 404 (ownership), 409 (add-chat conflict). Reorder is all-or-nothing in one statement.
- Client: optimistic revert + toast on any placement/reorder API rejection ([EditorView.vue:691](../../frontend/src/views/EditorView.vue#L691), [:737](../../frontend/src/views/EditorView.vue#L737)).
- Empty session is a first-class clean state — GET endpoints return `[]` ([app/api/session_resources.py:4](../../app/api/session_resources.py#L4)).

## Performance Considerations

- **Reorder is a single SQL statement** using `jsonb_to_recordset` instead of N per-row UPDATEs — avoids ~100 round-trips on large threads (operator-interactive hot path) ([app/api/session_resources.py:563](../../app/api/session_resources.py#L563)).
- **Auto-place is one statement** — a `DISTINCT ON (slide_index)` CTE over session-scoped segments; sub-10ms for ~200-segment sessions ([app/services/poll_autoplace.py:44](../../app/services/poll_autoplace.py#L44)).
- **Partial indexes** on `(session_id, order_index) WHERE order_index IS NOT NULL` keep the COALESCE-style ORDER BY cheap; built `CONCURRENTLY` to avoid `ACCESS EXCLUSIVE` lock on live tables ([migrations/052_chat_polls_order_index.sql:50](../../migrations/052_chat_polls_order_index.sql#L50)).
- **`GET /polls` is N+1** by design — one options query per poll ([app/api/session_resources.py:723](../../app/api/session_resources.py#L723)). Acceptable for the small poll counts per session; flagged as a known shape.
- Chat list reads ride `chat_messages_session_idx`.

## Source Verification
- **Files Used:** app/api/session_resources.py, app/api/add_to_session.py, app/api/gcs_upload.py, app/services/poll_autoplace.py, app/services/extras2_parser.py, app/engines/chat_parser.py, app/auth.py, app/api/diagnostics.py, app/tasks/ai_process.py, app/tasks/finalize.py, migrations/008_chat_polls.sql, migrations/052_chat_polls_order_index.sql, migrations/037_backfill_poll_anchors.sql, migrations/001_init.sql, migrations/004_audit.sql, frontend/src/components/editor/ChatTab.vue, PollsTab.vue, AnchorBlock.vue, frontend/src/views/EditorView.vue, frontend/src/services/api.ts, frontend/src/router/index.ts
- **Components Used:** ChatTab.vue, PollsTab.vue, AnchorBlock.vue, EditorView.vue
- **APIs Used:** GET/PATCH `/v1/sessions/{id}/chat`, `/chat/order`, `/chat/{id}`, `/chat-participants`, `/polls`, `/polls/order`, `/polls/{id}/anchor`; POST `/add/chat`, `/add/manifest`; `/v1/diag/autoplace-polls/{id}`
- **Database Tables Used:** chat_messages, polls, poll_options, segments, slides, sessions, audit_events
- **Permission Logic Used:** JWT presence only (CurrentUser). No role gate; LEGACY_ADMIN_EMAIL / client adminOnly guard do not apply.
- **Confidence Score:** High — every endpoint, column, and event traced to read source.
- **Evidence Links:** [session_resources.py:527](../../app/api/session_resources.py#L527), [:795](../../app/api/session_resources.py#L795), [poll_autoplace.py:84](../../app/services/poll_autoplace.py#L84), [gcs_upload.py:309](../../app/api/gcs_upload.py#L309), [migrations/052_chat_polls_order_index.sql:50](../../migrations/052_chat_polls_order_index.sql#L50), [EditorView.vue:724](../../frontend/src/views/EditorView.vue#L724)
