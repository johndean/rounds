# Reviewing AI accuracy (Discrepancies)

## What This Does

When a recording is transcribed, two versions of the words exist side by side: the cleaned-up AI transcript and the raw speech-to-text reference. Wherever the two disagree, the system records the difference. The Discrepancies view lines those differences up so you can see, segment by segment, exactly where the AI changed, dropped, or guessed at a word — and decide whether each spot is fine as-is or needs an edit.

The left column shows the AI transcript. The right column shows the raw speech-to-text, marked as read-only. The differing fragments are highlighted in both columns so your eye goes straight to the spot worth checking. A live counter at the top tells you how many differences were found and how many were flagged as meaningful (worth a human look) versus noise.

You do not have to clear every difference. Work through the meaningful ones first; the rest can pass to the next reviewer.

## Who Can Use It

Anyone signed in. There is no separate permission for this view — if you can open a session in the editor, you can review its discrepancies and clear them.

## How To Access

1. Open the session in the editor.
2. In the center pane, click the **Discrepancies** tab (it sits alongside the AI Transcript, STT, and Audit tabs).

The view opens with the **Flagged** filter selected so you start with the segments that actually have a difference attached.

## How To Create

You do not create discrepancies by hand. They are found automatically while the session is processing — the system compares the AI transcript against the raw reference and flags every spot where the two differ. By the time the editor opens, the differences are already there waiting in the Discrepancies tab.

## How To Edit

You have three ways to act on a flagged segment. Each segment row carries the buttons:

- **Edit** — opens the segment for an inline text correction. Use this when the AI got a word wrong. Saving the correction also clears the difference for that segment, so you do not need a separate "resolve" step.
- **Reassign** — pivots to the segment so you can change which speaker it belongs to.
- **Mark OK** — tells the system the AI got it right after all. The flag clears and the segment stops showing up under Flagged.

At the top of the view, three filter buttons control which segments you see:

- **All** — every segment in the session.
- **Flagged** — only segments that have at least one recorded difference.
- **Meaningful** — only the differences the system judged worth a human look (the noise is hidden).

You cannot edit the raw speech-to-text column. It is the reference, kept exactly as the original transcription produced it.

## How To Delete

There is no delete. A difference is a record of what the two transcripts said — it is not something you remove. Instead you **clear** it: Mark OK if the AI was right, or Edit the segment if it was wrong. Either action takes the segment off the flagged list. **Dismiss** is the third option — it clears the flag without changing the text, for when you want to skip a spot without endorsing or editing it.

## Common Tasks

- **Sweep the riskiest spots first.** Open the Discrepancies tab, leave it on **Flagged**, and work top to bottom. Mark OK the ones the AI nailed; Edit the ones it missed.
- **Hide the noise.** Switch to **Meaningful** to drop the trivial differences (spacing, punctuation, filler) and focus only on changes that could affect meaning.
- **Check a medication or a name.** Differences are tagged by category — medication, name, number, date, drift, low confidence, and so on. The tag tells you what kind of spot you are looking at so you can give the clinically risky ones extra attention.
- **Confirm the whole session is clean.** When the Flagged filter shows "All clean — no discrepancies matching this filter," every flag on that filter has been cleared.

## Troubleshooting

- **The right column is empty for a segment.** The raw speech-to-text reference only fills in where the original transcription produced words for that segment. If there are none, the column stays blank — that is expected, not a fault.
- **The count says differences exist but none are showing.** You are probably on the **Flagged** or **Meaningful** filter and the remaining differences fall outside it. Switch to **All** to see everything.
- **A flag will not clear.** Mark OK and Dismiss are disabled for a moment while a previous action on the same segment finishes. Wait a second and try again. If it still fails, you will see an error message with the reason.
- **I cleared a flag by mistake.** Clearing a flag is recorded as a change. Open the **Audit** tab in the editor to see the action, and undo it from there if needed.

## FAQs

**Why is a segment flagged "Low confidence" or "Drift"?**
The system flags a segment when the AI transcript differs from the raw reference, or when the AI's confidence falls below the review threshold. "Drift" specifically means the segment looks misaligned against its slide. Open the segment, confirm the wording, and Mark OK once you are satisfied.

**Do I have to clear every single difference?**
No. Many differences are noise. Handle the meaningful ones; the rest can move on with the session.

**What is the difference between Mark OK and Dismiss?**
Mark OK says "the AI was right." Dismiss says "skip this for now." Both remove the flag from the list. The difference is intent — Mark OK is an endorsement, Dismiss is a pass.

**Can I edit the raw speech-to-text side?**
No. It is read-only on purpose — it is the reference you are checking the AI against.

## Permissions Required

Any signed-in user can open the Discrepancies view and clear flags. There is no admin-only restriction on reviewing or resolving differences.

---

## Source Verification
- **Files Used:** [frontend/src/components/editor/DiscrepanciesPane.vue](../frontend/src/components/editor/DiscrepanciesPane.vue), [app/api/discrepancies.py](../app/api/discrepancies.py), [app/api/corrections.py](../app/api/corrections.py), [frontend/src/views/EditorView.vue](../frontend/src/views/EditorView.vue), [frontend/src/constants/help-content.ts](../frontend/src/constants/help-content.ts), [docs/product/quality-discrepancies-product-spec.md](../docs/product/quality-discrepancies-product-spec.md), [docs/help-center/articles.md](../docs/help-center/articles.md)
- **Components Used:** DiscrepanciesPane.vue (center "Discrepancies" tab in EditorView.vue), SegmentText.vue
- **APIs Used:** `GET /v1/sessions/{session_id}/discrepancies` ([app/api/discrepancies.py:49](../app/api/discrepancies.py#L49)); `POST /v1/sessions/{session_id}/corrections` with `correction_type: mark_ok` for Mark OK / Dismiss ([frontend/src/components/editor/DiscrepanciesPane.vue:62](../frontend/src/components/editor/DiscrepanciesPane.vue#L62), [app/api/corrections.py:63](../app/api/corrections.py#L63))
- **Database Tables Used:** `transcription_discrepancies` (read — [app/api/discrepancies.py:72](../app/api/discrepancies.py#L72)); `correction_ledger` (Mark OK / text_edit auto-close via `CLOSES_DISCREPANCY_TYPES` — [app/api/corrections.py:63](../app/api/corrections.py#L63))
- **Permission Logic Used:** JWT presence only (`CurrentUser`/`_u` dependency on the discrepancies list and corrections endpoints; no admin gate, no role check)
- **Confidence Score:** High — view, endpoint, and resolve path all read directly from code; behavior matches the in-app help content and product spec.
- **Evidence Links:** [DiscrepanciesPane.vue:62-81](../frontend/src/components/editor/DiscrepanciesPane.vue#L62) (Mark OK / Dismiss), [DiscrepanciesPane.vue:256-272](../frontend/src/components/editor/DiscrepanciesPane.vue#L256) (All/Flagged/Meaningful filter), [EditorView.vue:1276](../frontend/src/views/EditorView.vue#L1276) (Discrepancies tab), [discrepancies.py:49-111](../app/api/discrepancies.py#L49) (list endpoint + classification status)
