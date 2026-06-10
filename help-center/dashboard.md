# Dashboard

## What This Does

The dashboard is your home base. It opens when you sign in. The cards across
the top give you live counts of what is in the system right now, a "Your Queue"
strip surfaces the most recent sessions so you can jump straight into one, and
two pipeline strips show where your recordings sit — first in AI processing,
then in the review workflow.

## Who Can Use It

Anyone who is signed in can open the dashboard. Everyone sees the same layout
and the same live counts pulled from the sessions in the system.

## How To Access

The dashboard is the default page after you sign in. You can return to it any
time from the top bar, or by going to the site root — the app sends you to the
dashboard automatically.

## How To Create

The dashboard is a read-only overview — there is nothing to create on it. The
one action it offers is starting new work: click **New upload** in the top
right to go to the upload page and begin a new session.

## How To Edit

There is nothing to edit on the dashboard itself. The counts and lists update
on their own from the underlying sessions. To change anything you see, open the
relevant session and edit it there.

## How To Delete

Nothing is deleted from the dashboard. It only reflects what already exists. To
remove a session, open it from the sessions list (deleting sessions is an
administrator action).

## Common Tasks

**Read the top cards.** Each card is a live count tied to one part of the
workflow. **AI Sessions** is the total number of recordings in the system,
with a quick "ready / processing" breakdown underneath. **SOP Sessions** counts
recordings moving through the review workflow. **Segments** and **Words** are
running totals of how much transcript exists. **CMS Published** counts the
sessions that have been completed.

**Find work that needs you.** The **Your Queue** strip shows the most recent
sessions as cards. Click a card to open it — if it is still being processed you
land on its processing page, otherwise you go straight into the editor.

**See the whole list.** Click **View all** on the Your Queue strip to go to the
full sessions list.

**Read the pipeline strips.** The first strip (AI processing) walks a recording
from upload through transcription, alignment, and on to ready or failed; the
count on each step tells you how many recordings are at that point. The second
strip (review workflow) shows the review stages — Prep, Copy Draft, Medical,
Copy Final, CMS, Captions, QA, Complete — with a count per stage and an
attention badge when a stage has something overdue. Click any step to open the
sessions list filtered to that step or stage.

**Start a new upload.** Click **New upload** (top right) to begin a new
session.

## Troubleshooting

**My counts look stale.** The dashboard loads its numbers when you open it.
Navigate away and back, or refresh the page, to pull the latest counts. If a
number still looks wrong, sign out and back in.

**Some panels say "No data yet" or show a dash.** The lower panels — age
alerts, correction hotspots, storage, jobs queue, and the per-stage timing
grid — show their frame even when there is nothing to report yet. They fill in
as sessions move through the system. An empty panel is not an error.

**Your Queue is empty.** That means there are no recent sessions to show. Click
**upload one** in the empty-state message, or **New upload** at the top, to add
a recording.

**A pipeline step shows zero.** No recordings are at that step right now. The
counts move as sessions progress.

## FAQs

**What do the cards across the top mean?**
Each is a live count of one part of the workflow — total sessions, sessions in
review, segment and word totals, and completed/published sessions.

**How do I find sessions that need my attention?**
Look at Your Queue for the most recent sessions, or click **View all** to open
the full sessions list. Click a pipeline step to filter the list to that step.

**Where do I start a new upload?**
Click **New upload** in the top right of the dashboard.

**Why does a panel say "No data yet"?**
Those panels report derived information that fills in as sessions move through
the system. Until there is something to show, they display their frame with an
empty message.

**Why does the app sometimes say "Slow down"?**
A safety limit protects the processing pipeline from bursts of work. Wait a few
seconds and try again.

## Permissions Required

You only need to be signed in. The dashboard shows the same live counts and the
same panels to every signed-in user; there is no separate administrator-only
view of this page in the app today.

---

## Source Verification
- **Files Used:** frontend/src/views/DashboardView.vue, frontend/src/fixtures/sop_stages.ts, frontend/src/services/api.ts (sessions.list, sop.dashboardSummary), frontend/src/router/index.ts, app/api/sessions.py, app/api/sop.py, docs/help-center/articles.md, docs/help-center/faq.md, frontend/src/constants/help-content.ts
- **Components Used:** DashboardView.vue, Icon.vue, StageBadge.vue, Sparkline.vue
- **APIs Used:** GET /v1/sessions ([frontend/src/views/DashboardView.vue:30](../frontend/src/views/DashboardView.vue#L30)), GET /v1/sop/dashboard-summary ([frontend/src/views/DashboardView.vue:31](../frontend/src/views/DashboardView.vue#L31), [app/api/sop.py](../app/api/sop.py))
- **Database Tables Used:** sessions (counts/queue, via /v1/sessions), sop state summary (via /v1/sop/dashboard-summary)
- **Permission Logic Used:** JWT presence only (router guard [frontend/src/router/index.ts:59](../frontend/src/router/index.ts#L59)); the dashboard has no admin-only branch in code — the "admin" variant in frontend/src/constants/help-content.ts describes widgets (diagnostics strip, role-switcher) NOT PRESENT in DashboardView.vue.
- **Confidence Score:** Medium — the rendered cards, Your Queue, both pipeline strips, and empty/"No data yet" panels are fully code-verified; the help-content.ts admin intro references a diagnostics strip and role-switcher that are NOT IMPLEMENTED IN CODE on this view, so the body documents only the single shared dashboard that ships.
- **Evidence Links:** [frontend/src/views/DashboardView.vue:50](../frontend/src/views/DashboardView.vue#L50) (top KPI cards), [frontend/src/views/DashboardView.vue:59](../frontend/src/views/DashboardView.vue#L59) (Your Queue = first 3 sessions), [frontend/src/views/DashboardView.vue:75](../frontend/src/views/DashboardView.vue#L75) (AI pipeline steps), [frontend/src/views/DashboardView.vue:90](../frontend/src/views/DashboardView.vue#L90) (SOP pipeline + ATTN), [frontend/src/views/DashboardView.vue:305](../frontend/src/views/DashboardView.vue#L305) ("No data yet" panels)
