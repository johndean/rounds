# Business Rules — rounds.vin (BR-001 … BR-020)

> Code-verified restatement of the rules indexed in [`docs/BUSINESS_RULES.md`](../docs/BUSINESS_RULES.md).
> Each rule was re-checked against the cited source. Where the index table in the
> source doc carries a stale line number, the current verified line is used here and
> the drift is flagged. Constants under the "LOCKED weights" block are pinned by
> `tests/test_health.py::test_locked_weights_match_audit`.

## Index

| ID | Rule | Verified location | Current truth |
|----|------|-------------------|---------------|
| BR-001 | Bootstrap admin email gate (`LEGACY_ADMIN_EMAIL`) | [app/security/roles.py:54](../app/security/roles.py#L54) | Active — the ONLY real admin gate |
| BR-002 | Session trash carve-out (`SESSION_TRASH_ALLOWED`) | [app/api/sessions.py:52](../app/api/sessions.py#L52) | Active |
| BR-003 | Per-stage SLA hours (`_DEFAULT_SLA_HOURS`) | [app/tasks/sop_tasks.py:36](../app/tasks/sop_tasks.py#L36) | Active |
| BR-004 | 23-hour deadline-email throttle | [app/tasks/sop_tasks.py](../app/tasks/sop_tasks.py) | Active only when email flag ON (default OFF) |
| BR-005 | Zero-hour deadline-email grace | [app/tasks/sop_tasks.py](../app/tasks/sop_tasks.py) | Active (no grace constant) |
| BR-006 | Confidence-threshold priority scoring | [app/api/corrections.py](../app/api/corrections.py) | Active |
| BR-007 | Session FSM allowed transitions | [app/engines/state_machine.py:40](../app/engines/state_machine.py#L40) | Active |
| BR-008 | Locked fusion weights | [app/config.py:58](../app/config.py#L58) | Active (locked) |
| BR-009 | Locked alignment weights | [app/config.py:63](../app/config.py#L63) | Active (locked) |
| BR-010 | IIL TIER2 confidence gate | [app/config.py:71](../app/config.py#L71) | Active (locked) |
| BR-011 | Frame visual-change threshold | [app/config.py:53](../app/config.py#L53) | Active (locked) |
| BR-012 | Idempotency-key TTL (86400s) | [app/config.py:77](../app/config.py#L77) | Active |
| BR-013 | Signed-URL TTL (3600s) | [app/api/gcs_upload.py:50](../app/api/gcs_upload.py#L50) | Active |
| BR-014 | Upload-stuck threshold (300s) | [app/config.py:101](../app/config.py#L101) | Active only when watchdog flag ON (default OFF) |
| BR-015 | Gemini hallucination-loop detector | [app/tasks/ai_process.py:63](../app/tasks/ai_process.py#L63) | Active (direct AI-mode path only) |
| BR-016 | Filler-word stripping is format-specific | [app/engines/artifact_transformer.py](../app/engines/artifact_transformer.py) | Active |
| BR-017 | Empty speaker label fallback (`"(Unknown)"`) | [app/engines/artifact_transformer.py](../app/engines/artifact_transformer.py) | Active |
| BR-018 | Correction types that auto-close discrepancies | [app/api/corrections.py:63](../app/api/corrections.py#L63) | Active |
| BR-019 | Session title precedence cascade | [frontend/src/services/api.ts](../frontend/src/services/api.ts) | Active (client-side) |
| BR-020 | `auth_users` env-CSV fallback | [app/auth.py](../app/auth.py) | Active |

> **Line-number drift flagged:** the index table in `docs/BUSINESS_RULES.md` cites
> `LEGACY_ADMIN_EMAIL` at `roles.py:41`, but the constant is at
> [app/security/roles.py:54](../app/security/roles.py#L54) (verified). The same doc's
> prose body and `docs/security/permission-matrix.md` both correctly cite line 54.
> `config.py` line numbers in the source index are likewise a few lines off from the
> current file; verified offsets are used in the table above.

---

## BR-001 — Bootstrap admin email gate
`LEGACY_ADMIN_EMAIL = "johndean@vin.com"` ([app/security/roles.py:54](../app/security/roles.py#L54)). **This is the only operative admin gate in the running system.** `require_admin`/`is_admin` accept an optional `role=` arg, but no caller supplies it and `get_current_user` never loads `auth_users.role`, so every admin check falls through to a case-sensitive string equality on `user.email`. Re-exported as `ADMIN_EMAIL` in `app/api/sessions.py`. See [permissions.md](./permissions.md) for the full reality.

## BR-002 — Session trash carve-out
`SESSION_TRASH_ALLOWED = {ADMIN_EMAIL, "carlab@vin.com"}` ([app/api/sessions.py:52](../app/api/sessions.py#L52)). Gates the soft-delete action only — `carlab@vin.com` (an external service account) can soft-delete its own test sessions without a general admin grant. Not a tier; a per-action allowlist.

## BR-003 — Per-stage SLA hours
`_DEFAULT_SLA_HOURS` ([app/tasks/sop_tasks.py:36](../app/tasks/sop_tasks.py#L36)): prep 8, copy_draft 24, medical 48, copy_final 24, cms 12, captions 12, qa 8, complete 0 (terminal). Org-wide default applied at auto-init; per-session overrides live in `sop_state.sla_target_hours`. The same 8-entry map is inlined in [app/api/queue.py:69](../app/api/queue.py#L69) for `/v1/queue/mine` overdue computation.

## BR-004 — 23-hour deadline-email throttle window
Once a deadline email fires for a `(session, stage)` pair, no second email fires for 23 hours. Enforced by an `audit_events` row of kind `sop.deadline_email_sent | sop.deadline_email_failed` plus a Postgres advisory lock. **Only active when `SOP_DEADLINE_EMAIL_ENABLED` is true (default OFF, [app/config.py:110](../app/config.py#L110)).**

## BR-005 — Zero-hour deadline-email grace period
No grace period: a stage that is one minute past SLA is overdue. There is no `_DEADLINE_GRACE_HOURS` constant; `overdue_hours > 0` is the only check. The 23h throttle (BR-004) is the only thing that prevents repeat sends.

## BR-006 — Confidence-threshold priority scoring
The editor's "next discrepancy" cursor ranks pending alignments by a deterministic integer score: confidence < 0.4 adds +70, confidence < 0.6 adds +20 (both can apply), plus drift/uncertain/review flags ([app/api/corrections.py](../app/api/corrections.py), priority-scoring block). Reviewers see the lowest-confidence rows first. Tuning is pinned by the locked-weights test.

## BR-007 — Session state-machine allowed transitions
`ALLOWED_TRANSITIONS` ([app/engines/state_machine.py:40](../app/engines/state_machine.py#L40)) is the single source of truth for legal `sessions.status` *transitions*. Valid *values* are also enforced by the `sessions_status_check` CHECK constraint (migration 010) — the FSM guards *moves*, the CHECK guards *values*. The verified map (per [docs/workflows/ingest-pipeline.md](../docs/workflows/ingest-pipeline.md)):
```
uploading    → transcribing | ready | failed
transcribing → normalizing  | failed
normalizing  → fusing       | failed
fusing       → aligning     | failed
aligning     → ready        | failed
ready        → complete     | failed
```
`failed → transcribing/normalizing` is the operator reingest escape hatch.

## BR-008 — Locked fusion weights
`FUSION_WEIGHT_VISUAL=0.5`, `FUSION_WEIGHT_ANCHOR=0.3`, `FUSION_WEIGHT_SEMANTIC=0.2`, `FUSION_BOUNDARY_THRESHOLD=0.35` ([app/config.py:58](../app/config.py#L58)). Sum to 1.0, locked; drift fails `test_locked_weights_match_audit`. Changing them moves slide boundaries in finalized transcripts.

## BR-009 — Locked alignment weights
`ALIGN_WEIGHT_SEMANTIC=0.35`, `ALIGN_WEIGHT_COVERAGE=0.25`, `ALIGN_WEIGHT_TEMPORAL=0.25`, `ALIGN_WEIGHT_SEQUENTIAL=0.15`, `ALIGN_SEQUENTIAL_PENALTY=0.8` ([app/config.py:63](../app/config.py#L63)). Locked the same way as BR-008. Alignment confidence drives the discrepancies surface (BR-006).

## BR-010 — IIL TIER2 confidence gate
`IIL_TIER2_DEFAULT_THRESHOLD=0.7`, `IIL_TIER2_MODERATE_THRESHOLD=0.85` ([app/config.py:71](../app/config.py#L71)). Tier-2 normalization fires only at/above threshold. Locked; clinical-safety implication — be conservative.

## BR-011 — Frame visual-change threshold
`VISUAL_CHANGE_THRESHOLD=8.0` ([app/config.py:53](../app/config.py#L53)). A frame is a "visual change" only above this score; drives anchor-frame detection. Locked.

## BR-012 — Idempotency-key TTL (86400s)
`IDEMPOTENCY_KEY_TTL_SECONDS=86400` ([app/config.py:77](../app/config.py#L77)), enforced in `app/middleware/idempotency.py`. A repeated `Idempotency-Key` within 24h replays the cached response instead of re-running the side-effect.

## BR-013 — Signed-URL TTL (3600s)
Pre-signed GCS PUT URLs are valid for 60 minutes. `_DEFAULT_SIGNED_URL_TTL_SECONDS = 3600` ([app/api/gcs_upload.py:50](../app/api/gcs_upload.py#L50)); the service default is `make_signed_put_url(..., ttl_minutes=60)` ([app/services/gcs.py:73](../app/services/gcs.py#L73)).

## BR-014 — Upload-stuck threshold (300s)
`UPLOAD_STUCK_THRESHOLD_SEC=300` ([app/config.py:101](../app/config.py#L101)). Minimum age (since `updated_at`) before the watchdog treats an `uploading` session as stuck. **Only active when `UPLOAD_WATCHDOG_ENABLED` is true (default OFF, [app/config.py:100](../app/config.py#L100)).**

## BR-015 — Gemini hallucination-loop detector
`MIN_BLOCK = 80`, `MIN_REPS = 3` ([app/tasks/ai_process.py:63](../app/tasks/ai_process.py#L63)). Any 80-char block repeated ≥3× truncates the response at the first occurrence. Applies to the direct AI-mode Gemini STT path (`_process_direct`); does NOT apply to the chunked Google STT fallback.

## BR-016 — Filler-word stripping is format-specific
`docx`/`txt` exports strip fillers (`um, uh, er, ah, umm, uhh, hmm` — `TIER1_WORDS`); `srt`/`vtt` preserve them so captions stay in sync with audio. Enforced in the per-format transforms of [app/engines/artifact_transformer.py](../app/engines/artifact_transformer.py); the word set is in `app/iil/normalization.py`.

## BR-017 — Empty speaker label fallback
Segments with no resolved speaker export the literal `(Unknown)` rather than a blank field, keeping the export schema consistent and the gap reviewer-visible. In the per-segment serializer of [app/engines/artifact_transformer.py](../app/engines/artifact_transformer.py).

## BR-018 — Correction types that auto-close discrepancies
`CLOSES_DISCREPANCY_TYPES = frozenset({"text_edit", "mark_ok"})` ([app/api/corrections.py:63](../app/api/corrections.py#L63)). Only these two close a segment's open discrepancy. `find_replace`, `chat_edit`, `speaker_reassignment`, `split`, `merge`, slide/poll do NOT. (Note: the source prose body cites this at `corrections.py:49`; the constant is actually at line 63 — line 49 is the `ALLOWED_CORRECTION_TYPES` allowlist.)

## BR-019 — Session title precedence cascade
The frontend displays `title_long > title_short > title` (first non-empty wins) in the session DTO mapper, [frontend/src/services/api.ts](../frontend/src/services/api.ts). Client-side rule so every list/detail/breadcrumb shows the same string.

## BR-020 — `auth_users` env-CSV fallback
During the env-CSV → DB `auth_users` migration, JWT lookup falls back to the `AUTH_USERS` env var if the DB row is missing, keeping logins working through a deploy where the seed hasn't fired. In the `get_current_user` resolution path of [app/auth.py](../app/auth.py); seeder is `app/services/auth_users.py::seed_from_env_if_empty`.

---

## Notes on rules that are flag-gated or scaffold-adjacent

- **BR-004 / BR-014** describe behavior that is **inert by default** because their feature flags (`SOP_DEADLINE_EMAIL_ENABLED`, `UPLOAD_WATCHDOG_ENABLED`) default to `False`. The constants exist and are correct, but the surrounding workflow does not run until the flag is flipped in Railway env.
- **BR-001** is the linchpin of the whole authorization story: it is the single hardcoded email gate, NOT a role tier. `auth_users.role` exists (migration 045) but is never read at request time. See [permissions.md](./permissions.md).
- The locked-weight family (BR-008..BR-011) cannot be changed without breaking CI; treat any "tune the weights" demo request as requiring an audit + explicit authorization.

## Source Verification
- **Files Used:** docs/BUSINESS_RULES.md, app/security/roles.py, app/api/sessions.py, app/tasks/sop_tasks.py, app/api/corrections.py, app/engines/state_machine.py, app/config.py, app/api/gcs_upload.py, app/services/gcs.py, app/tasks/ai_process.py, app/api/queue.py
- **Components Used:** none (BR-019 lives in frontend/src/services/api.ts, referenced not re-read)
- **APIs Used:** /v1/sessions* (trash), /v1/sessions/{id}/sop*, /v1/queue/mine, /v1/gcs/upload-url, /v1/sessions/{id}/corrections, /v1/sessions/{id}/exports/{format}
- **Database Tables Used:** auth_users, sessions, sop_state, audit_events, correction_ledger, transcription_discrepancies
- **Permission Logic Used:** BR-001/BR-002 ARE the permission rules — JWT + `LEGACY_ADMIN_EMAIL = "johndean@vin.com"` gate + `SESSION_TRASH_ALLOWED` carve-out. `auth_users.role` not read.
- **Confidence Score:** High — every constant cited was grepped/read at HEAD; three stale line numbers in the source index table were corrected and flagged.
- **Evidence Links:** [app/security/roles.py:54](../app/security/roles.py#L54), [app/api/sessions.py:52](../app/api/sessions.py#L52), [app/api/corrections.py:63](../app/api/corrections.py#L63), [app/tasks/sop_tasks.py:36](../app/tasks/sop_tasks.py#L36), [app/tasks/ai_process.py:63](../app/tasks/ai_process.py#L63), [app/config.py:100](../app/config.py#L100), [app/config.py:110](../app/config.py#L110)
