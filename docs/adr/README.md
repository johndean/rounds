# Rounds — Architectural Decision Records

> **What is an ADR.** A short, dated document that captures **one** architectural decision: the context, the alternatives considered, the choice made, and its consequences. ADRs are append-only. We never edit a historical ADR to change its decision — when we change our mind, we write a new ADR that supersedes the old one and mark the old one `Status: Superseded by ADR-NNN`.
>
> **Status.** Created 2026-06-05 as Phase 2 of the documentation uplift. Eleven foundational ADRs capture the load-bearing decisions in Rounds. Future architectural decisions land here as `ADR-012`, `ADR-013`, …
>
> **How to cite.** From source: `# See ADR-NNN`. From a business rule: `[ADR-NNN](./adr/ADR-NNN-slug.md)`. Anchors within an ADR are conventional Markdown (`#context`, `#decision`, `#consequences`).

---

## Index

| ADR | Title | Status | Primary code |
|-----|-------|--------|--------------|
| [ADR-001](./ADR-001-authentication.md) | Authentication — JWT + AUTH_USERS env fallback | Accepted | `app/auth.py`, `app/api/auth.py`, `app/services/auth_users.py` |
| [ADR-002](./ADR-002-session-lifecycle.md) | Session lifecycle — soft-delete + status FSM | Accepted | `app/engines/state_machine.py`, `app/api/sessions.py` |
| [ADR-003](./ADR-003-fsm-python-only.md) | State machine — Python-only enforcement (no DB CHECK) | Accepted | `app/engines/state_machine.py` |
| [ADR-004](./ADR-004-export-engine.md) | Export engine — single-source artifact transformer | Accepted | `app/engines/artifact_transformer.py`, `app/api/exports.py` |
| [ADR-005](./ADR-005-corrections-ledger.md) | Transcript synchronization — append-only corrections ledger + pointer undo/redo | Accepted | `app/api/corrections.py`, `migrations/044_corrections*.sql` |
| [ADR-006](./ADR-006-queue-processing.md) | Queue processing — Celery DAG + WS bridge | Accepted | `app/tasks/`, `app/engines/ws_bridge.py`, `app/api/queue.py` |
| [ADR-007](./ADR-007-locked-weights.md) | Locked scoring weights — fusion + alignment + IIL | Accepted | `app/config.py`, `tests/test_health.py::test_locked_weights_match_audit` |
| [ADR-008](./ADR-008-websocket-architecture.md) | WebSocket architecture — session-scoped pub/sub via Redis | Accepted | `app/engines/ws_bridge.py`, `app/main.py` |
| [ADR-009](./ADR-009-editor-architecture.md) | Editor architecture — React SSOT + Vue port discipline | Accepted | `docs/port-source/`, `frontend/src/views/EditorView.vue` |
| [ADR-010](./ADR-010-hash-routed-spa.md) | Hash-routed SPA | Accepted | `frontend/src/router/`, `frontend/index.html` |
| [ADR-011](./ADR-011-migrations-ledger.md) | Append-only schema_migrations ledger (post-bootstrap) | Accepted | `migrations/000_*.sql`, `app/db/migrations.py` |

---

## Template for new ADRs

Create `docs/adr/ADR-NNN-short-slug.md` with this structure:

```markdown
# ADR-NNN — <title>

- **Status:** Accepted | Superseded by ADR-MMM | Deprecated
- **Date:** YYYY-MM-DD
- **Deciders:** <emails>
- **Related:** ADR-XXX, BR-YYY

## Context
What problem prompted this decision? What constraints (technical, regulatory, time, MIC-port)?

## Decision
The decision in one paragraph. Use direct voice — "We use X" not "It was decided to use X."

## Consequences
- **Positive:** …
- **Negative:** …
- **Risks:** …

## Code locations
Where the decision is materialized — `<file>:<line>` references.

## Alternatives considered
1. **<alternative>** — rejected because <reason>.
2. **<alternative>** — rejected because <reason>.
```

## When to write a new ADR

- A choice between two or more credible technical approaches is being made.
- The choice will be expensive to reverse later.
- A future maintainer reading the resulting code would not be able to recover the rationale from the diff alone.
- A locked invariant is being established (e.g. "weight X must never drift without an audit pass").

## When NOT to write an ADR

- Implementation detail that any competent engineer would make the same way.
- Style decisions (covered by linters, formatters, CLAUDE.md conventions).
- Anything that is just "we follow the framework's default."
