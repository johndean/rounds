# Reporting & Analytics

The Dashboard view and the audit trail — seeing the state of the pipeline and the
history of changes.

> Developer-facing twin: [../specs/reporting.spec.md](../specs/reporting.spec.md)

## What this gives you

**A live Dashboard.** The top of the Dashboard shows metric cards — AI Sessions,
SOP Sessions, Segments, Words, CMS Published, Improvement requests — each a live
count of one part of the workflow. Click a card to drill into the underlying
list.

**Your Queue.** A personalized shortlist of the sessions where you are the named
stage assignee, so you can jump straight to what needs you.

**Pipeline and workflow views.** The Dashboard shows the AI processing stages and
the eight SOP stages as a row of counts. Click a stage to filter the Sessions
list to just the sessions sitting there. Stages running over their deadline are
flagged for attention.

**The audit trail.** Every change to a session — text edits, speaker
reassignments, chat and poll moves, find-and-replace — is recorded with the user,
the timestamp, and the before/after. The log is append-only: nothing is ever
removed, so it is a complete history.

**The Improvements board.** Patterns the system notices across many sessions
(recurring corrections, speakers that are often misidentified) surface as
suggestions you can accept or retire — see how they accumulate over time.

## Known gaps

- **No historical trend charts** — counts are current-state; the sparkline-style
  visuals are not backed by a time-series yet.
- **No SLA dwell-time history** — you can see that a stage is overdue, not the
  average time sessions spend in each stage.
- **No per-operator productivity metrics.**
- **No cost tracking** — there is no view of AI or storage spend.
- **No exportable reports** — use a screenshot or your browser's print-to-PDF for
  now.
