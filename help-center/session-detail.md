# Session detail

## What This Does

The session detail page is the full picture of one recording. It shows the
status and title up top, the files that make up the session, the key counts
(segments, words, sources, duration), how the transcript lines up with the
slides, who is assigned to each review stage, and quick links into the editor,
the review workflow, and the change history. It is the page you land on when you
open a finished session from the list.

## Who Can Use It

Anyone signed in can open a session's detail page, read everything on it, edit
the title and code, add or update files, and change stage assignments. There is
no separate restricted view — everyone sees the same page.

## How To Access

Open the **Sessions** page and click a session that has finished processing. (A
session still being processed opens its processing page instead.) You can also
reach it from the dashboard by clicking a recent session card that is no longer
processing.

## How To Create

You do not create a session here — sessions begin on the upload page. What you
do create on this page are the pieces that complete a session: you can attach a
slide deck, a chat log, a session manifest, or speaker bios using the file
controls described below.

## How To Edit

**Title and code.** Click the title or the code to edit it inline. Type your
change and it saves immediately — there is no separate save button.

**Files.** In the **Session files** card, each file type (slides, chat log,
manifest, speaker bios) shows whether it is present or missing. Click **Add** on
a missing file, or **Update** on a present one, to attach or replace it. After
slides are added, the system extracts them and they appear in the editor's
slide rail once extraction finishes.

**Stage assignments.** In the **Stage Assignments** card, each review stage
shows who is responsible. Click the edit control on a stage to open the picker,
then choose a person or a group. A small marker appears next to any stage you
have set by hand; click **Reset** to return that stage to the default for the
session's type. Changing the session **Type** (the dropdown at the top of the
card) offers to apply that type's default assignments to every stage at once —
this replaces any manual choices, so the app asks you to confirm first.

## How To Delete

There is no delete control on this page. To remove a session, go back to the
sessions list and delete it there (deleting is an administrator action). Within
the file cards, adding a new file of a type that already exists replaces the
old one rather than keeping both.

## Common Tasks

**Check what is missing.** The **Session files** card flags how many expected
files are missing and marks each one **Present** or **Missing**, so you can see
at a glance what still needs to be added.

**Review the chat participants.** The **Chat Participants** card lists everyone
found in the chat log with a message count each, and shows the total at the top.

**Read the alignment.** The **Alignment** card shows the percentage of the
transcript that has been matched to a slide, alongside the number of sections.
The chips near the top of the page also show how many segments are flagged to
review and the overall aligned percentage.

**Scan quality.** Lower on the page, the **Segment Confidence**, **Slide
Assignment**, and **Review Queue** cards let you scan per-segment confidence,
see how segments are distributed across slides, and read the segments flagged
for a closer look.

**See the timeline.** The timeline bar shows the session's duration with
colored bands for each slide's stretch of segments.

**Open the editor.** Use **Open Editor** (top right) to start correcting the
transcript. **Workflow** opens the review stages and **Audit** opens the change
history.

## Troubleshooting

**The slides, segments, or timeline are empty.** The session has not finished
processing yet — these fill in after processing completes. The cards keep their
frame and show a short "no data yet" message in the meantime.

**A download button shows a warning instead of downloading.** The download
buttons in the left panel of this page are not the working export. To export the
finished transcript, open the editor and use its Export menu.

**A publishing link does not stick.** The publishing-link chips on this page are
placeholders and do not yet save. They will warn rather than persist when
clicked.

**I changed the type and lost my manual assignees.** Applying a type's defaults
replaces every stage's assignee with that type's defaults. The app warns you
before doing this. To restore a single stage you set by hand, use the **Reset**
control on that stage — but note Reset returns it to the type default, not to
your previous manual choice.

**My title edit did not seem to save.** Title and code edits save as soon as you
finish editing; there is no page-level save. If a save fails you will see an
error message — try again.

## FAQs

**What are the files on this page?**
The pieces that make up a session: the slide deck, the chat log, the session
manifest, and speaker bios. Each shows whether it is present or missing.

**How do I attach a slide deck after upload?**
Click **Add** on the Slides file, pick the PDF, and the system extracts the
slides. They appear in the editor's slide rail once extraction completes.

**What does Chat Participants show?**
Everyone found in the chat log, each with a message count, and the total at the
top.

**How do I change who is assigned to a review stage?**
Open the Stage Assignments card, click the edit control on a stage, and pick a
person or group. Use Reset to return a stage to the default for the session's
type.

**Where do exports come from?**
Open the editor and use its Export menu. The download buttons on this page are
not the working export.

## Permissions Required

You only need to be signed in to view this page, edit the title and code, add or
update files, and change stage assignments. Deleting the session is not done
here — it is an administrator action on the sessions list.

---

## Source Verification
- **Files Used:** frontend/src/views/SessionDetailView.vue, frontend/src/components/session/AddFileModal.vue, frontend/src/components/session/SessionTextEdit.vue, frontend/src/services/api.ts (sessions.get / .sources / .slides / .stageAssignees / .setStageAssignee / .applyTypeDefaults / .chatParticipants), frontend/src/fixtures/sop_stages.ts, docs/help-center/articles.md, frontend/src/constants/help-content.ts
- **Components Used:** SessionDetailView.vue, SessionTextEdit.vue (inline title/code edit), AddFileModal.vue, Icon.vue
- **APIs Used:** GET /v1/sessions/{id}, GET /v1/sessions/{id}/sources, GET /v1/sessions/{id}/slides, GET /v1/sessions/{id}/segments, GET /v1/sessions/{id}/stage-assignees, PATCH stage assignee, apply-type-defaults, chat-participants — wired in [frontend/src/views/SessionDetailView.vue:97](../frontend/src/views/SessionDetailView.vue#L97)
- **Database Tables Used:** sessions, session sources, slides, segments, session_stage_assignees (via the endpoints above)
- **Permission Logic Used:** JWT presence only. This view has no admin gate; the help-content.ts "admin" topics for this page describe Editor Admin-tab rescue tools that live in the editor, not on this page.
- **Confidence Score:** High — inline title/code edit, file Add/Update + replace semantics, stage reassign/reset, type-defaults confirm, alignment/chat/confidence/timeline cards, and the empty states are directly code-verified. Two surfaces are explicitly NOT WIRED: the left-panel download buttons ([frontend/src/views/SessionDetailView.vue:299](../frontend/src/views/SessionDetailView.vue#L299) warn-only) and the publishing-link chips ([frontend/src/views/SessionDetailView.vue:329](../frontend/src/views/SessionDetailView.vue#L329) warn-only) — the body steers users to the editor's Export menu and flags the publishing links as placeholders.
- **Evidence Links:** [frontend/src/views/SessionDetailView.vue:361](../frontend/src/views/SessionDetailView.vue#L361) (inline code/title edit), [frontend/src/views/SessionDetailView.vue:256](../frontend/src/views/SessionDetailView.vue#L256) (session files present/missing), [frontend/src/views/SessionDetailView.vue:178](../frontend/src/views/SessionDetailView.vue#L178) (setStageAssignee), [frontend/src/views/SessionDetailView.vue:148](../frontend/src/views/SessionDetailView.vue#L148) (apply type defaults confirm), [frontend/src/views/SessionDetailView.vue:299](../frontend/src/views/SessionDetailView.vue#L299) (download not wired), [frontend/src/views/SessionDetailView.vue:329](../frontend/src/views/SessionDetailView.vue#L329) (publishing link not persisted)
