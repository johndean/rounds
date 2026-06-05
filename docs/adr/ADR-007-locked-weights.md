# ADR-007 — Locked scoring weights: fusion + alignment + IIL

- **Status:** Accepted
- **Date:** 2026-05-17 (bootstrap), refined 2026-06-05
- **Deciders:** johndean@vin.com
- **Related:** [BR-008](../BUSINESS_RULES.md#br-008), [BR-009](../BUSINESS_RULES.md#br-009), [BR-010](../BUSINESS_RULES.md#br-010), [BR-011](../BUSINESS_RULES.md#br-011)

## Context

The pipeline contains three weighted scoring systems:

- **Fusion** — combines visual / anchor / semantic signals into a boundary score ([BR-008](../BUSINESS_RULES.md#br-008)).
- **Alignment** — matches segments to slides via semantic / coverage / temporal / sequential signals ([BR-009](../BUSINESS_RULES.md#br-009)).
- **IIL** — confidence gates Tier 2 normalization ([BR-010](../BUSINESS_RULES.md#br-010)), plus visual-change threshold ([BR-011](../BUSINESS_RULES.md#br-011)).

These weights were tuned during MIC's audit §6 work — months of iteration against a real corpus of clinical rounds. The resulting numbers are not arbitrary; changing them changes where slide boundaries land, which segments match which slide, and what reviewers see in the editor.

The risk: an unauthored drift in any weight — a careless commit, a refactor that "tidies up" the config, a future ADR that doesn't realize the constraint — silently changes every downstream output.

## Decision

**The weights are *locked*: a CI test verifies them against an audit-derived expected table, and any drift fails the build.**

- The weights live in `app/config.py` as `Settings` fields with hardcoded defaults.
- The Pydantic field defaults are the **canonical** values; env-var overrides are accepted by the type system but discouraged (no one overrides them in any environment today).
- A test at `tests/test_health.py::test_locked_weights_match_audit` instantiates `Settings()` and asserts every locked weight matches a hardcoded expected value.
- Any change to a locked weight requires:
  1. Updating the value in `app/config.py`.
  2. Updating the expected value in the test.
  3. A plan document explaining the audit pass that justified the change.
  4. Explicit user authorization at PR time (CLAUDE.md "Backend boundaries" section).
- The locked set comprises: `FRAME_SAMPLE_FPS`, `VISUAL_CHANGE_THRESHOLD`, `ANCHOR_CROSS_VALIDATE_WINDOW`, `SOFT_WINDOW_EXPANSION`, `BOUNDARY_MERGE_WINDOW`, all `FUSION_WEIGHT_*`, `FUSION_BOUNDARY_THRESHOLD`, all `ALIGN_WEIGHT_*`, `ALIGN_SEQUENTIAL_PENALTY`, all `IIL_*`, and the Celery retry triplet.

## Consequences

- **Positive.**
  - Drift is impossible without an explicit two-place edit (config + test).
  - Reviewers reading the codebase see the constraint instantly via comment markers + the test name.
  - Cross-deploy reproducibility — the same session produces the same boundaries across environments.
- **Negative.**
  - Trial-and-error tuning is friction. Every experiment requires editing two files.
  - The "lock" is application-level, not deploy-level — a Railway env-var override would still take effect (no one does this today, but it's possible).
- **Risks.**
  - The expected table in the test is duplicated from `config.py` — manual sync. A future weight added to config but forgotten in the test would be unlocked silently. Documented in the test docstring.
  - Future weights that should be locked but weren't (e.g. someone adds `ALIGN_WEIGHT_NEW_SIGNAL`) wouldn't automatically get into the locked set.

## Code locations

- `app/config.py:42–67` — locked weight defaults (block-comment header: "Processing — LOCKED weights (audit §6)")
- `tests/test_health.py::test_locked_weights_match_audit` — pinning test
- `app/engines/fusion.py` — consumes `FUSION_WEIGHT_*` + `FUSION_BOUNDARY_THRESHOLD`
- `app/engines/alignment.py` — consumes `ALIGN_WEIGHT_*` + `ALIGN_SEQUENTIAL_PENALTY`
- `app/iil/validation.py`, `app/iil/normalization.py` — consume `IIL_TIER2_*`

## Alternatives considered

1. **Hash-pin the config** — emit a hash of all locked values at boot and reject startup if it differs from a constant. Considered; deferred because the test-based approach already catches drift and is easier to diagnose on failure.
2. **Hardcode the values without Pydantic** — would prevent env-var override. Rejected because Pydantic gives field validation + clean docs + consistent shape with the rest of `Settings`.
3. **Move locked values to a separate constants module** — rejected because it would split the config across two import sites and the locked posture is already clear from the inline comment.

## When this ADR should be revisited

- If a new locked weight is added and the test isn't updated in the same PR — the lock failed.
- If a re-tuning audit is run (clinical corpus changes, new IIL tier added) — the test expected values move with the config values.
- If the application grows enough additional Settings fields that maintaining a manual locked list becomes brittle, move to a hash-pin model.
