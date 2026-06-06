# EditorView.vue — Zero-Risk Cleanup Plan

- **Date:** 2026-06-06
- **Author:** johndean@vin.com (+ Claude Opus 4.7)
- **Target:** [`frontend/src/views/EditorView.vue`](../../frontend/src/views/EditorView.vue) — 1408 LOC, the editor's top-level SFC.
- **Constraint:** Zero feature loss. Zero behavior change. The React JSX at [`docs/port-source/editor.jsx`](../port-source/editor.jsx) remains SSOT for layout, class names, and `data-test-id`s — **no template structural change** in this plan.

## 1. Why this plan exists

After today's Phase 3.5+4 work landed (`083f8f9` → `38ce2d5` → `402ef9a` → `d2a29aa` → `ecef8d2`), the IDE reported ~29 style/quality warnings on `EditorView.vue`. They are all pre-existing — none introduced by today's commits. None are blocking; none affect runtime behavior.

This plan inventories what is actually verifiable in the file, classifies each item by risk, and orders them so each phase ships its own commit and is independently revertible. **No template change. No behavior change. No surface change for the user.**

## 2. What's actually in the file (verified grep)

| # | Category | Locations (line numbers) | Count |
|---|---|---|---|
| A1 | `window.addEventListener` / `window.removeEventListener` (DOM globals) | 540, 541, 544, 545, 553, 554, 557, 558, 1008, 1009 | 10 |
| A2 | `parseInt(...)` global builtin (SonarLint S7773 prefers `Number.parseInt`) | 530, 531 | 2 |
| B1 | Duplicate import path `@/services/http` (lines 55, 56 both import from the same module) | 55, 56 | 1 |
| C1 | Multiple `onMounted` calls in same `<script setup>` | 359, 424, 952, 1008 | 4 |
| C2 | Multiple `onUnmounted` calls | 360, 953, 1009 | 3 |
| D1 | `load()` function — 11-endpoint Promise.all + 3 inline `interface` declarations + 4 shape adapters | 153–316 (~165 LOC) | 1 hotspot |
| D2 | Nested ternary in `confidence` mapping in load() | 209 | 1 |
| E1 | `_inferAnchor` function defined inside `load()` (closure over local maps) | 258–269 | 1 |
| F1 | `:anchors-by-segment="anchorsBySegment as any"` (untyped cast in template) | 1241 | 1 |

The "29 warnings" reported by the IDE likely also includes:
- ~3–4 nullish-coalescing nits (`||` where `??` is safer for `0`/`''` falsy operands)
- ~2–3 prefer-`const` / prefer-`readonly` minors
- Style preferences (e.g. single-line vs multi-line ternary)

**Before executing Phase 3, the actual 29-item list should be captured** from the IDE (Cursor / VS Code "Problems" pane, filter to `EditorView.vue`) and pasted into the PR description so we can confirm we addressed every flag, not just the ones I can reproduce with grep.

## 3. Critical invariants this plan WILL NOT touch

These are load-bearing — changing any of them risks breaking the editor:

1. **Template structure, class names, `data-test-id` attributes** — SSOT is React JSX per CLAUDE.md.
2. **`load()` Promise.all ordering and destructuring** — the result tuple `[s, sg, sl, sp, ch, po, di, co, wd, pc, al]` is positional; reordering is a regression.
3. **`_trackLoad` semantics** — every fetch must remain wrapped so per-stage `loadStages` flip `pending → done | error` and the loadbar keeps rendering.
4. **The skeleton gate** at line 1061 (`loadStages.segments === 'pending' && SEGMENTS.length === 0`) — just fixed today in `ecef8d2`. Stays.
5. **Active-segment binary search** (lines 457–480) — MIC parity port. Don't "simplify" — the gap-fallback comments document subtle correctness.
6. **Multiple `onMounted` / `onUnmounted` blocks** — Vue 3 allows them; collapsing into one can change execution order if not done literally. Keep one block per responsibility; do not reorder lifecycle work.
7. **`useSessionLock` / `useAutosave` / `useEditorPersistence` wiring** — the persistence layer's TDZ ordering hazard is documented at line 408. Don't reorder.

