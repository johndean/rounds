# Polls, Chat & Resources — Technical Spec

Developer-facing twin of [../product/polls-chat-resources.md](../product/polls-chat-resources.md).

> References verified against `HEAD` on 2026-06-08.

## Overview

Chat and polls are parsed from the uploaded manifest (extras2) at ingest, stored
as their own tables, and anchored to segments. Polls get a first-pass automatic
placement; both chat and polls support manual re-anchor and reorder via an
`order_index`.

## API routes

| Method | Path | File:Line |
|---|---|---|
| GET | `/v1/sessions/{id}/polls` | [app/api/session_resources.py](../../app/api/session_resources.py) |
| PATCH | `/v1/sessions/{id}/polls/{poll_id}/anchor` | [app/api/session_resources.py](../../app/api/session_resources.py) |
| PATCH | `/v1/sessions/{id}/polls/order` | [app/api/session_resources.py](../../app/api/session_resources.py) |
| GET | `/v1/sessions/{id}/chat` | [app/api/session_resources.py](../../app/api/session_resources.py) |
| PATCH | `/v1/sessions/{id}/chat/{message_id}` | [app/api/session_resources.py](../../app/api/session_resources.py) |
| PATCH | `/v1/sessions/{id}/chat/order` | [app/api/session_resources.py](../../app/api/session_resources.py) |
| GET | `/v1/sessions/{id}/chat-participants` | [app/api/session_resources.py](../../app/api/session_resources.py) |
| POST | `/v1/sessions/{id}/add/chat` | [app/api/add_to_session.py](../../app/api/add_to_session.py) |
| POST | `/v1/diag/autoplace-polls/{session_id}` | [app/api/diagnostics.py](../../app/api/diagnostics.py) |

## Services & engines

| Concern | Module |
|---|---|
| Poll auto-placement (semantic nearest-segment) | [app/services/poll_autoplace.py](../../app/services/poll_autoplace.py) |
| Manifest / extras2 parsing | [app/services/extras2_parser.py](../../app/services/extras2_parser.py) |
| Chat log parsing | [app/engines/chat_parser.py](../../app/engines/chat_parser.py) |

## Data model

| Table | Migration |
|---|---|
| `polls`, `chat_messages` | [migrations/008_chat_polls.sql](../../migrations/008_chat_polls.sql) |
| `order_index` (drag-to-reorder) | [migrations/052_chat_polls_order_index.sql](../../migrations/052_chat_polls_order_index.sql) |
| poll anchor backfill | [migrations/037_backfill_poll_anchors.sql](../../migrations/037_backfill_poll_anchors.sql) |
| manifest source | [migrations/011_manifest.sql](../../migrations/011_manifest.sql) |

## Key constants & invariants

- **Anchor scoping:** `anchor_segment_id` must reference a segment belonging to
  the same session (FK-enforced).
- **Read-only content:** chat/poll text is immutable post-ingest; only placement
  (`anchor_segment_id`) and ordering (`order_index`) are mutable.
- **Participants** are derived (`DISTINCT author` over `chat_messages`), not a
  separate table.

## Frontend

Chat and Polls tabs live in the Editor right rail; drag-to-anchor renders inline
blocks in the transcript. Layout SSOT: `docs/port-source/editor.jsx`.
