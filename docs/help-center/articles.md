# rounds.vin — Help Center Articles

Long-form guides for getting real work done in rounds.vin. Where the
[FAQ](faq.md) answers one question at a time, these articles walk an end-to-end
task from start to finish. They are written for the people who use the app —
operators, copy editors, medical reviewers — not for engineers.

For the feature-by-feature reference, see the product docs in
[../product/](../product/).

**Contents**

1. [From recording to published transcript](#1-from-recording-to-published-transcript)
2. [Uploading a session](#2-uploading-a-session)
3. [Correcting a transcript in the Editor](#3-correcting-a-transcript-in-the-editor)
4. [Getting speakers right](#4-getting-speakers-right)
5. [Placing chat and polls](#5-placing-chat-and-polls)
6. [Reviewing AI accuracy](#6-reviewing-ai-accuracy)
7. [Moving a session through the SOP workflow](#7-moving-a-session-through-the-sop-workflow)
8. [Exporting and publishing](#8-exporting-and-publishing)
9. [For admins: rescuing a stuck session](#9-for-admins-rescuing-a-stuck-session)

---

## 1. From recording to published transcript

Every session follows the same arc. Knowing the whole arc makes each step make
sense.

1. **Upload.** You bring in the recording (and, optionally, slides and a chat
   log). The files go straight to cloud storage from your browser.
2. **Processing.** In the background, the system transcribes the audio, samples
   the video for slide changes, and lines the transcript up against the slides.
   You can watch this on the Processing page.
3. **Ready.** When processing finishes, the Editor opens. This is where the
   human work happens: correcting text, fixing speakers, reviewing the spots the
   AI was unsure about.
4. **SOP workflow.** The session walks through a fixed set of review stages —
   copy editing, medical review, final copy, CMS prep, captions, and QA — each
   with an owner and a deadline.
5. **Publish.** Once the stages are complete, the finished transcript is
   exported and shipped to the CMS.

You can always see where a session sits on this arc from the status chip on the
Sessions page and the stage cards on the SOP page.

---

## 2. Uploading a session

Start on the **Upload** page (top bar → Upload).

**Pick your files.** Drop in a video or audio recording (MP4, MOV, or WAV). Add
a slide deck PDF if you have one, and a chat or poll log from the original
meeting if the platform produced one.

**Choose how it gets transcribed.**

- **AI Mode** sends the media to Gemini. You get a richer transcript with speaker
  labels and slide markers built in. Use this for clinical content where it
  matters who said what and which slide they were on.
- **Default Mode** runs standard cloud transcription. It is faster and cheaper
  but plainer. Use it for quick passes.

You also pick a **prompt template**, which tells the AI what tone to use and how
to handle filler words and slide markers. Your admin maintains these under
Settings.

**Start processing.** The upload runs in the background — you can navigate away.
Watch progress on the **Processing** page, which shows the current stage and a
live progress bar. A typical hour of video finishes in ten to fifteen minutes.

If the upload sits at 100% for more than five minutes, refresh and try once
more. Persistent hangs are rare; an admin can re-ingest the session in one click.

See also: [../product/upload-processing.md](../product/upload-processing.md).

---

## 3. Correcting a transcript in the Editor

The **Editor** is a three-pane workspace: slides on the left, the transcript in
the middle, and reference and audit tools on the right.

**Edit text.** Click a segment in the middle pane, type your correction, and
click Save. Cancel drops the edit. Every save is reversible — there is no way to
lose work.

**Undo and redo.** Open the **Audit** tab on the right rail. It lists every edit
with who made it, when, and the before/after text. Undo moves the whole session
back one step; Redo moves it forward. The history goes back to the moment the
session was created and is never deleted.

**Filter with the chips.** The colored chips above the transcript are filters.
Click "Filler" to see only segments with filler words, "Drift" to find shaky
alignment, "Punctuation" to surface punctuation issues. Click a chip again to
clear it. This is the fastest way to sweep a transcript for one class of problem
at a time.

**Compare against the reference.** The right rail shows the raw speech-to-text
reference next to the AI transcript. Where they disagree, you will see it
flagged — useful when you are not sure which version is right.

One person edits a session at a time. If a teammate has it open, you will see who
holds it; an admin can force-take control.

See also: [../product/editor.md](../product/editor.md).

---

## 4. Getting speakers right

Every segment is attributed to a speaker. The AI takes a first pass, but it
often needs cleanup — especially when the same person shows up under two names.

Open the **Speakers** panel (top right of the Editor, or on the Session Detail
page). From there you can:

- **Rename** a speaker — the new name applies to every segment at once.
- **Merge** two speakers when the AI split one person into two.
- **Reassign** a single segment to a different speaker.
- **Add** a speaker who the AI missed entirely.

Because a rename propagates everywhere, fixing speakers is usually a five-minute
job done once near the start of editing — not a per-segment chore.

If a segment exports as **(Unknown)**, it has no speaker assigned. Assign one in
the Editor and re-export.

See also: [../product/speakers.md](../product/speakers.md).

---

## 5. Placing chat and polls

If the original meeting had a chat log or polls, they show up in the right rail
of the Editor under the Chat and Polls tabs.

**You do not have to place everything.** Most chat is context only. Place the
notable questions and key moments; leave the rest unplaced.

**To place a card**, drag it from the right rail onto the transcript segment
where it belongs. The card snaps to that segment's start time and shows a
"PLACED" badge. Drag it again to re-anchor, or drag it back to the rail to detach
it.

Chat messages and polls are read-only — they come from the original meeting, so
you cannot edit their text, only where they sit in the timeline.

See also: [../product/polls-chat-resources.md](../product/polls-chat-resources.md).

---

## 6. Reviewing AI accuracy

The AI scores how confident it was in each segment. The low-confidence ones are
the ones worth your attention.

Open the **Discrepancies** view. It lists the segments where the AI transcript
diverges from the reference, sorted so the riskiest ones come first. For each:

- **Mark OK** if the AI got it right (this clears the flag).
- **Edit** the segment if it is wrong.
- **Dismiss** to skip it without changing anything.

You do not have to clear every flag. Work down the list in priority order; once
the genuinely shaky ones are handled, the rest can pass to the next reviewer.

Common flags you will see: *Low confidence*, *Drift* (the segment diverges from
the slide reference), *Uncertain*, plus content flags like *Medication*, *Name*,
*Number*, and *Date* that point you to spots worth double-checking.

See also: [../product/quality-ai.md](../product/quality-ai.md).

---

## 7. Moving a session through the SOP workflow

Once a session is ready, it enters the **SOP workflow** — a fixed sequence of
review stages, each with an owner and a deadline.

The stages are: **Prep → Copy Draft → Medical → Copy Final → CMS → Captions →
QA → Complete.**

On the **SOP** page each stage is a card showing the current assignee and a Done
button. When the owner of the current stage clicks Done, the session advances and
the next owner picks it up.

**Deadlines.** Each stage carries an SLA in hours. If a stage runs past its SLA,
the assignee gets a reminder email on the next hourly check — at most one per
stage per day.

**Assignees.** Defaults come from your org's settings, based on the session type,
but an admin can override the person on any stage from the Session Detail page.

Only admins can skip or re-open a stage. If a stage advanced by mistake, an admin
can re-open it and everyone downstream is notified.

See also: [../product/session-management.md](../product/session-management.md).

---

## 8. Exporting and publishing

When the transcript is ready to leave rounds.vin, use the **Export** menu at the
top of the Editor. Pick a format and the download starts immediately:

- **docx** — a Word document. Filler words ("um", "uh") are removed for
  readability.
- **txt** — plain text, also with fillers removed.
- **srt** / **vtt** — caption files. Fillers are kept so the captions stay
  aligned to the audio.
- **html** — a styled, self-contained page.
- **zip** — a bundle of all formats plus the original media. Use this when you
  want both a clean Word doc and full captions in one download.

Every export is generated fresh from the current state of the transcript, so it
always reflects your latest edits.

See also: [../product/workflow-and-export.md](../product/workflow-and-export.md).

---

## 9. For admins: rescuing a stuck session

Most sessions process cleanly. When one gets stuck or fails, the rescue tools
live in the **Admin** tab on the right rail of the Editor.

- **Re-Ingest** — restart the whole pipeline from the upload. Use this for a
  transient failure (a network blip, a Gemini quota cap, a one-off crash).
- **Re-Align** — rebuild just the slide-to-segment matches, without re-running
  transcription.
- **Init Session Stages** — assign SOP stages to a legacy session that predates
  the auto-assignment.
- **Auto-Place Polls** — backfill poll anchors for older sessions.
- **Abort** — force a hung session to failed status so it can be cleaned up.

Each button confirms before firing, and Abort asks twice.

**Retry vs. abort:** retry when the failure looks transient and the source media
is good; abort when the media itself is bad and the session should not continue.
Re-runs are safe to repeat.

For bulk operations and deeper diagnostics beyond these buttons, see the
operator command reference in the project's `CLAUDE.md` (the `/v1/diag/*`
endpoints).

---

_Contact: johndean@vin.com · `#rounds-help` · rounds.vin/docs_