## 4. Three-phase cleanup

Each phase is its own commit. Each runs `vue-tsc --noEmit` + `npm run build` + a manual smoke (open an existing session in `/e/:id`, hard-refresh, verify segments render).

---

### Phase 1 — Mechanical renames (zero risk, ~10 min)

**Scope: pure text substitutions. No behavior change. No logic change.**

| Edit | Before | After | Risk |
|---|---|---|---|
| Line 55–56 | two `import` statements from `@/services/http` | one combined `import { ApiError, http } from '@/services/http';` | none — identical resolution |
| Line 530 | `parseInt(localStorage.getItem('mic_left_w')  \|\| '320') \|\| 320` | `Number.parseInt(localStorage.getItem('mic_left_w')  ?? '320', 10) \|\| 320` | none — `Number.parseInt === parseInt`; explicit radix is harmless |
| Line 531 | same for `mic_right_w` / 360 | same shape | none |
| Lines 540, 541, 544, 545, 553, 554, 557, 558 | `window.addEventListener` / `removeEventListener` | `globalThis.addEventListener` / `removeEventListener` | none in SPA — `globalThis === window` in browser |
| Lines 1008, 1009 | same | same | none |

**Verification:**
- `npm run typecheck` clean
- `npm run build` clean
- Open `/e/<existing-session-id>`, drag left and right resizers, verify column widths persist after refresh
- Press `J`, `K`, `L`, `Cmd+Z`, `Cmd+F` and confirm keybindings still fire

**Commit:** `refactor(editor): mechanical lint cleanups — globalThis, Number.parseInt, merge http imports`

**Rollback:** `git revert <sha>` is trivial; no semantic change to revert against.

---

### Phase 2 — Hoist inline types out of `load()` (low risk, ~20 min)

**Scope: move 3 `interface` declarations from inside `load()` to module-top. No call-site change.**

Three interfaces are declared *inside* `load()` today:

- `interface ApiChat` (line 227)
- `interface ApiPollOption` (line 243)
- `interface ApiPoll` (line 244–249)

These force re-parsing on every `load()` invocation (cheap, but real) and bury type definitions in business logic. Hoisting them to the top-level type section (near line 121 where `LoadStageState`/`LoadStageKey` live) makes `load()` ~15 LOC shorter and makes the types referenceable from a future composable extract.

Also hoist the `_inferAnchor` helper out of `load()` into a top-level function that takes its dependencies as arguments. It's a 12-line function with no closure requirement that can't be satisfied by parameter-passing.

```ts
// Hoisted (after the existing LoadStageKey/_initialStages block):
interface ApiChat { id: string; author: string; body: string; sent_at_ms: number; anchor_segment: string | null; placed: boolean }
interface ApiPollOption { id: string; label: string; seq: number; votes: number }
interface ApiPoll {
  id: string; question: string; status: 'open' | 'closed';
  opened_at_ms: number; closed_at_ms: number | null;
  total_votes: number; anchor_segment: string | null; placed: boolean;
  options: ApiPollOption[]; metadata?: { slide_n?: number };
}

function _inferAnchor(
  p: ApiPoll,
  slidesByIndex: Map<number, string>,
  firstSegBySlide: Map<string, string>,
): string {
  if (p.anchor_segment) return p.anchor_segment;
  const slideN = p.metadata?.slide_n;
  if (typeof slideN !== 'number') return '';
  const slideId = slidesByIndex.get(slideN);
  if (!slideId) return '';
  return firstSegBySlide.get(slideId) ?? '';
}
```

Call sites inside `load()` pass `slidesByIndex` and `firstSegBySlide` explicitly. The early-return refactor of `_inferAnchor` (single-exit → guard clauses) drops cognitive complexity without changing the truth table — verify with a small unit table in the PR description.

