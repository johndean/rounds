# Editor

## What This Does

The Editor is where you review and correct a finished transcript. It is a
three-pane workspace: the video and slides sit on the left, the transcript runs
down the middle, and reference and review tools live on the right. Here you fix
the text, line segments up with the right slide, attribute speech to the right
person, work through the spots the system flagged, and download the finished
transcript when it is ready.

## Who Can Use It

Anyone signed in can open the Editor for a session. Only one person can edit a
session at a time — if a teammate already has it open, you get read-only access
until their hold expires. A note at the top tells you who holds it and when their
hold ends. Admins can force-take the session if needed.

## How To Access

Open a session from the Sessions page or the dashboard, then click into its
Editor. The breadcrumb at the top of the page (Sessions / session code / Editor)
shows where you are and links back.

## How To Create

The Editor does not create sessions — sessions come from the Upload page. The
Editor opens automatically once a session finishes processing, and you take it
from there.

## How To Edit

- **Edit a segment.** Click a segment's **Edit** button, type your correction in
  the box that opens, then click **Save**. Click **Cancel** to drop the change.
  The status next to the buttons tells you when an edit has saved.
- **Move a segment to a different slide.** Click the segment's **Reassign**
  button and pick the correct slide from the list.
- **Change who said a segment.** Click the segment's **Speaker** button and pick
  the right person from the speaker tiles.
- **Undo and redo.** Use the **Undo** and **Redo** buttons at the top of the
  Editor (or the keyboard shortcuts). Undo steps the whole session back one
  change; Redo steps it forward. You can also open the Audit view to see the full
  history of who changed what and when.
- **Find and replace.** Click **Find & Replace** to sweep a word or phrase across
  the whole transcript at once.
- **Filter by flag.** The colored chips under the title (Medication, Name,
  Number, Filler, Punctuation, Drift, and more) filter the transcript to just the
  segments that carry that flag. Click a chip to apply it; click it again to
  clear it. The number on each chip tells you how many segments match.
- **Follow the video.** The transcript scrolls to keep up with playback. Use the
  **Follow video** toggle to switch that off when you want to scroll freely.

Every save is reversible, and the change history goes back to the moment the
session was created.

## How To Delete

The Editor does not delete sessions. What you can remove here are individual
changes — use Undo to step back a correction — and chat or poll cards you have
placed (see the chat and polls help). To delete an entire session, use the
Sessions page; that is reserved for admins.

## Common Tasks

- **Fix a misheard word.** Click Edit on the segment, correct it, Save.
- **Clean up one class of problem fast.** Click the relevant flag chip (for
  example Punctuation), work down the filtered list, then clear the chip.
- **Check the original speech-to-text.** Switch to the STT Reference tab to read
  the raw machine transcript, or the Discrepancies tab to see the two side by
  side where they disagree.
- **Download the result.** Click **Download** at the top right and pick a format.

## Troubleshooting

- **I have read-only access.** Someone else has the session open. The banner at
  the top shows who holds it and when the hold expires; wait it out, or ask an
  admin to force-take it.
- **My edit did not stick.** If you are in read-only mode, edits are disabled.
  Otherwise, watch the status next to the Save button — it tells you when the
  change has saved.
- **A flag chip shows nothing when I click it.** That flag has no segments in
  this session, so the filtered list is empty. Clear the chip to see everything
  again.
- **The transcript keeps scrolling away from me.** Turn off the **Follow video**
  toggle so your own scrolling wins.

## FAQs

**Can two people edit the same session at once?**
No. Editing is locked to one person at a time. If someone else has it open you
get read-only access and can see who holds it; an admin can force-take control.

**How far back does the change history go?**
To the moment the session was created. Nothing is ever removed from the history.

**What formats can I download?**
Word (.docx), Captions (.srt), Plain Text (.txt), and a Word-macro bundle (.zip).
Each file is generated fresh from the current transcript, so it always reflects
your latest edits.

**What do the tabs in the middle do?**
AI Transcript is the working transcript you edit. STT Reference shows the raw
speech-to-text. Discrepancies shows where the two disagree. Audit shows the full
change history.

## Permissions Required

You must be signed in to open the Editor. Editing requires holding the session's
single-editor lock — the first person in gets it, everyone else is read-only
until it expires. The Force-take button appears only for admins.

## Source Verification
- **Files Used:** frontend/src/views/EditorView.vue, frontend/src/components/editor/TranscriptPane.vue, frontend/src/components/editor/DownloadMenu.vue, frontend/src/components/editor/DiscrepanciesPane.vue, frontend/src/composables/useIsAdmin.ts, app/api/exports.py, docs/help-center/articles.md, docs/help-center/faq.md, frontend/src/constants/help-content.ts
- **Components Used:** EditorView.vue (three-pane grid, SOP stepper, flag chips, Undo/Redo, Find & Replace, Follow-video toggle, lock banner, tabs), TranscriptPane.vue (Edit/Reassign/Speaker inline actions, Save/Cancel), DownloadMenu.vue (Download button + format list), DiscrepanciesPane.vue, DownloadMenu
- **APIs Used:** GET /v1/sessions/{id}, GET /v1/sessions/{id}/segments, GET /v1/sessions/{id}/slides, GET /v1/sessions/{id}/speakers, GET /v1/sessions/{id}/chat, GET /v1/sessions/{id}/polls, GET /v1/sessions/{id}/discrepancies, GET /v1/audit/sessions/{id}/corrections, POST /v1/sessions/{id}/corrections (text_edit / slide_reassignment / undo / redo), GET /v1/sessions/{id}/exports/{format}
- **Database Tables Used:** sessions, segments, slides, session_speakers, chat, polls, transcription_discrepancies, correction_ledger, artifacts
- **Permission Logic Used:** JWT presence to open; single-editor session lock (useSessionLock) for write access; admin-only Force-take gated by useIsAdmin (LEGACY_ADMIN_EMAIL = johndean@vin.com)
- **Confidence Score:** High — inline-edit buttons, flag chips, lock banner, and download formats read directly from EditorView.vue, TranscriptPane.vue, and DownloadMenu.vue.
- **Evidence Links:** [frontend/src/views/EditorView.vue (flag chips)](../frontend/src/views/EditorView.vue#L1247), [frontend/src/views/EditorView.vue (lock banner)](../frontend/src/views/EditorView.vue#L1138), [frontend/src/components/editor/TranscriptPane.vue (Edit/Reassign/Speaker + Save/Cancel)](../frontend/src/components/editor/TranscriptPane.vue#L488), [frontend/src/components/editor/DownloadMenu.vue (formats)](../frontend/src/components/editor/DownloadMenu.vue#L27)

> Maintainer note: the seed articles.md lists html and vtt as Export-menu
> formats. The actual DownloadMenu.vue UI exposes only docx / srt / txt / zip
> (the backend exports.py additionally supports vtt and html, but they are not
> selectable in this menu). The trigger is labeled "Download," not "Export."
> This article documents the four UI-selectable formats only. Discrepancy with
> seed copy noted.
