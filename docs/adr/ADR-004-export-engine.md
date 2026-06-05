# ADR-004 — Export engine: single-source artifact transformer

- **Status:** Accepted
- **Date:** 2026-05-19 (Phase 6p), refined 2026-06-05
- **Deciders:** johndean@vin.com
- **Related:** [BR-016](../BUSINESS_RULES.md#br-016), [BR-017](../BUSINESS_RULES.md#br-017), [ADR-005](./ADR-005-corrections-ledger.md)

## Context

Rounds exports finalized sessions in five formats: `.txt`, `.srt`, `.vtt`, `.docx`, `.html`, plus a `.zip` bundle. Each format has its own rules:

- `.docx` strips filler words ("um", "uh", "er", …) for clinician readability ([BR-016](../BUSINESS_RULES.md#br-016)).
- `.srt` and `.vtt` preserve fillers so captions stay in lock-step with the audio.
- `.txt` strips fillers but keeps speaker turns.
- `.html` is the CMS export — paragraph-shaped, with anchors for chat/poll insertions.
- `.zip` packages all formats plus the original media.

The risk of divergence: five format-specific paths can quietly disagree about what a segment is, how speakers are labeled, what the time bounds of a "chapter" are, etc. A bug fix to the speaker fallback in `.docx` doesn't automatically apply to `.srt`.

## Decision

**A single in-memory session object (`SessionExport`) is built once per export call, then handed to format-specific renderers as a read-only input.**

- `load_session_for_export(session_id)` (`app/engines/artifact_transformer.py`) reads every row needed for any export (segments, words, slides, speakers, chat, polls, corrections) and assembles a single `SessionExport` dataclass.
- Renderers (`to_txt`, `to_srt`, `to_vtt`, `to_docx`, `to_cms_html`, `to_zip`) take the dataclass and emit format-specific bytes.
- Every renderer applies the same TIER1 filler set (`app/iil/normalization.py:37`) — but only `.docx` / `.txt` / `.html` strip, while `.srt` / `.vtt` preserve. The dispatch is at the renderer level, not at the loader level — fillers stay in the source-of-truth dataclass and each renderer decides what to do with them.
- Empty speaker labels resolve to `"(Unknown)"` ([BR-017](../BUSINESS_RULES.md#br-017)).
- The `/v1/sessions/{id}/exports/{format}` route is a thin dispatch over the format string.

## Consequences

- **Positive.**
  - A bug fix to the segment loader propagates to every format on the next export.
  - A new format can be added by writing one renderer function plus one entry in the route's MIME dispatch table.
  - The `.zip` renderer is implemented as "call each other renderer and tar the results" — zero duplication.
- **Negative.**
  - The loader is monolithic — `load_session_for_export` is ~150 LOC and reads from 8 tables. Cold start has noticeable latency (~300ms for a typical session).
  - Adding a new optional field (e.g. "include word-level timings") requires either a parameter on the loader or a second load path. Currently we always load everything.
- **Risks.**
  - The dataclass shape is implicit — a new field on `SessionExport` that one renderer reads but other renderers don't can cause subtle divergence.
  - Format-specific quirks (filler strip [BR-016](../BUSINESS_RULES.md#br-016), speaker fallback [BR-017](../BUSINESS_RULES.md#br-017)) are spread across renderer files — easy to forget to mirror a fix.

## Code locations

- `app/engines/artifact_transformer.py` — loader + all renderers (~560 LOC)
- `app/api/exports.py:38` — `/v1/sessions/{id}/exports/{format}` route + MIME dispatch
- `app/api/exports.py:117` — `/v1/sessions/{id}/captions.vtt` ETag-cached caption route ([ADR-005](./ADR-005-corrections-ledger.md))
- `app/iil/normalization.py:37` — `TIER1_WORDS` filler set

## Alternatives considered

1. **One file per format under `app/engines/exporters/<format>.py`** — viable. Rejected at this scale because the loader would still need to be shared, and the import graph would acquire 5 files where 1 was sufficient.
2. **Use a templating library (Jinja, Mustache) for `.txt` / `.html`** — rejected for the same reason — adds a dependency for marginal benefit at the current renderer complexity.
3. **Pre-bake exports during finalize, store as artifacts, serve from cache** — partially adopted. The `artifacts` table records bytes-per-format with `ON CONFLICT (session_id, kind) DO UPDATE`. The `/v1/sessions/{id}/captions.vtt` route additionally ETag-caches with the corrections sequence number ([ADR-005](./ADR-005-corrections-ledger.md)) so re-renders only happen when corrections change.

## When this ADR should be revisited

- If the renderer file grows beyond ~1000 LOC — splitting becomes leverage.
- If a format requires inputs the dataclass doesn't carry (e.g. real-time stream) — the load-all-once model would no longer fit.
- If pre-baked artifact caching becomes the primary path (today the live render is the primary path), the dispatch may want to invert.