**Verification:**
- `npm run typecheck` clean
- `npm run build` clean
- Open a session whose polls had `metadata.slide_n` set but `anchor_segment` null. Confirm the poll lands on the first segment of that slide (this is the polls auto-place behavior `_inferAnchor` exists to provide).
- Open a session whose polls have `anchor_segment` set. Confirm anchors are unchanged.

**Commit:** `refactor(editor): hoist Api{Chat,Poll,PollOption} interfaces + _inferAnchor out of load()`

**Rollback:** trivial — paste the hoisted definitions back into `load()`.

---

### Phase 3 — Extract `load()`'s shape adapters (moderate care, ~45 min, gated)

**Scope: extract the 4 shape-adapters from inside `load()` into top-level named functions. `load()` becomes ~50 LOC instead of ~165, but executes the exact same steps in the exact same order.**

This is the only phase that touches `load()` itself. Approach is mechanical: identify each adapter block, extract it as a pure function, replace the inline block with a call.

| Adapter | Lines today | Extracted name | Pure / impure |
|---|---|---|---|
| Segment-row → editor `Segment` | 196–217 | `_adaptSegments(rows, speakersById)` | pure |
| Slide-row → editor `Slide` | 218–223 | `_adaptSlides(rows)` | pure |
| ApiChat → editor `ChatMessage` | 228–235 | `_adaptChat(rows)` | pure |
| ApiPoll → editor `Poll` | 270–279 | `_adaptPolls(rows, slidesByIndex, firstSegBySlide)` | pure |
| Words grouping | 296–302 | `_groupWordsBySegment(rows)` | pure |
| Alignment envelope unwrap | 307–311 | `_unwrapAlignment(envelope)` | pure |

After extraction, `load()`'s body becomes a sequence of:

```ts
session.value = s;
pipelineCfg.value = pc;
if (s?.duration_sec) TOTAL_DURATION.value = s.duration_sec;
void _fetchMediaUrl();  // existing media block extracted too
SPEAKERS_API.value = sp as ApiSpeaker[];
const speakersById = _indexSpeakers(SPEAKERS_API.value);
SEGMENTS.value = _adaptSegments(sg, speakersById);
SLIDES.value = _adaptSlides(sl);
CHAT.value = _adaptChat(ch);
const { slidesByIndex, firstSegBySlide } = _buildSlideAnchorIndex(SLIDES.value, SEGMENTS.value);
POLLS.value = _adaptPolls(po, slidesByIndex, firstSegBySlide);
placements.value = { ...placements.value, ..._initialPlacements(CHAT.value, POLLS.value) };
DISCREPANCIES.value = _unwrapDiscrepancies(di);
CORRECTIONS.value = co;
WORDS_BY_SEGMENT.value = _groupWordsBySegment(wd);
ALIGNMENT_BY_SEGMENT.value = _unwrapAlignment(al);
```

**Risk surface (each must be tested):**
1. The segment adapter at lines 196–217 maps `row.confidence` to `'low' | 'normal'` via a nested ternary at line 209. The extract MUST preserve this — write it as `_segmentConfidence(row.confidence)` returning the same literal union.
2. The polls anchor inference depends on the order: `_buildSlideAnchorIndex` must run after `_adaptSlides` AND `_adaptSegments` because it walks both. The new code preserves this ordering — but it's the one ordering invariant a reviewer must verify.
3. Optimistic placement merge at line 283–286 must run AFTER `_adaptChat` and `_adaptPolls` because it reads their results. Preserved.

**Verification (this is the test surface for the whole plan):**
- `npm run typecheck` clean
- `npm run build` clean
- Open a fresh session in the editor. Confirm:
  - Segments render with correct speaker chips
  - Slides render with correct titles + indexes
  - Chat anchors land on their segments
  - Polls with `metadata.slide_n` land on the first segment of that slide
  - STT pane shows real Google STT words
  - L2 alignment-driven word highlight tracks playback
  - Discrepancies tab populates with the right count
  - Audit tab populates with correction rows
