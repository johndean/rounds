# Speaker Management — Technical Spec

Developer-facing twin of [../product/speakers.md](../product/speakers.md).

> References verified against `HEAD` on 2026-06-08.

## Overview

Speakers are a per-session directory; `segments.speaker_id` is a nullable FK into
it. The transcription pass attributes segments to speakers; the Editor exposes
rename / merge / reassign / add. A null `speaker_id` renders as `(Unknown)` on
export (BR-017).

## API routes

| Method | Path | File:Line |
|---|---|---|
| GET | `/v1/sessions/{id}/speakers` | [app/api/session_resources.py](../../app/api/session_resources.py) |
| POST | `/v1/sessions/{id}/speakers` | [app/api/session_resources.py](../../app/api/session_resources.py) |
| PATCH | `/v1/sessions/{id}/speakers/{speaker_id}` | [app/api/session_resources.py](../../app/api/session_resources.py) |
| DELETE | `/v1/sessions/{id}/speakers/{speaker_id}` | [app/api/session_resources.py](../../app/api/session_resources.py) |
| POST | `/v1/segments/{id}/reassign` (speaker reassign) | [app/api/segments.py:224](../../app/api/segments.py#L224) |

A speaker reassignment is also persisted as a `speaker_edit` correction in the
ledger (see [editor.spec.md](editor.spec.md)).

## Services & engines

| Concern | Module |
|---|---|
| Speaker attribution during transcription | [app/tasks/transcribe.py](../../app/tasks/transcribe.py), [app/tasks/ai_process.py](../../app/tasks/ai_process.py) |
| Segment chunking / boundaries | [app/engines/segmenter.py](../../app/engines/segmenter.py) |
| Export fallback `(Unknown)` | [app/engines/artifact_transformer.py](../../app/engines/artifact_transformer.py) |

## Data model

| Table | Migration |
|---|---|
| `speakers` (name, role, avatar_color) | [migrations/001_init.sql](../../migrations/001_init.sql) |
| `segments.speaker_id` (nullable FK) | [migrations/001_init.sql](../../migrations/001_init.sql) |

On `DELETE` of a speaker, referencing `segments.speaker_id` is set null (→ exports
as `(Unknown)`).

## Key constants & invariants

- **Unknown fallback (BR-017):** `(Unknown)` is the canonical unresolved-speaker
  string across every export format.
- **Rename propagation:** a rename mutates the single `speakers` row, so all
  referencing segments reflect it without per-segment writes.

## Frontend

Speaker panel is in the Editor right rail and on the Session Detail page; inline
`[Speaker]` action on each segment. Layout SSOT: `docs/port-source/editor.jsx`.
