# rounds.vin — Frequently Asked Questions

Plain-language answers for everyone who uses rounds.vin. This is the offline
companion to the in-app Help Center (the question-mark button in the top bar).
Content here mirrors `HELP_CONTENT.ts` — when one changes, change both.

> **Voice:** second person, end-user nouns. No file names, no database terms,
> no internal routes.

---

## Getting started

**What is rounds.vin?**
It is where recorded VIN sessions become finished, accurate transcripts. You
upload a recording, the system produces a first-pass transcript with speaker
labels and slide alignment, and then the transcript moves through copy editing,
medical review, and publishing before it ships to the CMS.

**I forgot my password — what do I do?**
Contact your admin to set a new initial password. Five failed sign-in attempts
in fifteen minutes will briefly lock the account; wait it out, then sign in with
the new password.

**How long do sessions last?**
You stay signed in for up to a week of activity. After a short period of
inactivity the app may quietly refresh your session in the background so you do
not lose your place.

**Why does the app sometimes say "Slow down"?**
A safety limit guards the AI pipeline from accidental bursts of work. Wait a few
seconds and try the action again.

---

## Uploading & processing

**What file types can I upload?**
MP4, MOV, and WAV for video and audio, and PDFs for slide decks. The upload page
rejects other types up front.

**What is the difference between AI Mode and Default Mode?**
AI Mode sends the media to Gemini for a richer transcript with speaker labels and
slide markers. Default Mode runs standard cloud transcription, which is faster
and cheaper but plainer. Pick AI Mode for clinical content where speaker
attribution and slide alignment matter; pick Default for quick passes.

**How long does processing take?**
A typical hour of video takes about ten to fifteen minutes end to end. AI Mode is
slower than Default Mode. Large slide decks add a minute or two for slide
extraction.

**Why is my upload slow?**
Uploads go directly from your browser to cloud storage, so the speed is your
local upload speed. Large videos take time — leave the tab open until the
progress bar reaches 100%.

**My upload says it is stuck — what now?**
If progress sits at 100% for more than five minutes, refresh the page and try
once more. If it still hangs, contact your admin, who can re-ingest the session.

**Can I retry a failed session safely?**
Yes. Re-ingest restarts the pipeline from the upload; re-runs are built to be
safe to repeat. Only admins can fire re-ingest.

---

## Editing a transcript

**How do I edit a segment?**
Click the segment text in the middle pane, type your change, then click Save.
Use Cancel to drop the edit. Every save is reversible.

**I made a mistake — can I undo it?**
Yes. Open the Audit tab on the right rail and click Undo, or press the undo
shortcut. The whole session moves back one step; Redo moves it forward again.

**How do I change who said a segment?**
Use the Speakers panel on the top right to rename, merge, or reassign speakers
across the whole session. A one-time rename fixes every segment that references
that speaker.

**What do the colored chips above the transcript do?**
They filter the transcript. "Filler" shows only segments with filler words,
"Punctuation" surfaces punctuation issues, "Drift" finds places where the AI
alignment looks shaky. Click a chip again to clear it.

**Why is a segment flagged "Low confidence" or "Drift"?**
The system flags segments where the AI transcript differs from the reference
text or where its confidence is below the review threshold. Open the
Discrepancies view, check the segment, and mark it OK once you have confirmed it.

**Can two people edit the same session at once?**
No. Editing is locked to one person at a time. If someone else has the editor
open, you will see who holds it; an admin can force-take control if needed.

---

## Speakers

**Two detected speakers are actually the same person. How do I merge them?**
Open the Speakers panel, rename or merge the duplicate to match the correct
speaker. Every segment that used the old name updates at once.

**A segment shows "(Unknown)" in my export. How do I fix it?**
That segment has no speaker assigned. Open the session in the Editor, assign the
correct speaker, and re-export.

---

## Chat, polls & video

**Do I have to place every chat message into the transcript?**
No. Most chat is context only. Place the notable questions and key moments by
dragging the card onto the right segment; leave the rest unplaced.

**Can I edit a chat message or poll?**
No — they are read-only, carried over from the original meeting. You can move an
anchor to a different segment or detach it, but not change its text.

**The captions are not showing.**
Click the CC button in the video controls. If captions still do not appear, the
session may not have finished processing — check that its status is "ready".

---

## Workflow & publishing

**What are the SOP stages?**
Prep, Copy Draft, Medical, Copy Final, CMS, Captions, QA, Complete. The session
moves forward when the current stage's assignee marks it Done.

**What happens if a stage runs past its deadline?**
The stage assignee gets a deadline email on the next hourly check — at most one
email per stage per day, so you will not be spammed.

**Where do exports come from?**
The Export menu in the Editor generates the file fresh from the current
transcript every time. Filler words are stripped from docx and txt for
readability; srt and vtt keep them so captions stay aligned to the audio.

---

## Sessions & history

**I deleted a session by accident — can I get it back?**
Admins can restore it from the Trash tab on the Sessions page. Permanent purge
removes the data for good and cannot be undone, so the system asks twice.

**What happens when I archive a session?**
Archive moves it out of the active Sessions list but keeps the data intact.
Admins can restore it any time.

**Where can I see who edited a transcript?**
Open the session in the Editor, then the Audit tab on the right rail. Every edit
is logged with the user, timestamp, and before/after text. Nothing is ever
deleted from the audit log.

---

## Help & support

**How do I open the Help Center?**
Click the question-mark button in the top bar, or press `?` when no text box is
focused. Press `Esc` to close.

**When will Ask AI work?**
The Ask AI tab is in the next release. For now, use the search box at the top of
the Help Center or browse the tabs.

**Where can I learn more?**
See the long-form guides in [articles.md](articles.md), or click "Full docs" at
the bottom of the Help panel. For bug reports or feature ideas, reach your admin.

---

_Contact: johndean@vin.com · `#rounds-help` · rounds.vin/docs_
