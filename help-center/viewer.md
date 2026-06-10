# Viewer

## What This Does

The Viewer is a read-only preview of a finished session laid out the way it will
read once published. It shows the session's code, title, presenter, and topic
tags at the top, then a slide-by-slide render of the transcript — each slide with
the speech that was spoken over it, attributed to the right speaker. It also
lists the download formats available for the session and a publishing checklist
of the places a finished session usually goes. Use it to check how a transcript
reads before it ships, and to share or hand off a session once editing is done.

## Who Can Use It

Anyone signed in can open the Viewer for a session. It is read-only for everyone
— there is no edit mode here, and no admin-only controls. To make changes you go
back to the Editor.

## How To Access

Open a session and switch to its preview. From inside the Viewer there is an
**Editor** button in the toolbar that takes you straight to the editing view for
the same session. A session only renders meaningful content here once it has
finished processing; before that the slide area shows that the pipeline is still
pending.

## How To Create

The Viewer does not create anything — it is a rendered view of a session that
already exists. Sessions start on the Upload page and are corrected in the
Editor; the Viewer simply shows the result.

## How To Edit

You cannot edit from the Viewer; it is read-only by design. The only thing you
can change here is the preview itself: tick **Include key points section** to add
a key-points block to the bottom of the preview, or untick it to hide that block.
For any real change to the transcript, speakers, or slide alignment, click
**Editor** in the toolbar and make the change there.

## How To Delete

Nothing is deleted from the Viewer. It holds no editable records — to remove a
session, use the Sessions page (reserved for admins).

## Common Tasks

- **Read the transcript slide by slide.** Scroll the preview. Each slide shows
  its number and title, then the speech spoken over it. Slides with no speech are
  marked "no audio."
- **See the available download formats.** The format tiles list each format with
  a short description of what it is for — a Word document, captions, plain text,
  and a one-time Word-macro bundle.
- **Add a key-points summary to the preview.** Tick **Include key points
  section** in the toolbar.
- **Jump to editing.** Click **Editor** in the toolbar to open the same session
  in the Editor.

## Troubleshooting

- **The slides area says the pipeline is still pending / there are no slides.**
  The session has not finished processing yet, or no slide deck was attached.
  Check its status on the Sessions page; once it shows ready, the slides appear.
- **A slide shows "no audio."** Nothing was spoken over that slide, so there is
  no transcript text to show for it. That is expected for title or transition
  slides.
- **The key-points block is empty.** Key points are produced during the AI
  processing pass. If the session was not processed in AI Mode, or has not
  finished, the block stays empty.
- **A download or a publishing-checklist link does not start anything.** Those
  actions are not connected in this build yet — the page tells you so when you
  click. To get a file today, use the download in the Editor.

## FAQs

**Can I edit from the Viewer?**
No — the Viewer is read-only. To make edits, open the session in the Editor
instead. There is an Editor button in the Viewer toolbar.

**What formats are listed here?**
A Word document, a captions file, plain text, and a one-time Word-macro bundle,
each with a short description of what it is for.

**Why did clicking a download do nothing?**
Downloading from the Viewer is not wired up in this build — clicking shows a note
saying so. Use the download in the Editor to get a file.

**What is the publishing checklist?**
A list of the destinations a finished session typically goes to. It is a
reference checklist; the links are not active yet in this build.

**How do I share a session with someone outside the app?**
Download the session from the Editor and share the file. The Viewer itself is an
in-app preview, not a public link.

## Permissions Required

You must be signed in to open the Viewer. There are no role-based controls on
this page — it is read-only for every signed-in account, with no admin-only
features.

## Source Verification
- **Files Used:** frontend/src/views/ViewerView.vue, frontend/src/router/index.ts, frontend/src/constants/help-content.ts, docs/help-center/articles.md, docs/help-center/faq.md
- **Components Used:** ViewerView.vue (preview-id header, Export Preview toolbar with "Include key points section" checkbox + Editor link, format tiles, publishing checklist, slide-by-slide render, key-points block, footer counts)
- **APIs Used:** GET /v1/sessions/{id}, GET /v1/sessions/{id}/segments, GET /v1/sessions/{id}/slides, GET /v1/sessions/{id}/speakers
- **Database Tables Used:** sessions, segments, slides, session_speakers
- **Permission Logic Used:** JWT presence to load (router beforeEach auth check); no admin gate, no per-page role logic — read-only for all signed-in users
- **Confidence Score:** High — header fields, the four download tiles, the publishing checklist, the key-points toggle, and the read-only "not yet wired" download/publish behavior all read directly from ViewerView.vue.
- **Evidence Links:** [frontend/src/views/ViewerView.vue (download tiles)](../frontend/src/views/ViewerView.vue#L71), [frontend/src/views/ViewerView.vue (download not wired → warn toast)](../frontend/src/views/ViewerView.vue#L91), [frontend/src/views/ViewerView.vue (Include key points checkbox + Editor link)](../frontend/src/views/ViewerView.vue#L122), [frontend/src/views/ViewerView.vue (slide-by-slide render + "no audio")](../frontend/src/views/ViewerView.vue#L157)

> Maintainer note: the seed help-content.ts viewer copy says "Export the session
> as an HTML or zip from the Editor." ViewerView.vue's own download tiles offer
> Word (.docx), Captions (.srt), Plain Text (.txt), and a Word-macro bundle
> (.zip) — not HTML — and all download + publishing-link clicks are currently
> stubbed to a "not yet wired" warning toast (downloadFile / openPub), pending
> the Phase 10 exports wiring. This article documents the verified read-only
> behavior, not the seed's HTML/zip claim.
