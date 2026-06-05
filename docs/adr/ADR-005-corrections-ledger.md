# ADR-005 — Transcript synchronization: append-only corrections ledger + pointer undo/redo

- **Status:** Accepted
- **Date:** 2026-05-25 (corrections ledger rolled out), refined 2026-06-05
- **Deciders:** johndean@vin.com
- **Related:** [BR-006](../BUSINESS_RULES.md#br-006), [BR-018](../BUSINESS_RULES.md#br-018), [ADR-002](./ADR-002-session-lifecycle.md), [ADR-009](./ADR-009-editor-architecture.md)

## Context

A reviewer working a transcript in the editor performs hundreds of small edits per session: text edits, find-replace, speaker re-assigns, discrepancy resolutions, chat/poll re-anchors, "mark OK" closes. The requirements:

1. **Undo/redo across edits** including across page reloads (the reviewer who comes back tomorrow can still undo yesterday's last edit).
2. **Audit trail.** Every edit is attributable to a user, time-stamped, and inspectable later.
3. **Multi-tab safety.** Two browser tabs editing the same session must converge to a consistent state.
4. **Cheap export refresh.** When the reviewer hits "export," the engine reads the current corrected text — not the raw transcribed text — without a cascade of dependent recomputations.

A naive design (mutate the `segments` table in place; throw away history) fails all four.

## Decision

**Corrections are an append-only ledger; the rendered transcript is the result of replaying the ledger over the raw transcribed segments. Undo/redo is a pointer move, not a row deletion.**

- The `corrections` table records every edit with `(session_id, segment_id, correction_type, payload_json, sequence_number, created_at, created_by, supersedes_id)`.
- `sequence_number` is monotone-increasing per session, assigned at insert.
- `corrections.supersedes_id` links a new correction to the prior correction it replaces — used for undo / find-replace chains.
- A per-session "current pointer" (the max applied `sequence_number`) is implicit in `corrections.applied`. Undo decrements; redo increments. No row is deleted.
- When the editor (or the export engine) needs the current text, it reads raw `segments.text` then replays applied corrections in `sequence_number` order, producing `effective_text`.
- Some correction types ([BR-018](../BUSINESS_RULES.md#br-018) — `text_edit` and `mark_ok`) additionally close any discrepancy on the affected segment.
- Find-replace is a single correction with a list of `(segment_id, old, new)` payloads — undo restores all at once.

## Consequences

- **Positive.**
  - Undo/redo survives reloads, restarts, and Railway deploys.
  - Every edit is attributable in `audit_events` (the corrections table is itself the audit log).
  - Multi-tab edits don't lose work — both write to the ledger; the conflict resolution is "later sequence number wins."
  - Export caching can fingerprint on `MAX(sequence_number)` per session — the captions ETag does exactly this ([ADR-004](./ADR-004-export-engine.md)).
- **Negative.**
  - Read path is more expensive than mutating segments in place: every editor render replays the ledger. We mitigate by limiting the visible-segment window to ~50 segments at a time.
  - Storage grows proportional to edit count. No retention sweeper.
  - "Apply correction" + "close discrepancy" must remain inside one transaction or partial application leaves the discrepancy state inconsistent — see `app/api/corrections.py::apply_correction`.
- **Risks.**
  - A bug in the replay logic that misorders corrections produces text the user never authored. Mitigated by `sequence_number` being a single source of truth and an integer.
  - A migration that deletes a correction row breaks undo/redo. Migrations to `corrections` must be append-only.

## Code locations

- `app/api/corrections.py` — apply, undo, redo, find-replace, priority scoring ([BR-006](../BUSINESS_RULES.md#br-006))
- `app/api/corrections.py:49` — `CLOSES_DISCREPANCY_TYPES = frozenset({"text_edit", "mark_ok"})` ([BR-018](../BUSINESS_RULES.md#br-018))
- `migrations/044_corrections*.sql` — ledger schema (append-only)
- `frontend/src/views/EditorView.vue` — keyboard shortcuts (Cmd+Z / Cmd+Y / Cmd+F) wire to the ledger
- `app/api/exports.py:117` — captions ETag includes `MAX(corrections.sequence_number)`

## Alternatives considered

1. **Mutate `segments.text` in place; keep a `segment_history` audit table** — rejected because undo / redo would require copying back from history (slow, error-prone) and multi-tab conflict resolution would be ad-hoc.
2. **CRDT (Yjs, Automerge)** — rejected as over-engineered. Single-reviewer sessions are the norm; the rare multi-tab case is well-served by "later sequence number wins."
3. **Per-edit branch / merge model (git-style)** — rejected. Editors don't think in branches; they think in undo/redo.
4. **Materialize a `corrected_segments` table that the editor + exporter both read directly** — rejected because the replay step is cheap enough at session scale and the table would have to be kept in lock-step with the ledger.

## When this ADR should be revisited

- If session size grows such that ledger-replay latency becomes user-visible — then `corrected_segments` materialization becomes a leverage move.
- If real-time multi-user collaborative editing becomes a requirement — then a CRDT or OT layer goes on top.
- If a regulatory audit demands provable immutability — then signing or hashing of the ledger becomes a follow-on.
