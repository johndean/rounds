# Upload

## What This Does

The Upload page is where a new recording becomes a session. You pick a video or
audio file (and, optionally, a slide deck and a chat or poll log from the
original meeting), choose how you want it transcribed, and start processing. Your
files go straight from your browser to secure storage, and the system then
transcribes the audio and lines the transcript up against your slides. When it
finishes, the session opens in the Editor for review.

## Who Can Use It

Anyone signed in can upload a session. There is no separate permission for
starting an upload — if you can sign in, you can create a session here.

## How To Access

Click **Upload** in the top bar. The page opens with a large drop zone and a set
of processing options below it.

## How To Create

1. **Add your files.** Drag them onto the drop zone, or click the drop zone to
   open your file picker. You can add several files at once. The page reads the
   role of each file from its name: video and audio become the recording, a PDF
   or slide file becomes the slide deck, and a text file becomes the chat or
   manifest. The roles it detected are shown next to each file.
2. **Choose a Processing Pipeline.**
   - **Direct to AI** sends the media straight to the AI for a formatted
     transcript.
   - **AI-Enhanced** transcribes first and then has the AI refine the result;
     this is the mode that uses the Speech-to-Text option below.
3. **Choose an AI Processing Mode** — Transcript, Summary, Key Moments,
   Structured Notes, or Custom Prompt. Transcript is the usual choice for a clean
   verbatim transcript.
4. **Pick an AI Model** from the model list.
5. **(Optional) Set a Processing Style** — Lecture, Training / Workshop,
   Technical Deep Dive, Podcast / Conversation, Sales / Presentation, or a custom
   style. This tells the AI what kind of content it is working with.
6. **(Optional) Configure the filler-word layer.** The Instructor Intelligence
   Layer card lets you switch tiers of filler-word cleanup on or off — acoustic
   fillers ("um", "uh"), discourse fillers ("you know", "basically"), and
   redundant phrases.
7. Click **Process →**. The button shows the upload count as it streams each
   file, then takes you to the processing page for that session. Leave the tab
   open until it finishes — your files are streaming directly from your browser.

## How To Edit

There is nothing to edit on the Upload page itself once processing starts — it is
a one-way "start a session" form. To remove a file before you process, click the
**×** next to it in the file list. To change the transcript after processing, do
that in the Editor.

## How To Delete

The Upload page does not delete anything. Removing a file from the list before
processing simply drops it from this upload. To remove a session after it has
been created, use the Sessions page (deleting and archiving sessions is reserved
for admins).

## Common Tasks

- **Upload just audio.** Drop an audio file on its own — slides and chat are
  optional.
- **Add slides.** Include a PDF or slide file in the same upload and it is
  detected as the slide deck automatically.
- **Quick, plain transcript.** Use the Transcript processing mode with the Direct
  to AI pipeline.
- **Trim filler words.** Leave the filler-word tiers switched on so "um" and
  "uh" are cleaned up during processing.

## Troubleshooting

- **My upload is slow.** Files go directly from your browser to storage, so the
  speed is your own connection's upload speed. Large videos take time — leave the
  tab open until the count finishes.
- **The Process button is greyed out.** You have not added a file yet. Add at
  least one file and it becomes active.
- **It says "do not close this tab."** That message appears while bytes are
  streaming. Closing the tab interrupts the upload — wait for it to finish.
- **An upload failed partway.** Start the upload again from this page. If a
  session was created but never finished processing, contact your admin.

## FAQs

**What file types can I upload?**
Video and audio files (such as MP4, MOV, MKV, WebM, MP3, M4A, WAV), slide files
(PDF, PPTX, PPT), and text files for chat or session manifests. The page reads
each file's role from its name.

**What is the difference between the two pipelines?**
Direct to AI sends the media straight to the AI and returns a formatted
transcript. AI-Enhanced transcribes first and then has the AI clean up the
result — and only this mode uses the Speech-to-Text option.

**Can I upload more than one file at once?**
Yes. Add as many as you need in a single upload; duplicate files (same name and
size) are skipped automatically.

**Do I have to stay on the page while it uploads?**
Stay until the streaming step finishes — that part runs in your browser. Once it
hands off to processing, you can navigate away and watch progress on the
processing page.

## Permissions Required

You must be signed in. There is no additional permission to upload — any signed-in
user can create a session.

## Source Verification
- **Files Used:** frontend/src/views/UploadView.vue, app/api/gcs_upload.py, docs/help-center/faq.md, docs/help-center/articles.md, frontend/src/constants/help-content.ts
- **Components Used:** UploadView.vue (drop zone, file list, Processing Pipeline / AI Processing Mode / AI Model / Processing Style / Instructor Intelligence Layer controls, Process button)
- **APIs Used:** POST /v1/sessions, POST /v1/gcs/upload-url (signed URL), PUT to signed GCS URL, POST /v1/gcs/upload-complete, GET /v1/settings (default prefill)
- **Database Tables Used:** sessions, sources (written by upload-complete)
- **Permission Logic Used:** JWT presence only — no role gate on the Upload page or its endpoints
- **Confidence Score:** High — UI controls, file-role inference, and the upload sequence are read directly from UploadView.vue; backend write path confirmed in gcs_upload.py.
- **Evidence Links:** [frontend/src/views/UploadView.vue](../frontend/src/views/UploadView.vue#L328), [frontend/src/views/UploadView.vue (inferRole)](../frontend/src/views/UploadView.vue#L86), [frontend/src/views/UploadView.vue (processBatch)](../frontend/src/views/UploadView.vue#L199), [app/api/gcs_upload.py](../app/api/gcs_upload.py#L155)

> Maintainer note: the in-app/seed copy says the page "rejects other types up
> front." The actual `<input type="file" multiple>` in UploadView.vue has no
> `accept` attribute and `inferRole` falls back to an "other" role rather than
> rejecting; gcs_upload.py does not enforce a file-type allowlist. This article
> describes the detected types without claiming hard rejection. PARTIALLY
> IMPLEMENTED: client-side type rejection.
