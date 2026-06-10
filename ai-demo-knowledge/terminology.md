# rounds.vin — Terminology (product-specific terms)

> Terms specific to rounds.vin and its AI transcript pipeline. Each is defined
> from code, with file:line evidence. For general industry terms (JWT, Celery,
> WebVTT, etc.) see [glossary.md](./glossary.md). Links relative to
> `ai-demo-knowledge/`. Unproven claims tagged `NOT VERIFIED IN CODE`.

## Session
The central unit of work: one uploaded recorded lecture and everything derived
from it (sources, transcript segments, words, slides, speakers, alignments,
discrepancies, SOP state). Stored in the `sessions` table; its lifecycle is
governed by a locked state machine
([app/engines/state_machine.py:40-49](../app/engines/state_machine.py#L40)).

## Session status / AI pipeline stage
The lifecycle state of a session as it moves through AI processing. Locked
transition map: `uploading → transcribing → normalizing → fusing → aligning →
ready`, with an AI-direct shortcut `uploading → ready` and a final SOP promotion
`ready → complete`. `failed` is terminal from any stage; `failed` and `complete`
are terminal states. No other moves are permitted
([app/engines/state_machine.py:40-49](../app/engines/state_machine.py#L40)). The
Dashboard calls this the "7-step AI processing pipeline."

## ai_pipeline (routing mode)
The pipeline route chosen at upload, stored on `session_templates`. `direct` runs
Gemini multimodal straight to `ready`; `standard`/`enhanced` run the full
transcribe → anchor → normalize → fusion → align → finalize chain (enhanced adds
a Gemini text-refine pass)
([docs/technical/processing-pipeline-technical-spec.md:15-31](../docs/technical/processing-pipeline-technical-spec.md#L15)).

## Segment
A contiguous chunk of transcript text with a start/end time, confidence, optional
slide and speaker, and a content hash. Produced by the deterministic 4-rule
segmenter and stored in the `segments` table; the conflict key is
`(session_id, content_hash)` so re-runs are idempotent
([docs/technical/processing-pipeline-technical-spec.md:139-143](../docs/technical/processing-pipeline-technical-spec.md#L139)).

## Segmenter (4-rule)
The deterministic word→segment grouping engine. Four rules applied in exact
order: (1) split on sentence-ending punctuation `.?!`; (2) merge consecutive
segments if combined duration < 2s; (3) split a segment if duration > 20s;
(4) split on a silence pause ≥ 500ms. Segment IDs are
`SHA256(session_id + start_ms)`, making the same inputs produce the same IDs
([app/engines/segmenter.py:1-13](../app/engines/segmenter.py#L1)).

## Anchor (and "ANCHORS phrase")
A slide-transition cue detected in segment text. The engine scans for a fixed
list of `ANCHORS` phrases ("next slide", "on this slide", "moving on", "turning
to", etc.). An anchor is **CONFIRMED** only when an ANCHORS phrase appears **and**
a visual change occurs within ±`ANCHOR_CROSS_VALIDATE_WINDOW` (5s) **or** the
semantic shift > 0.3; otherwise it is **speculative** and is not used as a
boundary signal in fusion. Confirmed anchors feed the fusion engine's locked
0.3-weight anchor signal
([app/engines/anchor.py:4-36](../app/engines/anchor.py#L4)).

## anchor_hit (alignment flag)
A boolean on an `alignments` row indicating the segment's slide assignment was
backed by a confirmed anchor
([docs/technical/processing-pipeline-technical-spec.md:158-161](../docs/technical/processing-pipeline-technical-spec.md#L158)).

## Fusion
The engine that combines three signals — visual change, confirmed anchors, and
semantic shift — into `slide_time_ranges` (when each slide was on screen) with a
confidence score. Locked weights: visual 0.5, anchor 0.3, semantic 0.2; a
boundary needs a fused score ≥ `FUSION_BOUNDARY_THRESHOLD` (0.35). A locked
signal-gating rule forbids the semantic signal from triggering a boundary alone
when visual change is below threshold and no anchor is confirmed. Boundary
timestamps are rounded to 0.5s for replay reproducibility
([app/engines/fusion.py:1-25](../app/engines/fusion.py#L1)).

## Fusion gate
A 5-assertion completeness check (`run_fusion_gate`) over the produced
`slide_time_ranges`. A gate failure raises `GateFailure` and halts the session
rather than retrying
([docs/technical/processing-pipeline-technical-spec.md:238-239](../docs/technical/processing-pipeline-technical-spec.md#L238)).

## Alignment (4-signal)
Per-segment scoring against every slide time range to pick the dominant slide.
Four signals with locked weights: semantic (token overlap with slide
bullets/text) 0.35, coverage (fraction of the segment inside the slide range)
0.25, temporal (linear proximity to slide center) 0.25, sequential (adjacency to
the prior segment's slide) 0.15, with a 0.8 penalty for backward jumps. Writes
an `alignments` row per segment
([app/engines/alignment.py:1-25](../app/engines/alignment.py#L1)).

## Drift / drift_flag
A low-confidence alignment signal. `drift_flag` is set when the best alignment
score < 0.6 and the segment is not already flagged uncertain (the MIC formula).
The IIL drift handling applies a confidence penalty
(`IIL_DRIFT_CONFIDENCE_PENALTY` = 0.3) and a realign window
(`IIL_DRIFT_REALIGN_WINDOW` = 20s)
([app/engines/alignment.py:18](../app/engines/alignment.py#L18),
[app/config.py:69-70](../app/config.py#L69)).

## uncertain_flag
An `alignments` flag marking a segment whose slide assignment is ambiguous;
combined with the alignment `status` value (`assigned` / `uncertain` / `review`)
([app/engines/alignment.py:57-66](../app/engines/alignment.py#L57)).

## IIL (Intelligent / Iterative normalization layer)
The normalization configuration applied to raw STT segments: filler-word policy,
terminology preservation, rewrite level, and tiered cleanup ("IIL tiers"). Tier
toggles live in `session_templates.iil_config`, with a **locked policy-floor
rule**: `filler_policy='light'` is the floor and `iil_config` cannot re-enable
disabled tiers. Tier-2 thresholds are locked: default 0.7, moderate 0.85
([app/tasks/normalize.py:1-16](../app/tasks/normalize.py#L1),
[app/config.py:69-72](../app/config.py#L69)). The expansion of the acronym "IIL"
itself is **NOT VERIFIED IN CODE**; it appears only as the config/weight prefix.

## Normalization result
One `normalization_results` row per segment, holding the normalized text, the
template used, validation results, and repair metadata. Conflict key
`(session_id, segment_id)`
([docs/technical/processing-pipeline-technical-spec.md:164-167](../docs/technical/processing-pipeline-technical-spec.md#L164)).

## Discrepancy
A detected difference between the AI-normalized transcript and the raw Google STT
reference, found by an LCS (longest-common-subsequence) diff and stored in
`transcription_discrepancies` (`ai_text`, `stt_text`, `category`). A Gemini
classify task then marks each as `is_meaningful` true/false (meaningful vs.
noise). The editor renders the AI ↔ STT comparison from this
([app/api/discrepancies.py:1-9](../app/api/discrepancies.py#L1),
[app/api/discrepancies.py:29-46](../app/api/discrepancies.py#L29)).

## word_alignment
A per-word mapping between the Gemini transcript index and the matched STT word
(with STT timing and a `match_kind`), used to drive word-level highlighting.
Conflict key `(segment_id, gemini_idx)`
([docs/technical/processing-pipeline-technical-spec.md:170-172](../docs/technical/processing-pipeline-technical-spec.md#L170)).

## Correction (ledger / sequence_number)
An entry in the append-only correction ledger. Every text/slide/speaker edit in
the editor appends a correction row; undo/redo moves a `sequence_number` pointer
rather than deleting rows, so nothing is ever lost
([app/api/corrections.py:883](../app/api/corrections.py#L883),
[app/api/corrections.py:928](../app/api/corrections.py#L928)).

## Split / Merge (structural edit)
A structural segment edit (splitting one segment into two, or merging adjacent
segments), gated by the backend `SPLIT_MERGE_ENABLED` flag. When off the executor
returns 503 `SPLIT_MERGE_DISABLED` and the UI hides the "Split here" menu item +
merge-up keystroke ([app/config.py:125-134](../app/config.py#L125)).

## SOP / SOP stage
"Standard Operating Procedure" — the 8-stage human workflow that runs after a
transcript is `ready`: `prep · copy_draft · medical · copy_final · cms ·
captions · qa · complete`. Forward-only (advance exactly one stage). Each stage
has a default SLA in hours (e.g. medical = 48h)
([app/api/sop.py:24-38](../app/api/sop.py#L24),
[app/api/sop.py:80-90](../app/api/sop.py#L80)). The Dashboard calls this the
"8-stage SOP control layer."

## Stage assignee
The person or group responsible for a session at a given SOP stage. Assignees can
be set per session+stage, and a session type can carry default assignees applied
on init ([app/api/sessions.py:345-498](../app/api/sessions.py#L345),
[app/api/sop.py:60-68](../app/api/sop.py#L60)).

## SLA / overdue (ATTN / OVERDUE)
Each SOP stage has a default service-level deadline in hours; a session past its
stage deadline is "overdue." The Dashboard flags overdue stages with an `ATTN`
badge and the per-user queue shows an `OVERDUE` pill
([docs/product/dashboard-product-spec.md:19](../docs/product/dashboard-product-spec.md#L19),
[docs/product/dashboard-product-spec.md:29](../docs/product/dashboard-product-spec.md#L29)).

## replay_log
A per-session record of the fusion inputs + outputs (with an input hash) enabling
deterministic replay of the fusion step
([docs/technical/processing-pipeline-technical-spec.md:173-174](../docs/technical/processing-pipeline-technical-spec.md#L173)).

## Source (role)
A registered input file for a session. The `sources` table `role` is one of
`video` / `audio` / `audio_enhance` / `slide` / `manifest` / `chat` / `other`
([docs/technical/processing-pipeline-technical-spec.md:132-134](../docs/technical/processing-pipeline-technical-spec.md#L132)).

## R7 scope invariant
The rule that `/v1/gcs/upload-complete` rejects any `gcs_uri` not under
`gs://<bucket>/sessions/<id>/`, preventing a caller from registering media
outside the session's own prefix
([app/services/gcs.py](../app/services/gcs.py),
[docs/technical/processing-pipeline-technical-spec.md:231-232](../docs/technical/processing-pipeline-technical-spec.md#L231)).

## Locked weights
The block of scoring constants (`FUSION_*`, `ALIGN_*`, `IIL_*`, frame/visual
thresholds) pinned by `tests/test_health.py::test_locked_weights_match_audit`;
changing them requires a coordinated config + test + plan update
([app/config.py:51-77](../app/config.py#L51)).

## LEGACY_ADMIN_EMAIL (the bootstrap admin)
The single hardcoded admin identity, `johndean@vin.com`. It is the only
real authorization tier above "logged-in user." Used by `require_admin(user)`
(which always falls back to this email because no caller passes a role) and by a
client-side `adminOnly` route guard
([app/security/roles.py:54](../app/security/roles.py#L54),
[frontend/src/router/index.ts:51](../frontend/src/router/index.ts#L51)).

## CC-Rounds compliance
A Help Center compliance meter shown per help article in the admin Help Editor.
**NOT VERIFIED IN CODE** here as to its exact scoring rules; it appears as a
documented Help Center feature
([docs/product/help-center-product-spec.md:20](../docs/product/help-center-product-spec.md#L20),
[docs/product/help-center-product-spec.md:28](../docs/product/help-center-product-spec.md#L28)).

## Source Verification
- **Files Used:** app/engines/state_machine.py, app/engines/segmenter.py, app/engines/anchor.py, app/engines/fusion.py, app/engines/alignment.py, app/tasks/normalize.py, app/config.py, app/api/discrepancies.py, app/api/corrections.py, app/api/sop.py, app/api/sessions.py, app/security/roles.py, app/services/gcs.py, frontend/src/router/index.ts, docs/technical/processing-pipeline-technical-spec.md, docs/product/dashboard-product-spec.md, docs/product/help-center-product-spec.md
- **Components Used:** none (term definitions)
- **APIs Used:** /v1/sessions/{id}/discrepancies, /v1/sessions/{id}/sop, /v1/gcs/upload-complete (referenced)
- **Database Tables Used:** sessions, segments, words, slides, slide_time_ranges, alignments, normalization_results, transcription_discrepancies, word_alignment, sources, replay_log, corrections, sop_state, session_templates
- **Permission Logic Used:** LEGACY_ADMIN_EMAIL gate (defined as a term)
- **Confidence Score:** High — each term's definition + numeric constants traced to engine/config source; two acronym expansions (IIL, CC-Rounds) flagged NOT VERIFIED IN CODE.
- **Evidence Links:** [app/engines/anchor.py:4-36](../app/engines/anchor.py#L4), [app/engines/fusion.py:1-25](../app/engines/fusion.py#L1), [app/engines/alignment.py:1-25](../app/engines/alignment.py#L1), [app/api/sop.py:24-38](../app/api/sop.py#L24), [app/config.py:51-77](../app/config.py#L51)
