# Rounds — Business Rules Index

> **Purpose.** Every business / domain rule that today lives only in source code is indexed here with a stable ID (`BR-NNN`), a citation to the canonical line, and the reasoning a future maintainer needs in order to change it safely. New rules MUST be appended here when they are added to the codebase. Renumbering existing IDs is forbidden — the IDs are cited from inline comments and from ADRs.
>
> **Status.** Created 2026-06-05 as Phase 1 of the documentation uplift (`docs/UPLIFT_REPORT_2026-06-05.md`). Indexes 20 rules extracted from the codebase reality audit at HEAD `56eb009`.
>
> **How to cite.** From source: `# BR-NNN — <one-line summary>`. From an ADR: link to `docs/BUSINESS_RULES.md#br-nnn`. Section anchors are `#br-001`, `#br-002`, …

---

## Index

| ID | Rule | Canonical location |
|----|------|--------------------|
| [BR-001](#br-001) | Bootstrap admin email gate (`LEGACY_ADMIN_EMAIL`) | `app/security/roles.py:41` |
| [BR-002](#br-002) | Session trash carve-out (`SESSION_TRASH_ALLOWED`) | `app/api/sessions.py:36` |
| [BR-003](#br-003) | Per-stage SLA hours (`_DEFAULT_SLA_HOURS`) | `app/tasks/sop_tasks.py:32` |
| [BR-004](#br-004) | 23-hour deadline-email throttle window | `app/tasks/sop_tasks.py:294` |
| [BR-005](#br-005) | Zero-hour deadline-email grace period | `app/tasks/sop_tasks.py` (implicit in throttle logic) |
| [BR-006](#br-006) | Confidence-threshold priority scoring (<0.4 → +70, <0.6 → +20) | `app/api/corrections.py:577` |
| [BR-007](#br-007) | Session state-machine allowed transitions (`ALLOWED_TRANSITIONS`) | `app/engines/state_machine.py:37` |
| [BR-008](#br-008) | Locked fusion weights (visual / anchor / semantic) | `app/config.py:49` |
| [BR-009](#br-009) | Locked alignment weights (semantic / coverage / temporal / sequential) | `app/config.py:54` |
| [BR-010](#br-010) | IIL TIER2 confidence gate (0.7 default) | `app/config.py:62` |
| [BR-011](#br-011) | Frame visual-change threshold (8.0) | `app/config.py:44` |
| [BR-012](#br-012) | Idempotency-key TTL (86400s) | `app/config.py:68`, enforced in `app/middleware/idempotency.py` |
| [BR-013](#br-013) | Signed-URL TTL (3600s) | `app/api/add_to_session.py:62` |
| [BR-014](#br-014) | Upload-stuck threshold (300s) | `app/config.py:92` |
| [BR-015](#br-015) | Gemini hallucination-loop detector (`MIN_BLOCK=80`, `MIN_REPS=3`) | `app/tasks/ai_process.py:52` |
| [BR-016](#br-016) | Filler-word stripping is format-specific | `app/engines/artifact_transformer.py` |
| [BR-017](#br-017) | Empty speaker label fallback (`"(Unknown)"`) on export | `app/engines/artifact_transformer.py` |
| [BR-018](#br-018) | Correction types that auto-close discrepancies (`CLOSES_DISCREPANCY_TYPES`) | `app/api/corrections.py:49` |
| [BR-019](#br-019) | Session title precedence cascade (long → short → fallback) | `frontend/src/services/api.ts` |
| [BR-020](#br-020) | `auth_users` env-CSV fallback (cutover safety) | `app/auth.py` |

---

## BR-001 — Bootstrap admin email gate

- **Purpose.** Rounds needs a single named superadmin during the period before role-based access control is fully wired into `auth_users.role`. That account can hit every operator / diagnostic / settings surface regardless of org-level role.
- **Location.** `app/security/roles.py:41`
- **Code reference.**
  ```python
  LEGACY_ADMIN_EMAIL = "johndean@vin.com"
  ```
  Used by `is_legacy_admin(user)` at `app/security/roles.py:79` and re-exported as `ADMIN_EMAIL` in `app/api/sessions.py:19`.
- **Stakeholder impact.** Whoever owns this address has implicit superadmin everywhere. If the address changes (handover, departure), every operator surface that gates on `is_legacy_admin` breaks until this constant is updated.
- **Dependencies.** [BR-002](#br-002) (SESSION_TRASH_ALLOWED includes this email), the `/v1/diag/*` family of routes, [ADR-001](./adr/ADR-001-authentication.md).
- **Risk if changed.** Changing the literal moves all admin power to whatever new address is set. Removing the constant breaks every callsite. Migrating away from the literal requires wiring `auth_users.role = 'superadmin'` checks into every callsite (`/v1/sessions/*` trash, `/v1/diag/*`, settings UI), at which point this rule can be retired.
- **Related ADR.** [ADR-001 — Authentication](./adr/ADR-001-authentication.md).

## BR-002 — Session trash carve-out

- **Purpose.** Soft-delete + restore + purge of session rows is restricted to a small allow-list. The list intentionally includes one **external service account** (`carlab@vin.com`) which is used by an integration partner — they must be able to clean up their own test sessions without granting them full admin rights.
- **Location.** `app/api/sessions.py:36`
- **Code reference.**
  ```python
  SESSION_TRASH_ALLOWED = {ADMIN_EMAIL, "carlab@vin.com"}
  ```
  Enforced at `app/api/sessions.py:614` in the trash endpoint.
- **Stakeholder impact.** External-service partners (carlab) can soft-delete their own test sessions. Internal users without admin rights cannot trash anything.
- **Dependencies.** [BR-001](#br-001) (relies on `LEGACY_ADMIN_EMAIL` for the in-house side).
- **Risk if changed.** Adding addresses here grants destructive-data-loss power. Removing carlab@vin.com breaks an external partner workflow — coordinate with the integration owner before changing.
- **Related ADR.** [ADR-002 — Session lifecycle](./adr/ADR-002-session-lifecycle.md).

## BR-003 — Per-stage SLA hours

- **Purpose.** Each SOP stage carries a target SLA (in hours) that drives the overdue-email scheduler. Per-session overrides live in `sop_state.sla_target_hours`; the dictionary below is the **org-wide default** applied when a session is auto-initialized.
- **Location.** `app/tasks/sop_tasks.py:32`
- **Code reference.**
  ```python
  _DEFAULT_SLA_HOURS = {
      "prep":       8,
      "copy_draft": 24,
      "medical":    48,
      "copy_final": 24,
      "cms":        12,
      "captions":   12,
      "qa":         8,
      "complete":   0,  # terminal
  }
  ```
- **Stakeholder impact.** Stage assignees (medical reviewers, copy editors, QA) get deadline emails the moment their stage exceeds the SLA above. Changing a value here changes the cadence of those alerts for **all new sessions** (existing sessions retain their snapshot in `sop_state.sla_target_hours`).
- **Dependencies.** [BR-004](#br-004) (throttle), [BR-005](#br-005) (grace), [ADR-006](./adr/ADR-006-queue-processing.md) (Beat dispatch).
- **Risk if changed.** Setting a value too low floods reviewers; setting too high lets work sit. The medical-review SLA (48h) is the longest by design — clinical review can require external citation lookup.

## BR-004 — 23-hour deadline-email throttle window

- **Purpose.** Once a deadline email fires for a `(session, stage)` pair, no second email may fire for **23 hours**. Prevents the hourly `sop_check_deadlines_task` from re-emailing every Beat tick on the same overdue stage.
- **Location.** `app/tasks/sop_tasks.py:294`
- **Code reference.**
  ```python
  if datetime.now(timezone.utc) - last < timedelta(hours=23):
      # throttled — skip
  ```
- **Stakeholder impact.** Stage assignees see at most one deadline email per day per stage, even if the Beat scheduler runs hourly.
- **Dependencies.** [BR-003](#br-003) (SLA table that triggers the email), [BR-005](#br-005) (grace = 0). The throttle is implemented by a `(session_id, stage)` `audit_events` row with kind `sop.deadline_email_sent | sop.deadline_email_failed` plus an advisory lock for atomicity (`_deadline_lock_key`).
- **Risk if changed.** Shortening to <24h could cause two emails on consecutive days for the same stage (interpreted as spam). Lengthening past 24h may cause an assignee to never get a daily reminder.

## BR-005 — Zero-hour deadline-email grace period

- **Purpose.** Deadline emails fire the **moment** SLA elapses — no grace period is applied. The throttle window in [BR-004](#br-004) is the only thing that prevents repeat sends.
- **Location.** `app/tasks/sop_tasks.py` — implicit; no `grace_hours` constant is added because `overdue_hours > 0` is the only check.
- **Stakeholder impact.** A reviewer who is one minute past SLA gets the email on the next hourly Beat tick.
- **Dependencies.** [BR-003](#br-003), [BR-004](#br-004).
- **Risk if changed.** Adding a grace period would require introducing a new constant (e.g. `_DEADLINE_GRACE_HOURS`) and wiring it into the `overdue_hours` calculation in `sop_check_deadlines_task`. Operationally low-risk; the current "no grace" posture was a deliberate choice for the trial cohort.

## BR-006 — Confidence-threshold priority scoring

- **Purpose.** When the editor's "next discrepancy" cursor advances, it pulls the highest-priority pending alignment first. Priority is a deterministic integer score; rows with **confidence < 0.4** add **+70 points**, and **confidence < 0.6** adds **+20 points** (both can apply). The thresholds came out of MIC's audit-section-18 tuning.
- **Location.** `app/api/corrections.py:577`
- **Code reference.**
  ```python
  if a["drift_flag"]      and a["slide_id"] is None: score += 100
  if a["uncertain_flag"]  and a["slide_id"] is None: score += 90
  if (a["confidence"] or 0) < 0.4:                    score += 70
  if a["drift_flag"]:                                 score += 50
  if a["status"] == "review":                         score += 40
  if (a["confidence"] or 0) < 0.6:                    score += 20
  ```
- **Stakeholder impact.** Reviewers see the lowest-confidence rows first. Editors complete the most ambiguous edits earliest in the session.
- **Dependencies.** [ADR-005](./adr/ADR-005-corrections-ledger.md).
- **Risk if changed.** Re-ranking changes the order in which reviewers encounter problem segments. Coordinate with the audit-section-18 tuning record (locked weight; see `tests/test_health.py::test_locked_weights_match_audit`).

## BR-007 — Session state-machine allowed transitions

- **Purpose.** A session may move only between explicitly enumerated states. The `ALLOWED_TRANSITIONS` map is the **single source of truth** for legal session moves — neither the database (no CHECK constraint) nor any individual API route is allowed to bypass it without going through `app/engines/state_machine.py::ensure_can_transition`.
- **Location.** `app/engines/state_machine.py:37`
- **Code reference.**
  ```python
  ALLOWED_TRANSITIONS: dict[str, set[str]] = {
      "uploading":  {"ingesting", "failed"},
      "ingesting":  {"processing", "failed"},
      "processing": {"ready", "failed"},
      "ready":      {"published", "archived"},
      "published":  {"archived"},
      "archived":   set(),
      "failed":     {"ingesting", "processing"},  # escape-hatch for diag/reingest
  }
  ```
- **Stakeholder impact.** Operators (via `/v1/diag/reingest/*`) can re-enter the pipeline from `failed`. All other moves are gated.
- **Dependencies.** [ADR-002](./adr/ADR-002-session-lifecycle.md), [ADR-003](./adr/ADR-003-fsm-python-only.md).
- **Risk if changed.** Adding a transition opens a new lifecycle path; verify every downstream task tolerates the new origin state. The FSM has **no schema-level enforcement** — `sessions.status` is `TEXT NOT NULL DEFAULT 'ingesting'`. See [ADR-003](./adr/ADR-003-fsm-python-only.md) for why and what would be required to harden it.

## BR-008 — Locked fusion weights (visual / anchor / semantic)

- **Purpose.** The fusion engine combines three independent signals (visual change, anchor cross-reference, semantic similarity) into a single boundary score. The three weights sum to 1.0 and are **locked** to the values derived from MIC's audit §6 — they are pinned by a test (`tests/test_health.py::test_locked_weights_match_audit`) so any drift breaks CI.
- **Location.** `app/config.py:49`
- **Code reference.**
  ```python
  FUSION_WEIGHT_VISUAL: float = 0.5
  FUSION_WEIGHT_ANCHOR: float = 0.3
  FUSION_WEIGHT_SEMANTIC: float = 0.2
  FUSION_BOUNDARY_THRESHOLD: float = 0.35
  ```
- **Stakeholder impact.** Any drift in these numbers changes where slide boundaries land in finalized transcripts. Reviewer-visible.
- **Dependencies.** [ADR-007](./adr/ADR-007-locked-weights.md). Also see [BR-009](#br-009), [BR-010](#br-010), [BR-011](#br-011) for the rest of the locked-weight family.
- **Risk if changed.** A change here will fail `test_locked_weights_match_audit`. Re-tuning requires an audit pass + plan-doc decision + explicit user authorization.

## BR-009 — Locked alignment weights (semantic / coverage / temporal / sequential)

- **Purpose.** The alignment engine matches segments to slides via a weighted four-factor score (semantic match, coverage of slide words, temporal proximity, sequential adjacency). Weights sum to 1.0 and are **locked** the same way as [BR-008](#br-008).
- **Location.** `app/config.py:54`
- **Code reference.**
  ```python
  ALIGN_WEIGHT_SEMANTIC: float = 0.35
  ALIGN_WEIGHT_COVERAGE: float = 0.25
  ALIGN_WEIGHT_TEMPORAL: float = 0.25
  ALIGN_WEIGHT_SEQUENTIAL: float = 0.15
  ALIGN_SEQUENTIAL_PENALTY: float = 0.8
  ```
- **Stakeholder impact.** Reviewer-visible. Alignment confidence directly drives the discrepancies surface ([BR-006](#br-006)).
- **Dependencies.** [ADR-007](./adr/ADR-007-locked-weights.md).
- **Risk if changed.** Same as [BR-008](#br-008).

## BR-010 — IIL TIER2 confidence gate (0.7 default)

- **Purpose.** Internal Intent Layer (IIL) Tier 2 normalization will fire only when the confidence of the candidate normalization meets or exceeds `IIL_TIER2_DEFAULT_THRESHOLD`. Lowering this threshold accepts more aggressive normalizations; raising it preserves more raw text.
- **Location.** `app/config.py:62`
- **Code reference.**
  ```python
  IIL_TIER2_DEFAULT_THRESHOLD: float = 0.7
  IIL_TIER2_MODERATE_THRESHOLD: float = 0.85
  ```
- **Stakeholder impact.** Clinical reviewers see normalized text in the editor; raw text is preserved in audit. Aggressive normalization can mask clinical nuance.
- **Dependencies.** [ADR-007](./adr/ADR-007-locked-weights.md).
- **Risk if changed.** Same as [BR-008](#br-008). Clinical safety implication: be conservative.

## BR-011 — Frame visual-change threshold

- **Purpose.** The frame-sampler treats a frame as a "visual change" only when the change score exceeds `VISUAL_CHANGE_THRESHOLD = 8.0`. Drives anchor-frame detection.
- **Location.** `app/config.py:44`
- **Code reference.**
  ```python
  VISUAL_CHANGE_THRESHOLD: float = 8.0
  ```
- **Stakeholder impact.** Determines how many visual anchors a session produces. Too low → too many anchors, noisy boundaries; too high → too few anchors, drift.
- **Dependencies.** [BR-008](#br-008) (fusion uses anchor count).
- **Risk if changed.** Locked weight. Same change-control posture as [BR-008](#br-008).

## BR-012 — Idempotency-key TTL (86400s)

- **Purpose.** A client that sends the same `Idempotency-Key` header within **24 hours** gets the cached prior response replayed instead of a duplicate side-effect. Beyond 24h, the key is forgotten and a new submission is treated as fresh.
- **Location.** `app/config.py:68`; enforcement at `app/middleware/idempotency.py`.
- **Code reference.**
  ```python
  IDEMPOTENCY_KEY_TTL_SECONDS: int = 86400
  ```
- **Stakeholder impact.** Mobile-network retries replay safely for one day. Background reconciliations that span >24h must mint a new key for the same logical action.
- **Dependencies.** None.
- **Risk if changed.** Shortening risks double-side-effect during the gap between TTL expiry and retry. Lengthening grows Redis storage proportionally.

## BR-013 — Signed-URL TTL (3600s)

- **Purpose.** Pre-signed GCS PUT URLs are valid for exactly **60 minutes**. Long enough for a normal browser upload; short enough that a leaked URL has limited blast radius.
- **Location.** `app/api/add_to_session.py:62`, mirrored at `app/api/gcs_upload.py:44`.
- **Code reference.**
  ```python
  _SIGNED_URL_TTL_SECONDS = 3600
  ```
- **Stakeholder impact.** Slow uploaders (rural network, large file) may see the URL expire before the upload finishes. The frontend re-requests on 401 / 403.
- **Dependencies.** R7 invariant (gcs scope), [ADR-001](./adr/ADR-001-authentication.md).
- **Risk if changed.** Lengthening grows the leak window. Shortening can break legitimate uploads of large clinical recordings.

## BR-014 — Upload-stuck threshold (300s)

- **Purpose.** The `upload_watchdog` Celery Beat task treats any session whose status is `uploading` and whose `updated_at` is older than **5 minutes** as a candidate for rescue (re-enqueue the ingest task that silently failed). 5 minutes is well past the expected upload time even for large files.
- **Location.** `app/config.py:92`
- **Code reference.**
  ```python
  UPLOAD_STUCK_THRESHOLD_SEC: int = 300       # 5min — minimum age before considering 'stuck'
  ```
- **Stakeholder impact.** Users who actually have a slow ongoing upload will see the watchdog rescue fire **after** their upload would have succeeded normally — the threshold is intentionally longer than a healthy upload.
- **Dependencies.** `UPLOAD_WATCHDOG_ENABLED` flag at `app/config.py:91` (default false) and the 60s beat tick. Watchdog is **off by default**.
- **Risk if changed.** Shortening risks rescuing healthy slow uploads (double-enqueue). Lengthening leaves users stuck longer when the silent failure path fires.

## BR-015 — Gemini hallucination-loop detector (`MIN_BLOCK=80`, `MIN_REPS=3`)

- **Purpose.** Gemini's STT output can degrade into a runaway repetition loop (the same ~80-char chunk repeats indefinitely). The detector scans for any 80-character substring that appears **3 or more times** and truncates the response at the start of the first repetition. The thresholds are intentionally conservative — false positives would clip legitimate transcripts.
- **Location.** `app/tasks/ai_process.py:52`
- **Code reference.**
  ```python
  MIN_BLOCK = 80
  MIN_REPS  = 3
  ```
- **Stakeholder impact.** Saves real cost (a runaway loop can burn 100k+ output tokens before timing out) and prevents reviewers from being handed a transcript that's mostly garbage.
- **Dependencies.** Gemini STT path (`_process_direct`); does not apply to the chunked Google STT fallback.
- **Risk if changed.** Lowering thresholds risks clipping a legitimate transcript that happens to contain a long repeated phrase (e.g. a chant, an enumerated list). Raising them risks letting more hallucination tokens through.

## BR-016 — Filler-word stripping is format-specific

- **Purpose.** Export to `.docx` strips filler words (`um`, `uh`, `er`, `ah`, `umm`, `uhh`, `hmm`) for readability — that's the format the medical writer hands to the practice. Export to `.srt` and `.vtt` **preserves** fillers so the captions match the audio. Export to `.txt` strips. The rule is enforced in the per-format transform inside the artifact transformer.
- **Location.** `app/engines/artifact_transformer.py` (format dispatch around the `to_docx` / `to_srt` / `to_vtt` / `to_txt` functions).
- **Code reference.** The TIER1 word set is defined at `app/iil/normalization.py:37`:
  ```python
  TIER1_WORDS = frozenset(["um", "uh", "er", "ah", "umm", "uhh", "hmm"])
  ```
- **Stakeholder impact.** Clinicians read clean prose. Caption viewers see what was actually said.
- **Dependencies.** [BR-009](#br-009) (alignment), the corrections ledger ([ADR-005](./adr/ADR-005-corrections-ledger.md)).
- **Risk if changed.** Stripping captions would desynchronize them from the audio (caption appears at time T but the audio at T is a filler word that no longer maps to any displayed text). Preserving docx fillers harms readability.

## BR-017 — Empty speaker label fallback (`"(Unknown)"`)

- **Purpose.** When a segment has no resolved speaker, the export engine emits the literal string `(Unknown)` rather than leaving the field blank. Keeps the export schema consistent and makes the gap visible to the reviewer.
- **Location.** `app/engines/artifact_transformer.py` (in the per-segment serializer around the `speaker` field).
- **Stakeholder impact.** Editors can `Ctrl-F "(Unknown)"` in the exported doc to find unresolved speakers.
- **Dependencies.** None.
- **Risk if changed.** Removing the fallback could produce malformed downstream documents (e.g. docx tables with empty header cells). Changing the literal will need a sweep of downstream consumers.

## BR-018 — Correction types that auto-close discrepancies

- **Purpose.** When a correction of type `text_edit` or `mark_ok` is applied, any discrepancy attached to the same segment is automatically marked resolved. Other correction types (e.g. `find_replace`, `chat_edit`, `speaker_edit`) do **not** auto-close discrepancies.
- **Location.** `app/api/corrections.py:49`
- **Code reference.**
  ```python
  CLOSES_DISCREPANCY_TYPES = frozenset({"text_edit", "mark_ok"})
  ```
  Consumed at `app/api/corrections.py:224`.
- **Stakeholder impact.** Editors who apply a `text_edit` correction at the exact spot of a discrepancy clear the discrepancy in one action. `mark_ok` is the explicit "no change needed" close.
- **Dependencies.** [BR-006](#br-006), the discrepancies pane in the editor.
- **Risk if changed.** Adding a type here can mass-close discrepancies that an operator did not intend to close. Removing `mark_ok` would orphan the explicit "no change" close button.

## BR-019 — Session title precedence cascade

- **Purpose.** When the frontend displays a session, the title used is `title_long > title_short > title` (first non-empty wins, where `title` is the legacy field). Locked so that every list / detail / breadcrumb shows the same string.
- **Location.** `frontend/src/services/api.ts` (in the session DTO mapper).
- **Stakeholder impact.** Reviewer sees one canonical title across all surfaces.
- **Dependencies.** None.
- **Risk if changed.** Changing precedence (or adding a fourth fallback) will diverge the title across surfaces unless every consumer is updated together.

## BR-020 — `auth_users` env-CSV fallback (cutover safety)

- **Purpose.** During the migration from env-CSV-based auth to database-backed `auth_users`, the JWT lookup falls back to the `AUTH_USERS` env variable if the corresponding DB row is missing. Keeps logins working through the cutover window where the migration may have run but the seeder hasn't fired yet.
- **Location.** `app/auth.py` (in the `get_current_user` resolution path).
- **Stakeholder impact.** Operators don't get locked out during a Railway deploy where the seed hasn't completed.
- **Dependencies.** [ADR-001](./adr/ADR-001-authentication.md), `app/services/auth_users.py::seed_from_env_if_empty`.
- **Risk if changed.** Removing the fallback before the seed is universally reliable risks locking out users mid-deploy. The fallback's eventual removal is tracked under the "AUTH_USERS plaintext debt" item.

---

## How to add a new rule

1. Assign the next free `BR-NNN` (no renumbering).
2. Append a section using the structure above (purpose, location, code reference, stakeholder impact, dependencies, risk if changed).
3. Add a row in the Index table.
4. Where the rule appears in code, add an inline comment of the form:
   ```python
   # BR-NNN — <one-line summary>. See docs/BUSINESS_RULES.md#br-nnn.
   ```
5. If the rule materializes an architectural decision, cross-link it from the relevant ADR under `docs/adr/`.

## Out-of-scope today (acknowledged gaps)

The following are domain rules that exist in code but were either too granular for this initial index (single-use validators, per-component UI thresholds) or are best documented inside ADRs because they shape architecture rather than business behavior:

- Per-endpoint rate-limit slots (`MAX_CONCURRENT_SESSIONS = 3`, `MAX_QUEUE_LENGTH = 10` at `app/config.py:37–38`) — operationally tuned, not business-derived.
- Max upload size + max video duration (`app/config.py:39–40`) — operational ceilings.
- ETag fingerprint format `W/"{session_id}-{max_correction_seq}"` for captions — implementation detail; see [ADR-005](./adr/ADR-005-corrections-ledger.md).
- The 16 specific `/v1/diag/*` operator routes — documented in `CLAUDE.md` under "Emergency operator commands."

A future revision of this document may absorb any of the above if they harden into business rules rather than tuning knobs.