- Open an in-flight session (status `processing`). Confirm:
  - Skeleton shows ONLY while `loadStages.segments === 'pending'`
  - Per-stage loadbar fills as endpoints settle
  - One stage erroring leaves the rest functional (kill an endpoint mid-load to test)
- Re-test the four event paths that re-call `load()`: WS `timeline_ready`, undo, redo, find/replace apply.

**Commit:** `refactor(editor): extract load()'s shape adapters into named pure functions`

**Rollback:** the adapters are pure functions; inlining them back is a mechanical undo. The PR diff should be split as one commit per adapter so a reviewer can revert any single one if a regression surfaces.

---

## 5. Explicitly OUT of scope

These look like style hits but each carries real risk for the value they buy. **Defer.**

| Item | Why deferred |
|---|---|
| Consolidating the 3 `onMounted` / 3 `onUnmounted` blocks into single hooks | Lifecycle ordering already works; collapsing risks subtle re-ordering of `wsConnect()` vs `persistence.restore()` vs `keydown` listener registration. Multi-hook is a Vue-3-approved pattern. |
| Removing `_inferAnchor`'s defensive fallbacks | Each fallback (no `metadata`, no `slide_n`, no matching slide, no first segment) is reached in production by sessions of varying completeness. |
| Adding a proper type for the template `:anchors-by-segment="anchorsBySegment as any"` cast | TranscriptPane's prop typing was loosened during the Phase 4 split/merge wiring; tightening it requires aligning the AnchorEntry interface between two SFCs — own PR. |
| Rewriting `flagCounts` to one `.reduce()` | The current dual-loop form mirrors the React source; rewriting diverges from JSX SSOT for legibility we don't need. |
| Memoizing `activeWordIdx`'s `seg.text.split(/\s+/)` | Runs O(words-in-active-segment) per tick — ~10 µs in practice. Not a real perf concern. |
| Rewriting the binary-search `activeSegment` computed | MIC-parity port; subtle correctness. Don't touch. |
| Splitting `EditorView.vue` into smaller views | This is the right long-term move (the file does too much), but it's a multi-day refactor, not a zero-risk cleanup. |

## 6. Verification matrix

| Phase | typecheck | build | manual editor smoke | manual data smoke |
|---|---|---|---|---|
| 1 | ✓ | ✓ | column resizers + keybindings | — |
| 2 | ✓ | ✓ | open session, polls land on slides | poll with slide_n only |
| 3 | ✓ | ✓ | every tab loads, undo/redo/find work | fresh session + in-flight session |

After all three phases, re-run the IDE's Problems pane on `EditorView.vue` and confirm the count drops from ~29 to <5. Any remaining items get listed in a Phase-4 follow-up issue (not this plan).

## 7. Total effort + sequencing

| Phase | Time | Risk | Reverts cleanly? |
|---|---|---|---|
| 1 | ~10 min | none | yes |
| 2 | ~20 min | low | yes |
| 3 | ~45 min | moderate (load path) | yes, per-adapter |

**~75 min total** with verification. Phases 1 and 2 can ship today. Phase 3 should ship in its own PR with the actual IDE warnings list pasted into the description so the reviewer can spot-check that each pre-existing warning is now gone.

## 8. What this plan deliberately does NOT promise

- **No "fix all 29 warnings" guarantee.** I can verify ~17 from the file directly; the remaining ~12 are inferred from the IDE category buckets you mentioned (globalThis, Number.parseInt, duplicate imports, cognitive complexity). The actual list must be captured from the IDE before Phase 3 ships.
- **No performance gain claim.** This is a legibility + lint-cleanliness pass. The hot paths (`activeSegment` binary search, `visibleSegments` filter, `anchorsBySegment` map build) are untouched.
- **No new tests.** This is a refactor under existing behavior; if Phase 3's extracted adapters drift, the existing Playwright smoke + manual verification catches it. Unit tests for `_adaptSegments` et al. are a follow-up if anyone reaches for them — but they aren't required for zero-risk cleanup.

---

*Awaiting approval before executing any phase.*
