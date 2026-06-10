# Troubleshooting Library — rounds.vin

Consolidated troubleshooting for everyone who uses rounds.vin, gathered from the
per-feature help articles into one place. Symptoms are in user language; each
entry says what to check and who can fix it.

> For the per-feature deep dives see the individual articles in this folder. For
> the known feature gaps behind some of these, see `docs/gap-analysis.md`.

---

## Sign-in & sessions

**"My password doesn't work."**
Contact your admin to set a new initial password. Five failed attempts in fifteen
minutes briefly locks the account — wait it out, then try the new password.

**"I got signed out / the app says I'm not authenticated."**
Your login token expired (sessions last up to ~8 hours of a working day). Sign in
again; you'll return to where you were.

**"The app says 'Slow down' / I see a rate-limit message."**
A safety limit caps how much pipeline work one user can trigger at once. Wait a
few seconds and retry. If it persists after a create-then-delete cycle, an admin
can clear stuck slots.

---

## Upload & processing

**"My upload is stuck at 100%."**
Give it a moment — ingest starts right after the transfer. If it sits past five
minutes, refresh and re-upload. If it still hangs, an admin can re-ingest. (There
is no manual pause/resume.)

**"Processing failed."**
Open the session to see the failure reason. Most failures are transient (an AI
quota cap, a network blip). An admin can re-ingest with one click — re-runs are
safe to repeat.

**"Processing is taking a long time."**
A typical hour of video takes ~10–15 minutes. AI Mode is slower than Default Mode;
large slide decks add a minute or two. Watch the live stage on the Processing page.

**"My file type was rejected."**
Only MP4 / MOV / WAV (video/audio) and PDF (slides) are accepted. Convert other
formats first.

---

## Editor

**"I made a bad edit — can I undo it?"**
Yes. Open the Audit tab and click Undo (or the undo shortcut). The whole session
steps back; Redo steps forward. Nothing is ever permanently lost.

**"A segment is on the wrong slide."**
Use the segment's Reassign action and pick the correct slide from the grid.

**"Two speakers are really the same person."**
Open the Speakers panel and rename/merge the duplicate — it fixes every segment
that referenced the old name at once.

**"A segment exported as (Unknown)."**
That segment has no speaker assigned. Assign one in the Editor, then re-export.

**"Someone else has the editor open."**
Editing is one-person-at-a-time. You'll see who holds it; an admin can force-take
control if they're unavailable.

**"I can't find the Split/Merge option."** / **"The Ask AI tab is missing."**
Both are behind feature switches that are off by default. An admin enables them in
the environment configuration; until then they're intentionally hidden.

---

## Video & captions

**"Captions aren't showing."**
Click the CC button. If they still don't appear, the session may not have finished
processing — confirm its status is "ready".

**"Captions don't match the transcript."**
Captions regenerate from your corrected transcript on each edit. If they differ,
you likely have an unsaved edit in progress — save it and reload.

**"I can't change playback speed."**
The player is fixed at 1× today; speed control isn't wired yet.

---

## Chat, polls & discrepancies

**"Do I have to place every chat message?"**
No — most chat is context. Place the notable questions/moments; leave the rest.

**"I can't edit a chat message or poll."**
They're read-only (from the original meeting). You can move or detach an anchor,
but not change the text.

**"There are hundreds of low-confidence flags."**
Work the Discrepancies pane top-down (it's priority-ranked). Mark OK the ones that
are correct, edit the ones that aren't; the rest can pass to the next reviewer.

---

## SOP workflow

**"A stage is overdue (ATTN)."**
The current assignee is past the stage SLA. Open the session, finish the stage and
mark it Done, or an admin can reassign it.

**"A stage advanced by mistake."**
An admin can re-open the stage; everyone downstream is notified.

**"I'm not getting deadline emails."**
Deadline emails are off by default — an admin enables them in configuration. Even
when on, you get at most one reminder per stage per day.

---

## Sessions & recovery (admin)

**"I deleted a session by accident."**
Restore it from the Trash tab within 30 days. Permanent purge cannot be undone.

**"Why can't I delete a session?"**
Soft-delete is limited to admins and one external partner account; everyone else
sees it disabled.

**"A session is stuck and re-ingest didn't help."**
From the Editor → Admin tab, the rescue buttons (Re-Ingest / Re-Align / Init Stage
Assignees / Auto-Place Polls / Abort) re-run individual pipeline stages. For deeper
recovery, operators have the `/v1/diag/*` endpoints (see `CLAUDE.md`).

---

## When to escalate to an engineer

- A session fails repeatedly after re-ingest on good source media.
- The "reload for <sha>" banner persists after a hard refresh (frontend/api
  version skew).
- Exports are missing data that is visibly present in the Editor.
- Any 500 error that doesn't clear on retry — capture the session ID.

---

## Source Verification
- **Files Used:** help-center/*.md (per-feature Troubleshooting sections), docs/gap-analysis.md, app/config.py (feature-flag defaults), CLAUDE.md (operator endpoints)
- **Components Used:** Editor Admin tab (rescue), AppHeader version chip
- **APIs Used:** /v1/diag/* (operator), session re-ingest/re-align
- **Database Tables Used:** none directly (symptom-oriented)
- **Permission Logic Used:** admin-gated rescue + soft-delete carve-out noted where relevant
- **Confidence Score:** High — symptoms map to verified behaviors/flags; feature-flag defaults from app/config.py read this session.
- **Evidence Links:** [config.py:121](../app/config.py#L121), [config.py:134](../app/config.py#L134), [gap-analysis.md](../docs/gap-analysis.md)
