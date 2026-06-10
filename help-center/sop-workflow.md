# Moving a session through the workflow (SOP)

## What This Does

Once a recording is transcribed, it walks through a fixed sequence of review stages before it is ready to publish. The workflow page is where you see that journey: which stage the session is in right now, who owns it, how long it has been sitting there, and the full history of every stage it has already passed through.

The stages, in order, are:

**Prep → Copy Draft → Medical → Copy Final → CMS → Captions → QA → Complete.**

A session is always in exactly one stage. It moves forward one stage at a time — there is no skipping ahead and no moving backward. Every move is recorded permanently, so you can always reconstruct how a session got to where it is.

## Who Can Use It

Anyone signed in can open the workflow page for a session, advance it, reassign a stage owner, add a note, or record an override. The actions are not locked to a separate "admin" role — if you can open the session, you can act on its workflow.

## How To Access

1. Open the session in the editor.
2. Click **SOP Workflow** (reachable from the editor and from the session's breadcrumb).

You land on a single page with the current stage up top, a row of summary tiles, a clickable stepper showing all eight stages, and detail cards for the selected stage on the left with owner, approvals, and quick actions on the right.

## How To Create

You do not create a workflow by hand. When a recording finishes processing and becomes ready, its workflow is set up automatically and starts at the **Prep** stage with default deadlines already attached. The first time anyone opens the workflow page for a session that somehow has no workflow yet, the page quietly creates one at Prep.

## How To Edit

**Advance to the next stage.** The current stage's detail card has an **Advance** button that moves the session to the next stage in the sequence. You confirm the move in a dialog, and the transition is recorded with your name and the time. You can only advance one stage forward — the button always points at the single next stage.

> The Advance button is gated by the stage's acceptance checks. Those checks currently display as "pending" and do not flip to "passed" on this page, so in normal use the in-page Advance button stays disabled until that check behavior is completed. This is a known limitation of the current build, not a sign that something is wrong with your session.

**Reassign a stage owner.** On the stage owner card, click **Reassign** and enter who should own the stage. You can enter a person's email address, or a group by typing `group:` followed by the group name (for example, `group:QA Group`). The change is recorded.

**Add a note or an override.** The Quick actions card lets you attach a free-text **note** to a stage, or record an **override with a reason** when a stage needs to move along despite an open concern. Both are append-only — once added they are part of the permanent record and are not edited or removed.

**Resolve a check.** Where a stage shows a failing acceptance check, a **Resolve** button records that you cleared it. The resolution is saved to the session's history.

## How To Delete

There is nothing to delete in the workflow, and that is by design. Stage advances, reassignments, notes, and overrides are append-only — each one writes a permanent record. You cannot remove a transition or an annotation. If a stage moved forward by mistake, the correct path is to add an override note explaining the situation and reassign or re-advance as appropriate; the original move stays in the history.

## Common Tasks

- **See where a session stands.** Open the workflow page. The Current Stage tile and the stepper show the stage; the Assigned-to tile shows the owner; the Dwell tile shows how long it has been in the stage.
- **Hand a session to the next reviewer.** Confirm your stage's work is done, then Advance. The next owner picks it up from there.
- **Change who is responsible.** Use Reassign on the stage owner card. Enter an email for a person or `group:NAME` for a team.
- **Explain an unusual decision.** Use "Override with reason" so the reasoning is captured in the permanent history for the next reviewer.
- **Review the full trail.** The Stage Transition History card lists every move; the "Full audit ledger" quick action opens the complete edit-and-action log for the session.

## Troubleshooting

- **The Advance button is greyed out.** Advancing is gated by the stage's acceptance checks, which in the current build stay "pending." This is expected — see the note under How To Edit. Advancement still happens through the normal review process; the in-page button gate is a known limitation.
- **A stage shows "+Nh OVERDUE."** The stage has been sitting longer than its target time. That is a prompt, not a block — it does not stop work, it just flags that the stage is running late.
- **The owner shown looks like a placeholder name or color.** The name and avatar styling come from a built-in display set; only the actual assigned person (or group) is pulled live. If a stage has not been explicitly reassigned, you may see a default display rather than a real teammate.
- **The Ping button did nothing useful.** Ping is not connected to any messaging system in this build — it only shows a notice saying so. Use Reassign and your normal channels to hand work off.

## FAQs

**What are the stages?**
Prep, Copy Draft, Medical, Copy Final, CMS, Captions, QA, Complete. A session moves forward one stage at a time when the owner advances it.

**Can a session skip a stage or go backward?**
No. Moves are forward-only and one step at a time. A request to jump or reverse is rejected.

**What happens when a stage runs past its deadline?**
The stage is marked overdue on the page, and the assignee can receive a deadline reminder email. Reminders are throttled so the same stage will not email the same person more than once in roughly a day's window — you will not be spammed.

**Where do the deadline windows come from?**
Each stage has a default target time built in. Prep is short, Medical review gets the longest window, and Complete is terminal so it never goes overdue. A session can carry its own override of these targets.

**Who is the owner of each stage?**
Whoever was assigned. New sessions arrive with default owners attached; anyone can reassign a stage afterward by entering an email or a `group:NAME`.

## Permissions Required

Any signed-in user can view the workflow and perform every action on it — advance, reassign, annotate, override, and resolve checks. None of these actions are restricted to an admin role in the current build; the only requirement is that you are signed in.

---

## Source Verification
- **Files Used:** [app/api/sop.py](../app/api/sop.py), [frontend/src/views/SopView.vue](../frontend/src/views/SopView.vue), [app/tasks/sop_tasks.py](../app/tasks/sop_tasks.py), [frontend/src/fixtures/sop_stages.ts](../frontend/src/fixtures/sop_stages.ts), [frontend/src/router/index.ts](../frontend/src/router/index.ts), [frontend/src/constants/help-content.ts](../frontend/src/constants/help-content.ts), [docs/product/sop-workflow-product-spec.md](../docs/product/sop-workflow-product-spec.md), [docs/help-center/articles.md](../docs/help-center/articles.md)
- **Components Used:** SopView.vue (route `/e/:id/sop`), StageBadge.vue
- **APIs Used:** `GET /v1/sessions/{id}/sop` ([app/api/sop.py:93](../app/api/sop.py#L93)); `POST /sop/advance` ([app/api/sop.py:113](../app/api/sop.py#L113)); `POST /sop/assign` ([app/api/sop.py:145](../app/api/sop.py#L145)); `PATCH /sop/annotations` for note/override ([app/api/sop.py:196](../app/api/sop.py#L196)); `POST /sop/checks/resolve` ([app/api/sop.py:250](../app/api/sop.py#L250)); `GET /v1/sop/dashboard-summary` ([app/api/sop.py:279](../app/api/sop.py#L279))
- **Database Tables Used:** `sop_state` (current_stage, assignees JSONB, sla_target_hours, metadata.annotations, entered_current_at), `sop_transitions`, `sop_checks`, `audit_events`
- **Permission Logic Used:** JWT presence only (`CurrentUser`/`_u` on all SOP endpoints; no `require_admin`, no role check, no LEGACY_ADMIN_EMAIL gate on this module)
- **Confidence Score:** High — stages, forward-only rule, default SLA values, and the no-admin-gate reality are all read directly from code and corroborated by the product spec.
- **Evidence Links:** [sop.py:24](../app/api/sop.py#L24) (8 stages), [sop.py:80-90](../app/api/sop.py#L80) (forward-only one-step transition), [sop.py:29-38](../app/api/sop.py#L29) (default SLA hours), [SopView.vue:114-139](../frontend/src/views/SopView.vue#L114) (acceptance checks pending → Advance gate disabled), [SopView.vue:273](../frontend/src/views/SopView.vue#L273) (Ping not wired), [sop_tasks.py deadline throttle](../app/tasks/sop_tasks.py) (~23h email throttle per session+stage)
