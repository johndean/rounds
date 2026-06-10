# Sessions

## What This Does

The sessions page is the home of every recording in the system. Each row is one
session and shows its code, title and presenter, processing status, review
stage, and a quick count of segments and words. From here you search, filter,
open a session, and — if you are an administrator — delete one.

## Who Can Use It

Anyone signed in can open the sessions page, search and filter it, and open any
session. Deleting a session is restricted to administrators.

## How To Access

Open **Sessions** from the top bar. The page leads with four count tiles — In
Workflow, Processing, Published, and Total — then a search-and-filter toolbar,
then the table of sessions.

## How To Create

You do not create a session on this page. New sessions begin on the upload
page. Click **New upload** (top right of the sessions page) to go there, pick a
recording, and start processing. Once a recording finishes, it appears as a row
in this table.

## How To Edit

You do not edit a session's content from the list. Click a row to open it:

- If the session is still processing, you land on its processing page.
- Otherwise you open the session detail page, where you can edit the title,
  code, files, and stage assignments, and from there open the editor.

To rename or re-tag a session, open it and edit it on the detail page or in the
editor.

## How To Delete

Each row has a small delete control on the right. Deleting is an administrator
action — if your account is not allowed to delete, the action is refused.

When you delete a session, it is a **soft delete**: the session is moved out of
the active list but its data is preserved for thirty days, so it can be
recovered by an administrator within that window. The app asks you to confirm
before deleting. Permanently removing a session (so it cannot be recovered) is a
separate administrator-only step.

## Common Tasks

**Search.** Type in the search box to filter by session title or presenter.
Press Enter to run the search against the full list.

**Filter by state.** Use the chips — **All**, **In Workflow**, **Processing**,
**Published** — to narrow the table. Each chip shows a count.

**Filter by pipeline step or review stage.** If you arrived here by clicking a
step on the dashboard, a labelled filter chip appears showing which AI step or
review stage you are viewing. Click its **×** to clear it and return to the
full list.

**Sort.** Use the **Sort** dropdown (top right of the toolbar) to order by last
updated, code, or title.

**Open a session.** Click anywhere on a row. Processing sessions open their
processing page; everything else opens the session detail page.

**See why a session failed.** If a session's status reads **Failed · why?**,
click it. A panel opens with the failure category, the recorded reason, and a
list of recent status changes, plus a link to open that session's full history.

**Read the status at a glance.** The AI status chip tells you where a session
is: **Processing** (still being prepared and transcribed), **Ready** (finished
and editable), **Published** (completed), or **Failed** (something went wrong —
click for details).

**Export the list.** Click **Export CSV** to start a download of the session
list.

## Troubleshooting

**The list is empty.** If no recordings have been uploaded yet, you will see an
empty state with an **upload one** link. If you have a filter or search active,
the message instead says no sessions match — clear the search box and reset the
chips to **All**.

**A session is stuck on "Processing."** Open it to see its processing page. If
it has actually failed, its row shows **Failed · why?** — click that for the
recorded reason. Recovering a stuck or failed session is an administrator
action.

**I cannot delete a session.** Deleting is restricted to administrators. If you
need a session removed, ask an administrator.

**My search returned nothing.** Search matches the session title and presenter.
Try fewer words, check spelling, and make sure a state chip is not also
filtering the list.

## FAQs

**How do I find a specific session?**
Use the search box to filter by title or presenter, and use the state chips to
narrow by where the session is in the pipeline.

**What does each status mean?**
Processing: still being prepared and transcribed. Ready: finished and the
editor is available. Published: completed. Failed: something went wrong — click
the status for details.

**How do I open the editor for a session?**
Click the row to open the session detail page, then use **Open Editor** there.

**Can I delete a session?**
Only administrators can delete. Deletes are recoverable for thirty days;
permanent removal is a separate administrator step.

**Why did a session fail?**
Click the **Failed · why?** status on its row to see the category, the recorded
reason, and the recent status history.

## Permissions Required

Viewing, searching, filtering, sorting, opening sessions, and exporting the CSV
require only that you are signed in. Deleting a session is restricted to
administrators; restoring a deleted session and permanently removing one are
administrator-only as well.

---

## Source Verification
- **Files Used:** frontend/src/views/SessionsView.vue, frontend/src/services/api.ts (sessions.list / .remove / .failureReason), frontend/src/fixtures/sop_stages.ts, frontend/src/composables/useConfirm.ts, app/api/sessions.py, app/middleware/rate_limit.py, docs/help-center/articles.md, docs/help-center/faq.md, frontend/src/constants/help-content.ts
- **Components Used:** SessionsView.vue, Icon.vue, StageBadge.vue, confirm/toast composables, failure-detail modal
- **APIs Used:** GET /v1/sessions (list + stage/ai/f filters) [frontend/src/views/SessionsView.vue:37](../frontend/src/views/SessionsView.vue#L37); DELETE /v1/sessions/{id} (soft-delete) [app/api/sessions.py:621](../app/api/sessions.py#L621); GET session failure reason [frontend/src/views/SessionsView.vue:133](../frontend/src/views/SessionsView.vue#L133)
- **Database Tables Used:** sessions (rows, status, deleted_at soft-delete) — [app/api/sessions.py:647](../app/api/sessions.py#L647)
- **Permission Logic Used:** JWT presence for list/view; soft-delete gated by SESSION_TRASH_ALLOWED = {johndean@vin.com, carlab@vin.com} ([app/api/sessions.py:52](../app/api/sessions.py#L52), enforced [app/api/sessions.py:630](../app/api/sessions.py#L630)); restore + permanent purge gated by require_admin / LEGACY_ADMIN_EMAIL ([app/api/sessions.py:674](../app/api/sessions.py#L674), [app/api/sessions.py:707](../app/api/sessions.py#L707)).
- **Confidence Score:** High — table, search/filter/sort, status chips, failure modal, and the soft-delete/30-day/confirm behavior are all directly code-verified. The delete control is shown to all users in the UI but the server enforces the SESSION_TRASH_ALLOWED gate; the body describes deletion as an administrator action accordingly.
- **Evidence Links:** [frontend/src/views/SessionsView.vue:106](../frontend/src/views/SessionsView.vue#L106) (delete + 30-day confirm copy), [app/api/sessions.py:624](../app/api/sessions.py#L624) ("data preserved for 30 days"), [app/api/sessions.py:630](../app/api/sessions.py#L630) (delete gate 403), [frontend/src/views/SessionsView.vue:91](../frontend/src/views/SessionsView.vue#L91) (status chip mapping), [frontend/src/views/SessionsView.vue:284](../frontend/src/views/SessionsView.vue#L284) (failure-detail modal)
