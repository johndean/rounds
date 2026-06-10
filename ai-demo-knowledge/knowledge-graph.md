# AI Knowledge Graph — rounds.vin

Human-readable companion to [`knowledge-graph.json`](knowledge-graph.json) (the
machine-consumable source). Phase 12 of the AI Knowledge Center framework, mapped
to rounds.vin's **actual** domain.

> **Domain note.** rounds.vin is transcript software for VIN (recorded CE sessions
> → transcripts). The originating framework was written for an inspection/EHS
> product. Its entities — Inspection, Asset, Site, Area, Observation, Corrective
> Action, Escalation Engine, Compliance Rule Engine, GPS, Mobile App, CMMS/ERP/GIS
> — have **no implementation here** and produce no nodes. They are listed under
> `not_implemented` in the JSON so a demo AI can answer "do you do inspections?"
> with a confident **no**.

## Entity types (with node counts)

| Type | Count | Examples |
|---|---|---|
| Role | 3 | Authenticated user, Bootstrap admin, Soft-delete carve-out |
| Page | 16 | Dashboard, Sessions, Editor, Upload, SOP, Settings |
| Status (session FSM) | 8 | uploading → transcribing → normalizing → fusing → aligning → ready → complete; failed |
| AssignmentStage (SOP) | 8 | prep, copy_draft, medical, copy_final, cms, captions, qa, complete |
| Permission | 3 | JWT, Admin (email gate), Soft-delete allowed |
| Rule | 12 | BR-001/002/004/006/007/008/009/010/016/017/018, R7 |
| Router | 20 | sessions, corrections, sop, exports, help, diagnostics… |
| Integration | 6 | GCS, Google STT, Gemini, Vertex (off), SMTP, Railway |
| FeatureFlag | 5 | watchdog, deadline-email, ask-AI, split/merge, vertex (all default-off) |
| DomainObject | 19 | session, segment, word, slide, speaker, correction, discrepancy… |

## Core relationship chains (the spine a demo AI should know)

**Lifecycle:**
`Session —has_status→ uploading —transitions_to→ transcribing → normalizing → fusing → aligning → ready → complete` (governed by **BR-007**, `state_machine.py:40`). `failed` is reachable from every stage and is terminal.

**Workflow (SOP):**
`Session —has→ sop_state —current_stage→ prep —advances_to→ copy_draft → medical → copy_final → cms → captions → qa → complete`. Each stage is `assigned_via session_stage_assignees` and `on_sla_breach_notifies SMTP` (gated by `SOP_DEADLINE_EMAIL_ENABLED`, default off).

**Transcript content:**
`Session —has_many→ segment —has_many→ word`; `segment —attributed_to→ speaker`, `—aligned_to→ slide`, `—edited_via→ correction`; `correction —closes→ discrepancy` (**BR-018**); `alignment —produces→ discrepancy` (ranked by **BR-006**).

**Anchors & export:**
`poll/chat_message —anchored_to→ segment`; `Session —exports_to→ artifact` (filler rules **BR-016**).

**Access:**
`Authenticated user —can_access→` most pages/routers (JWT only). `Admin (email gate) —guards→ settings, diagnostics, admin help, destructive session ops`. There is **no role tier** — see [permission-matrix](../docs/security/permission-matrix.md).

**Trust boundary:**
`gcs_upload —enforces→ R7` (uploads confined to `gs://<bucket>/sessions/{id}/`).

## How to use this graph

- Resolve any demo question to one or more entity IDs, then follow `relationships`
  edges to assemble a code-true answer.
- Every node carries an `evidence` field (`file:line` or migration) — cite it.
- If a question maps to a `not_implemented` concept, answer that rounds.vin does
  not implement it (it is transcript software, not an inspection platform).

## Source Verification
- **Files Used:** frontend/src/router/index.ts, frontend/src/components/AppHeader.vue, app/engines/state_machine.py, app/tasks/sop_tasks.py, app/security/roles.py, app/api/sessions.py, app/config.py, migrations/* — plus the verified corpus in `docs/` from the prior generation run.
- **Components Used:** AppHeader.vue (nav truth)
- **APIs Used:** 20 routers under app/api/
- **Database Tables Used:** 19 core domain tables (see `data-dictionary.md`)
- **Permission Logic Used:** JWT (`app/auth.py:172`) + LEGACY_ADMIN_EMAIL gate (`app/security/roles.py:54`)
- **Confidence Score:** High — entities/edges traced to file:line; FSM + SOP SLAs + nav read directly from source this session.
- **Evidence Links:** [state_machine.py:40](../app/engines/state_machine.py#L40), [sop_tasks.py:36](../app/tasks/sop_tasks.py#L36), [router/index.ts:27](../frontend/src/router/index.ts#L27), [AppHeader.vue:149](../frontend/src/components/AppHeader.vue#L149)
