# Suggesting and tracking improvements

## What This Does

The Improvements page is a shared backlog for change requests about the app itself — product enhancements, bug reports, and operator suggestions. It is the place to write down "this feature should work differently" or "here is something that is broken" so it does not get lost. The page header describes it as a roadmap for product enhancements, bug fixes, and operator requests.

It is a master/detail list: every request shows up as a row with a title, the person who submitted it, a status, a risk level, and a priority. Click a row and a detail panel opens on the right with the full description and a structured action-plan view.

This is a tracker for requests about the app. It is not a feature that watches your editing and proposes corrections — there is no automatic pattern detection here. Each entry exists because a person typed it in.

## Who Can Use It

Anyone signed in. Any user can open the page, file a new request, browse and search the list, and delete a request. The page is gated only by being signed in — there is no separate admin-only access to reach it.

## How To Access

Click **Improvements** in the top bar. The page loads the full list of requests, newest first, and selects the first one so the detail panel has something to show.

## How To Create

1. On the Improvements page, click **Suggest Improvement** (top right).
2. Fill in the form:
   - **Title** (required) — a short summary of the request.
   - **Surface** — which part of the app it concerns, chosen from a list.
   - **Priority** — Low, Medium, High, or Critical.
   - **Description** — the details.
3. Click submit.

The new request appears at the top of the list and is selected for you, and you get a confirmation showing its new id. Your name is attached automatically as the submitter — you do not type it in.

## How To Edit

You can change which request you are looking at, filter the list, and search it:

- **Filter by status** using the tabs across the top: All, Pending, Under Review, Approved, In Progress, Rolled Out, Declined, Archived. Each tab shows a count.
- **Search by title** using the search box; it filters the list as you type.
- **Open a request** by clicking its row; the detail panel shows the full description and a stepped action-plan view (Overview, Requirements, Implementation, Testing, Review).

> The detail panel's planning tools are display-and-draft only in the current build. The "Save Changes," "Regenerate," and the AI-model selector inside the detail panel do not yet write anything back — they show a notice saying so. The reliable, fully-working actions on this page are filing a new request, browsing/filtering/searching, and deleting. Treat the action-plan panel as a structured preview, not an editor.

A request's core text is set when you file it. Beyond filing and deleting, editing the saved record (changing its status, risk, or notes) is not wired into this page yet.

## How To Delete

1. Find the request in the list.
2. Click **Del** at the end of its row.
3. Confirm in the dialog.

The request disappears from the list. Deletion is a soft removal — the record is hidden rather than physically erased — but from your point of view it is gone from the backlog.

## Common Tasks

- **Report a bug or request a change.** Click Suggest Improvement, give it a clear title and description, set a priority, and submit.
- **Find a request someone filed.** Use the search box (title match) or pick a status tab to narrow the list.
- **Check who asked for something.** The submitter's name appears under the title in each row.
- **Read the full details of a request.** Click the row; the description and action-plan view open on the right.
- **Remove a request that is no longer relevant.** Click Del on the row and confirm.

## Troubleshooting

- **Submit did nothing.** A title is required. If the title box is empty you will see a "title required" notice — fill it in and submit again.
- **A status tab shows zero even though requests exist in that state.** Some status tabs use slightly different labels than the stored values, so a few tabs can read 0 while the matching requests sit under All. Use the **All** tab and the search box to find any request reliably.
- **Save Changes / Regenerate in the detail panel did nothing.** Those buttons are not wired to save in the current build — they only show a notice. Your filed request and its description are saved; the action-plan editing is not yet active.
- **The AI Model dropdown does not seem to do anything.** It is a display control only in this build and is not sent anywhere. You can ignore it.

## FAQs

**Is this where the app suggests corrections to my transcripts?**
No. This page is a backlog of change requests about the app, all written by people. It does not watch your editing or propose automatic fixes.

**Who can file a request?**
Any signed-in user.

**Does my name get attached?**
Yes, automatically. The submitter is set to your account when you file — you do not enter it.

**Can I undo a delete?**
The page removes the request from view and does not offer a restore button. Deletion hides the record rather than erasing it outright, but plan as though it is gone; re-file it if you deleted one by mistake.

**Why are the planning steps in the detail panel not saving?**
The action-plan tools (Save Changes, Regenerate, the model picker) are preview-only in this build. Filing, browsing, searching, and deleting are the working actions.

## Permissions Required

Any signed-in user can reach the Improvements page, file a request, browse and search, and delete a request. There is no admin-only gate on the page or on filing and deleting. Saved-record editing (status, risk, notes) is not exposed on this page in the current build for any user.

---

## Source Verification
- **Files Used:** [frontend/src/views/ImprovementsView.vue](../frontend/src/views/ImprovementsView.vue), [app/api/improvements.py](../app/api/improvements.py), [frontend/src/components/improvements/ImprovDetail.vue](../frontend/src/components/improvements/ImprovDetail.vue), [frontend/src/components/overlays/SuggestImprovementModal.vue](../frontend/src/components/overlays/SuggestImprovementModal.vue), [frontend/src/router/index.ts](../frontend/src/router/index.ts), [frontend/src/constants/help-content.ts](../frontend/src/constants/help-content.ts), [docs/product/improvements-product-spec.md](../docs/product/improvements-product-spec.md)
- **Components Used:** ImprovementsView.vue (route `/improvements`), ImprovDetail.vue, SuggestImprovementModal.vue
- **APIs Used:** `GET /v1/improvements` (list — [app/api/improvements.py:76](../app/api/improvements.py#L76)); `POST /v1/improvements` (suggest — [app/api/improvements.py:93](../app/api/improvements.py#L93)); `DELETE /v1/improvements/{id}` (soft delete — [app/api/improvements.py:179](../app/api/improvements.py#L179)). Note: `PUT .../wizard/{step}` and `PATCH .../{id}` exist server-side but are not called by this view ([docs/product/improvements-product-spec.md:87-94](../docs/product/improvements-product-spec.md#L87)).
- **Database Tables Used:** `improvements` (single shared backlog, soft-delete via `deleted_at`); `audit_events` (suggest/delete write rows)
- **Permission Logic Used:** JWT presence only (`CurrentUser`/`_u` on improvements endpoints; route has no `meta.adminOnly`; `submitted_by` is forced to the JWT email — no role check anywhere)
- **Confidence Score:** High — verified the view is a change-request backlog (not pattern detection), that any user can suggest/delete, and that the detail-panel save/regenerate/model controls are unwired. The in-app help seed's "patterns/accept/retire" wording does NOT match the shipped code; this article documents the code.
- **Evidence Links:** [ImprovementsView.vue:94-130](../frontend/src/views/ImprovementsView.vue#L94) (suggest + delete handlers), [ImprovementsView.vue:138-140](../frontend/src/views/ImprovementsView.vue#L138) ("roadmap" header), [improvements.py:103](../app/api/improvements.py#L103) (submitter forced to JWT email), [router/index.ts:39](../frontend/src/router/index.ts#L39) (no adminOnly on `/improvements`), [improvements-product-spec.md:87-94](../docs/product/improvements-product-spec.md#L87) (Save/Regenerate not wired; model selector inert)

> Maintainer flag: `frontend/src/constants/help-content.ts` improvements topics describe "patterns the system noticed" / "accept / dismiss" / "Retire," which the shipped `ImprovementsView.vue` does not implement (it is a Suggest/Delete change-request tracker). This article follows the code; the in-app seed text should be reconciled to match.
