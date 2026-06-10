# Status Dictionary — rounds.vin

Every status / state surface in the product, consolidated and code-verified.
rounds.vin has **four** distinct state surfaces — they are independent and must
not be conflated:

1. **Session processing status** (the AI pipeline FSM)
2. **SOP workflow stage** (the human review pipeline)
3. **Discrepancy status** (review items)
4. **Improvement status** (suggestion tracker)

Plus two lifecycle flags (soft-delete, edit-lock).

> ⚠️ Common error (see `docs/gap-analysis.md` D1): older docs describe the session
> lifecycle as `uploading → ingesting → processing → ready → published → archived`.
> That is **wrong**. The verified statuses are below.

---

## 1. Session processing status (FSM)

Single source of truth: `ALLOWED_TRANSITIONS` in
[app/engines/state_machine.py:40](../app/engines/state_machine.py#L40). All changes
go through `transition_session` / `transition_session_sync`; illegal moves raise
`ConflictError` → HTTP **409**. Every transition appends to `session_audit.processing_log`
and emits a `processing_update` WebSocket event.

| Status | Meaning | Allowed transitions | Terminal? |
|---|---|---|---|
| `uploading` | Files transferring / awaiting ingest | → `transcribing`, `ready`, `failed` | no |
| `transcribing` | Speech-to-text running | → `normalizing`, `failed` | no |
| `normalizing` | IIL filler/terminology normalization | → `fusing`, `failed` | no |
| `fusing` | Boundary fusion (visual + anchor + semantic) | → `aligning`, `failed` | no |
| `aligning` | Segment → slide alignment | → `ready`, `failed` | no |
| `ready` | Processing done; Editor available; SOP begins | → `complete`, `failed` | no |
| `complete` | Finalized | — | **yes** |
| `failed` | Pipeline error (reachable from every non-terminal status) | — | **yes** |

**Notes:**
- `uploading → ready` is the **AI-mode direct path** (skips intermediate stages) — [state_machine.py:38](../app/engines/state_machine.py#L38).
- `ready → complete` is the SOP final-stage promotion.
- `processing`, `published`, and `archived` are **not** statuses. `ingesting` is a
  **legacy** alias that migration 010 normalized to `uploading` (a dead
  `status === 'ingesting'` branch still exists in frontend routing); the
  `sessions_status_check` CHECK rejects it.
- Valid *values* are enforced by the `sessions_status_check` CHECK
  ([010_state_machine.sql:21-26](../migrations/010_state_machine.sql#L21)); the FSM
  enforces valid *transitions*. Two layers.
- "Archived" in the UI = `sessions.deleted_at` (soft-delete), a flag, not a status.

### State diagram

```
            ┌─────────────► ready ──────► complete
            │                 ▲
 uploading ─┼─► transcribing ─┘ (via normalizing→fusing→aligning)
            │        │
            │        ▼
            │    normalizing ─► fusing ─► aligning ─► ready
            │
            └────────────────────────────────────────────► failed
   (failed is reachable from uploading/transcribing/normalizing/fusing/aligning/ready)
```

---

## 2. SOP workflow stage

Source: `_DEFAULT_SLA_HOURS` in [app/tasks/sop_tasks.py:36](../app/tasks/sop_tasks.py#L36);
state stored in `sop_state.current_stage` (migration 003). Advanced by the stage
owner via `POST /v1/sop/advance`. Auto-initialized at `prep` on session finalize.

| Stage | Default SLA (hours) | Advances to |
|---|---|---|
| `prep` | 8 | `copy_draft` |
| `copy_draft` | 24 | `medical` |
| `medical` | 48 | `copy_final` |
| `copy_final` | 24 | `cms` |
| `cms` | 12 | `captions` |
| `captions` | 12 | `qa` |
| `qa` | 8 | `complete` |
| `complete` | 0 (terminal) | — |

- Each stage has an assignee (`session_stage_assignees`, migration 042), defaulted
  from the session type and overridable per session.
- On SLA breach, the hourly `sop_check_deadlines_task` emails the assignee — once
  per stage per ~23h (**BR-004**) — **only if** `SOP_DEADLINE_EMAIL_ENABLED` (default off).
- There is **no escalation tier** beyond this single reminder email.

---

## 3. Discrepancy status

Source: `discrepancies` table (migrations 002 / 017_full). Surfaced in the Editor's
Discrepancies pane, ranked by priority (**BR-006**, `corrections.py:577`).

| Status | Meaning | Set by |
|---|---|---|
| `review` | Open; needs a human decision | created by `lcs_discrepancies_task` / alignment |
| `resolved` | Closed by an edit | auto-closed on a `text_edit` or `mark_ok` correction (**BR-018**, `corrections.py:49`) |
| `dismissed` | Skipped without editing | reviewer "Dismiss" action |

---

## 4. Improvement status

Source: `improvements` table (migration 005); `app/api/improvements.py`.

`proposed → in_review → approved → completed` — a lightweight tracker, simpler
than the session FSM (no enforced transition guard).

---

## 5. Lifecycle flags (not statuses)

| Flag | Meaning | Source |
|---|---|---|
| `sessions.deleted_at` | Soft-deleted ("Trash"); restorable within 30 days; permanent purge is separate | `app/api/sessions.py` (delete/restore/permanent) |
| Session edit-lock | Redis/DB lock so one operator edits at a time; admin can force-take | `app/api/locks.py`, `session_locks` (migration 057) |

---

## Source Verification
- **Files Used:** app/engines/state_machine.py, app/tasks/sop_tasks.py, app/api/corrections.py, app/api/improvements.py, app/api/sessions.py, app/api/locks.py, migrations/002/003/005/017/042/057
- **Components Used:** none (backend state)
- **APIs Used:** /v1/sop/advance, /v1/sessions/* lifecycle, /v1/discrepancies, /v1/improvements, /v1/sessions/{id}/locks/*
- **Database Tables Used:** sessions, session_audit, sop_state, session_stage_assignees, discrepancies, improvements, session_locks
- **Permission Logic Used:** JWT; admin gate on destructive session ops + SOP checks resolve
- **Confidence Score:** High — FSM and SOP SLAs read from source this session (§1–§2); §3–§4 from prior verified specs.
- **Evidence Links:** [state_machine.py:40](../app/engines/state_machine.py#L40), [sop_tasks.py:36](../app/tasks/sop_tasks.py#L36), [corrections.py:577](../app/api/corrections.py#L577)
