# Corrections API

Router source: [app/api/corrections.py](../../app/api/corrections.py)

Append-only correction ledger backing the editor's Undo/Redo, inline segment edits/reassigns, split/merge structural ops, and the Find/Replace bulk-edit flow. All routes mount under the prefix `/v1/sessions` with tag `corrections` ([corrections.py:45](../../app/api/corrections.py#L45)).

**INVARIANT (from the module docstring):** corrections are APPEND-ONLY. `UPDATE`/`DELETE` on the `correction_ledger` rows is forbidden; undo/redo moves `ledger_pointers.current_pointer` instead of mutating rows ([corrections.py:9-11](../../app/api/corrections.py#L9)). The one exception is `_truncate_redo_tail`, which deletes rows *past* the pointer when a new correction is recorded (the redo branch is abandoned) ([corrections.py:188-198](../../app/api/corrections.py#L188)).

Six `@router` decorators are defined in this file:

| # | Method | Path | Handler | Decorator line |
|---|--------|------|---------|----------------|
| 1 | POST | `/v1/sessions/{session_id}/corrections` | `apply_correction` | [corrections.py:332](../../app/api/corrections.py#L332) |
| 2 | POST | `/v1/sessions/{session_id}/find-replace` | `find_replace` | [corrections.py:653](../../app/api/corrections.py#L653) |
| 3 | GET | `/v1/sessions/{session_id}/corrections` | `list_corrections` | [corrections.py:832](../../app/api/corrections.py#L832) |
| 4 | POST | `/v1/sessions/{session_id}/corrections/undo` | `undo_correction` | [corrections.py:883](../../app/api/corrections.py#L883) |
| 5 | POST | `/v1/sessions/{session_id}/corrections/redo` | `redo_correction` | [corrections.py:928](../../app/api/corrections.py#L928) |
| 6 | GET | `/v1/sessions/{session_id}/review-queue` | `get_review_queue` | [corrections.py:978](../../app/api/corrections.py#L978) |

## Authentication & authorization (applies to every endpoint below)

- **Authentication:** Every handler depends on `CurrentUser` (alias `user`) or `_u` ([corrections.py:40](../../app/api/corrections.py#L40)). This requires a valid HS256 JWT bearer token via `get_current_user`; missing/invalid token → 401 ([app/auth.py:172](../../app/auth.py#L172)).
- **Authorization:** No `LEGACY_ADMIN_EMAIL` / `require_admin` / role check anywhere in this router (grep-confirmed: no matches). **All six routes are JWT-only.** Any authenticated user may call them. Where an actor is recorded, it is `getattr(user, "email", None) or "(unknown)"` ([corrections.py:396](../../app/api/corrections.py#L396), [corrections.py:531](../../app/api/corrections.py#L531), [corrections.py:760](../../app/api/corrections.py#L760)).

## Shared constants

- `ALLOWED_CORRECTION_TYPES` ([corrections.py:49-53](../../app/api/corrections.py#L49)): `slide_reassignment`, `text_edit`, `split`, `merge`, `mark_ok`, `chat_insert`, `chat_edit`, `chat_remove`, `poll_insert`, `poll_remove`, `speaker_reassignment`.
- `CLOSES_DISCREPANCY_TYPES` ([corrections.py:63](../../app/api/corrections.py#L63)): `text_edit`, `mark_ok` (BR-018) — applying one of these auto-resolves an unresolved discrepancy on the segment.

---

## 1. POST `/v1/sessions/{session_id}/corrections`

**Endpoint** [corrections.py:332](../../app/api/corrections.py#L332)
**Method:** POST
**Purpose:** Append a single correction and advance the undo pointer to it. Handles 11 simple correction types plus the two structural ops (`split`, `merge`) on a gated, advisory-locked branch ([corrections.py:339-344](../../app/api/corrections.py#L339)).
**Authentication:** JWT required (`user: CurrentUser`).
**Authorization:** JWT-only. No admin gate.

**Request Schema** — `CorrectionRequest` ([corrections.py:90-112](../../app/api/corrections.py#L90)):

| Field | Type | Notes |
|-------|------|-------|
| `segment_id` | UUID | required |
| `correction_type` | str | required; must be in `ALLOWED_CORRECTION_TYPES` |
| `old_slide_id` | UUID \| null | for `slide_reassignment` |
| `new_slide_id` | UUID \| null | for `slide_reassignment` |
| `old_text` | str \| null | for `text_edit` |
| `new_text` | str \| null | for `text_edit` |
| `action_id` | UUID \| null | client-supplied idempotency / batch key |
| `after_word_index` | int \| null | consulted only for `split`/`merge` ([corrections.py:98-100](../../app/api/corrections.py#L98)) |
| `expected_right_segment_id` | UUID \| null | for `merge` |
| `expected_content_hash` | str \| null | autosave-vs-split race guard for `text_edit` ([corrections.py:104-112](../../app/api/corrections.py#L104)) |

**Response Schema** — varies by branch:

- **Simple correction** ([corrections.py:636-649](../../app/api/corrections.py#L636)): `correction_id`, `sequence_number`, `action_id`, `segment_id`, `correction_type`, `old_slide_id`, `new_slide_id`, `old_text`, `new_text`, `applied_at`, `applied_by`, `resolved_discrepancy_id`.
- **No-op** ([corrections.py:462-469](../../app/api/corrections.py#L462)): `correction_id: null`, `sequence_number` (unchanged pointer), `action_id`, `segment_id`, `correction_type`, `noop: true`.
- **Stale autosave** ([corrections.py:518-525](../../app/api/corrections.py#L518)): same shape as no-op but `stale: true`, `correction_id: null`.
- **Split/merge success** ([corrections.py:444-454](../../app/api/corrections.py#L444)): `correction_id`, `sequence_number`, `action_id`, `segment_id`, `correction_type`, `affected_segment_ids` (list), `deleted_segment_id` (merge only), `applied_at`, `applied_by`.
- **Split/merge dedup replay** ([corrections.py:317-328](../../app/api/corrections.py#L317)): same as success plus `deduped: true` (reconstructed from the cached ledger row).

**Validation Rules**
- `correction_type` must be in `ALLOWED_CORRECTION_TYPES`, else 400 ([corrections.py:345-346](../../app/api/corrections.py#L345)).
- Session must exist (`_session_exists`), else 404 ([corrections.py:350-351](../../app/api/corrections.py#L350)).
- Segment must belong to the session (`_segment_belongs`), else 404 ([corrections.py:352-353](../../app/api/corrections.py#L352)).
- **No-op guard** (`_is_noop_correction`, [corrections.py:74-86](../../app/api/corrections.py#L74)): a `text_edit` with `old_text == new_text`, or a `slide_reassignment` with `old_slide_id == new_slide_id`, returns early with `noop: true` and does **not** truncate the redo tail ([corrections.py:460-469](../../app/api/corrections.py#L460)).
- **split/merge gate:** requires `settings.SPLIT_MERGE_ENABLED` (else 503) and acquires the `(session_id, "split_merge")` advisory lock (else 409). `action_id` dedup happens inside the lock ([corrections.py:360-371](../../app/api/corrections.py#L360)).
- **Stale-autosave guard:** when a `text_edit` ships `expected_content_hash`, the segment write is conditional on the hash still matching; a mismatch is logged, the autosave is dropped (no ledger row, no redo-tail truncation), and `stale: true` is returned ([corrections.py:482-525](../../app/api/corrections.py#L482)).

**Side effects**
- Truncates the redo tail, computes `_next_seq` (serialized via a `FOR UPDATE` lock on `ledger_pointers`, [corrections.py:153-185](../../app/api/corrections.py#L153)), inserts into `correction_ledger`, advances `ledger_pointers.current_pointer`.
- For `text_edit` without `expected_content_hash`, materializes `segments.text` in the same transaction so exports see the autosaved text ([corrections.py:584-596](../../app/api/corrections.py#L584)).
- For `text_edit`/`mark_ok`, marks any unresolved `transcription_discrepancies` row on the segment as resolved with a back-reference ([corrections.py:601-620](../../app/api/corrections.py#L601)).
- Emits best-effort WS events `correction_applied` and (if a discrepancy closed) `discrepancy_resolved` ([corrections.py:624-634](../../app/api/corrections.py#L624)).

**Errors**

| Status | Condition | Detail |
|--------|-----------|--------|
| 401 | missing/invalid JWT | "Could not validate credentials" |
| 400 | invalid `correction_type` | `"Invalid correction_type: ..."` ([corrections.py:346](../../app/api/corrections.py#L346)) |
| 404 | session not found | `"Session ... not found"` ([corrections.py:351](../../app/api/corrections.py#L351)) |
| 404 | segment not in session | `"Segment ... not in session ..."` ([corrections.py:353](../../app/api/corrections.py#L353)) |
| 503 | split/merge disabled | `{"code": "SPLIT_MERGE_DISABLED"}` ([corrections.py:363](../../app/api/corrections.py#L363)) |
| 409 | split/merge advisory lock held | `{"code": "SPLIT_MERGE_BUSY"}` ([corrections.py:367](../../app/api/corrections.py#L367)) |
| 500 | split/merge executor raised | `{"code": "SPLIT_MERGE_EXEC_ERROR", "operation": ..., "error_class": ..., "error_message": ...}` ([corrections.py:429-437](../../app/api/corrections.py#L429)) |
| 4xx | structured error raised by split/merge executor | propagated unchanged ([corrections.py:417-419](../../app/api/corrections.py#L417)) |

**Example**
```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"segment_id":"<SEG>","correction_type":"text_edit","old_text":"teh","new_text":"the"}' \
  https://rounds.vin/v1/sessions/<SESSION_ID>/corrections
```

**Related Screens:** Editor Undo/Redo, inline segment edit / slide-reassign / speaker save, split/merge segment actions.
**Related Tables:** `correction_ledger`, `ledger_pointers`, `sessions`, `segments`, `transcription_discrepancies`. Split/merge delegate to `app/services/segment_split` and `app/services/segment_merge`; advisory lock via `app/services/db_locks`.

---

## 2. POST `/v1/sessions/{session_id}/find-replace`

**Endpoint** [corrections.py:653](../../app/api/corrections.py#L653)
**Method:** POST
**Purpose:** Literal-substring find/replace across all segments in the session. Replaces ALL occurrences, writes one `text_edit` correction per affected segment sharing one `action_id` (so undo reverses them as a single batch). `dry_run=true` returns a preview without writing ([corrections.py:660-669](../../app/api/corrections.py#L660)).
**Authentication:** JWT required (`user: CurrentUser`).
**Authorization:** JWT-only. No admin gate.

**Request Schema** — `FindReplaceRequest` ([corrections.py:115-119](../../app/api/corrections.py#L115)):

| Field | Type | Constraint |
|-------|------|-----------|
| `find` | str | required, `min_length=1`, `max_length=512` |
| `replace` | str | default `""`, `max_length=512` |
| `case_sensitive` | bool | default `false` |
| `dry_run` | bool | default `false` |

**Response Schema** ([corrections.py:742-754](../../app/api/corrections.py#L742) for preview, [corrections.py:817-828](../../app/api/corrections.py#L817) for applied):

| Field | Type | Notes |
|-------|------|-------|
| `session_id` | str | |
| `find` | str | echo |
| `replace` | str | echo |
| `case_sensitive` | bool | echo |
| `matches` | list | each: `segment_id`, `old_text`, `new_text`, `match_count` |
| `total_matches` | int | |
| `segment_count` | int | number of affected segments |
| `applied` | bool | `false` for dry_run or no matches; `true` after write |
| `action_id` | str \| null | shared batch id when applied; `null` otherwise |
| `corrections` | list | inserted ledger rows when applied; `[]` otherwise |

**Validation Rules**
- Session must exist, else 404 ([corrections.py:671-672](../../app/api/corrections.py#L671)).
- Effective text per segment uses the same 3-layer precedence as the segment list: user `text_edit` ≤ pointer → `normalized_text` → `segments.text` ([corrections.py:676-726](../../app/api/corrections.py#L676)).
- Matching uses `re.escape(find)` (literal substring, not regex), with `re.IGNORECASE` unless `case_sensitive` ([corrections.py:720-721](../../app/api/corrections.py#L720)).
- `dry_run=true` OR zero matches → returns preview with `applied: false`, `action_id: null`, no DB writes ([corrections.py:742-754](../../app/api/corrections.py#L742)).

**Errors**

| Status | Condition | Detail |
|--------|-----------|--------|
| 401 | missing/invalid JWT | "Could not validate credentials" |
| 404 | session not found | `"Session ... not found"` ([corrections.py:672](../../app/api/corrections.py#L672)) |
| 422 | `find` empty / over 512 chars, `replace` over 512 | Pydantic Field rejection |

**Example**
```bash
# Dry run preview
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"find":"canine","replace":"dog","dry_run":true}' \
  https://rounds.vin/v1/sessions/<SESSION_ID>/find-replace
```

**Related Screens:** Editor Find/Replace modal (FindReplaceModal).
**Related Tables:** `correction_ledger`, `ledger_pointers`, `sessions`, `segments`, `normalization_results` (optional).

---

## 3. GET `/v1/sessions/{session_id}/corrections`

**Endpoint** [corrections.py:832](../../app/api/corrections.py#L832)
**Method:** GET
**Purpose:** Return the full correction log for the session plus the current pointer; each row is flagged `active` if its `sequence_number <= current_pointer` ([corrections.py:859-879](../../app/api/corrections.py#L859)).
**Authentication:** JWT required (`_u: CurrentUser`).
**Authorization:** JWT-only. No admin gate.

**Request Schema** — path parameter `session_id: UUID`; no body.

**Response Schema** ([corrections.py:859-879](../../app/api/corrections.py#L859)):
- `session_id` (str), `current_pointer` (int; `-1` if no pointer row), `corrections` (list).
- Each correction: `correction_id`, `sequence_number`, `action_id`, `segment_id`, `correction_type`, `old_slide_id`, `new_slide_id`, `old_text`, `new_text`, `applied_at`, `applied_by`, `active` (bool).

**Validation Rules**
- No payload. Does not 404 on unknown session — returns an empty `corrections` list and `current_pointer: -1`.

**Errors**
- 401 — missing/invalid JWT.

**Example**
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  https://rounds.vin/v1/sessions/<SESSION_ID>/corrections
```

**Related Screens:** Editor undo/redo history surface.
**Related Tables:** `correction_ledger`, `ledger_pointers`.

---

## 4. POST `/v1/sessions/{session_id}/corrections/undo`

**Endpoint** [corrections.py:883](../../app/api/corrections.py#L883)
**Method:** POST
**Purpose:** Decrement the ledger pointer by 1. Before moving the pointer, inverts any `split`/`merge` corrections between `new_ptr+1` and the current pointer (newest-to-oldest), then materializes `segments.text` to the new pointer. Held under the `split_merge` advisory lock ([corrections.py:889-922](../../app/api/corrections.py#L889)).
**Authentication:** JWT required (`_u: CurrentUser`).
**Authorization:** JWT-only. No admin gate.

**Request Schema** — path parameter `session_id: UUID`; no body.

**Response Schema**
- When nothing to undo (pointer already `< 0`): `{"session_id", "pointer": -1, "action": "nothing_to_undo"}` ([corrections.py:887-888](../../app/api/corrections.py#L887)).
- Otherwise: `{"session_id", "pointer": <new_ptr>}` ([corrections.py:924](../../app/api/corrections.py#L924)).

**Validation Rules**
- Pointer is upserted via `_ensure_pointer` first ([corrections.py:886](../../app/api/corrections.py#L886)).
- Structural inverse replay handled by `app/services/segment_inverse.apply_inverse_for_correction` ([corrections.py:910-911](../../app/api/corrections.py#L910)).

**Errors**

| Status | Condition | Detail |
|--------|-----------|--------|
| 401 | missing/invalid JWT | "Could not validate credentials" |
| 409 | `split_merge` advisory lock held | `{"code": "SPLIT_MERGE_BUSY"}` ([corrections.py:898-899](../../app/api/corrections.py#L898)) |

Emits a best-effort WS `correction_applied` event with `action_id: "undo"` ([corrections.py:923](../../app/api/corrections.py#L923)).

**Example**
```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  https://rounds.vin/v1/sessions/<SESSION_ID>/corrections/undo
```

**Related Screens:** Editor Undo button.
**Related Tables:** `correction_ledger`, `ledger_pointers`, `segments`. Inverse via `app/services/segment_inverse`; lock via `app/services/db_locks`.

---

## 5. POST `/v1/sessions/{session_id}/corrections/redo`

**Endpoint** [corrections.py:928](../../app/api/corrections.py#L928)
**Method:** POST
**Purpose:** Increment the ledger pointer by 1. Re-applies any `split`/`merge` corrections between `current_ptr+1` and `new_ptr` (oldest-first), then materializes `segments.text`. Held under the `split_merge` advisory lock ([corrections.py:942-972](../../app/api/corrections.py#L942)).
**Authentication:** JWT required (`_u: CurrentUser`).
**Authorization:** JWT-only. No admin gate.

**Request Schema** — path parameter `session_id: UUID`; no body.

**Response Schema**
- When nothing to redo (pointer already at max sequence): `{"session_id", "pointer": <current_ptr>, "action": "nothing_to_redo"}` ([corrections.py:940-941](../../app/api/corrections.py#L940)).
- Otherwise: `{"session_id", "pointer": <new_ptr>}` ([corrections.py:974](../../app/api/corrections.py#L974)).

**Validation Rules**
- `max_seq` is computed as `MAX(sequence_number)` of the ledger; `-1` if empty ([corrections.py:932-938](../../app/api/corrections.py#L932)).
- Forward replay via `app/services/segment_inverse.apply_forward_for_correction` ([corrections.py:960-961](../../app/api/corrections.py#L960)).

**Errors**

| Status | Condition | Detail |
|--------|-----------|--------|
| 401 | missing/invalid JWT | "Could not validate credentials" |
| 409 | `split_merge` advisory lock held | `{"code": "SPLIT_MERGE_BUSY"}` ([corrections.py:948-949](../../app/api/corrections.py#L948)) |

Emits a best-effort WS `correction_applied` event with `action_id: "redo"` ([corrections.py:973](../../app/api/corrections.py#L973)).

**Example**
```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  https://rounds.vin/v1/sessions/<SESSION_ID>/corrections/redo
```

**Related Screens:** Editor Redo button.
**Related Tables:** `correction_ledger`, `ledger_pointers`, `segments`. Forward replay via `app/services/segment_inverse`; lock via `app/services/db_locks`.

---

## 6. GET `/v1/sessions/{session_id}/review-queue`

**Endpoint** [corrections.py:978](../../app/api/corrections.py#L978)
**Method:** GET
**Purpose:** Return alignment rows in `uncertain` or `review` status, ordered by a priority score (BR-006) so the editor's "next discrepancy" cursor surfaces the worst cases first ([corrections.py:979-981](../../app/api/corrections.py#L979)).
**Authentication:** JWT required (`_u: CurrentUser`).
**Authorization:** JWT-only. No admin gate.

**Request Schema** — path parameter `session_id: UUID`; no body.

**Response Schema** ([corrections.py:1017-1033](../../app/api/corrections.py#L1017)):
- `session_id` (str), `count` (int), `items` (list).
- Each item: `segment_id`, `alignment_id`, `status`, `confidence` (float \| null), `drift_flag` (bool), `uncertain_flag` (bool), `slide_id` (str \| null), `priority_score` (int).

**Validation Rules / scoring (BR-006)** ([corrections.py:1005-1013](../../app/api/corrections.py#L1005)):
- Only rows with `status IN ('uncertain', 'review')` are selected ([corrections.py:991-992](../../app/api/corrections.py#L991)).
- Priority weights (additive): drift + no slide `+100`; uncertain + no slide `+90`; confidence < 0.4 `+70`; drift `+50`; status == review `+40`; confidence < 0.6 `+20`. Rows sorted descending by score.

**Errors**
- 401 — missing/invalid JWT. (No 404; an unknown session yields an empty list.)

**Example**
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  https://rounds.vin/v1/sessions/<SESSION_ID>/review-queue
```

**Related Screens:** Editor Discrepancies tab / "next discrepancy" cursor.
**Related Tables:** `alignments`.

---

## Source Verification
- **Files Used:** [app/api/corrections.py](../../app/api/corrections.py), [app/auth.py](../../app/auth.py)
- **Components Used:** none (frontend FindReplaceModal / EditorView referenced only in code comments, not read)
- **APIs Used:** `POST /v1/sessions/{id}/corrections`, `POST /v1/sessions/{id}/find-replace`, `GET /v1/sessions/{id}/corrections`, `POST /v1/sessions/{id}/corrections/undo`, `POST /v1/sessions/{id}/corrections/redo`, `GET /v1/sessions/{id}/review-queue`
- **Database Tables Used:** `correction_ledger`, `ledger_pointers`, `sessions`, `segments`, `transcription_discrepancies`, `alignments`, `normalization_results` (optional)
- **Permission Logic Used:** JWT presence only (`CurrentUser` → `get_current_user`). No `LEGACY_ADMIN_EMAIL` / `require_admin` gate in this router (grep-confirmed: no matches).
- **Confidence Score:** High — schemas, branches, error codes, and the BR-006 scoring all read directly from the router source.
- **Evidence Links:** decorators at [corrections.py:332](../../app/api/corrections.py#L332), [corrections.py:653](../../app/api/corrections.py#L653), [corrections.py:832](../../app/api/corrections.py#L832), [corrections.py:883](../../app/api/corrections.py#L883), [corrections.py:928](../../app/api/corrections.py#L928), [corrections.py:978](../../app/api/corrections.py#L978); schemas at [corrections.py:90](../../app/api/corrections.py#L90), [corrections.py:115](../../app/api/corrections.py#L115); auth at [app/auth.py:172](../../app/auth.py#L172).
