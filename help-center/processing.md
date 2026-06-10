# Processing

## What This Does

The Processing page is what you watch while a session is being built into a
transcript. It shows a "Building your output" card with the file name, a list of
the pipeline steps with the current one spinning, a live progress bar with the
percentage complete, the elapsed time, and an estimate of the time remaining.
Below that, a small panel counts the segments, slide markers, and aligned slides
as they are produced. When everything finishes, the page sends you straight to
the Editor.

## Who Can Use It

Anyone signed in can watch a session process. The Retry and Delete buttons on the
failure card are available to whoever is on the page; deleting asks you to
confirm first.

## How To Access

The Processing page opens for you automatically right after you start an upload.
You can also navigate back to it for a session that is still working. The exact
steps you see depend on how the session is being transcribed:

- An AI Mode session that goes directly to the AI shows: Preparing files → AI
  analysis → Mapping slides → Finalizing.
- An AI Mode session that enhances a first-pass transcript shows: Uploading →
  Transcribing → AI enhancement → filler cleanup → Matching slides.
- A standard (Default Mode) session shows: Uploading → Transcribing → filler
  cleanup → Detecting boundaries → Matching slides.

If a template was chosen or auto-detected for the session, its name shows as a
badge above the steps.

## How To Create

You do not create anything on the Processing page — it reflects work that is
already running. New sessions start on the Upload page, and processing begins the
moment you start one.

## How To Edit

There is nothing to edit while a session is processing; the page is a live status
view. You wait for it to finish. Once it does, it takes you to the Editor, where
all the editing happens. If a session fails, the page changes into a failure card
with **Retry** and **Delete & start over** buttons (see Common Tasks).

## How To Delete

If a session has failed, the failure card offers **Delete & start over**. It asks
you to confirm, then marks the session as deleted (it stays recoverable from the
deleted-sessions area in Settings for a window of time) and returns you to the
Upload page. There is no delete button while a session is processing normally.

## Common Tasks

- **Watch a session finish.** Stay on the page. When the last step completes you
  are taken to the Editor automatically.
- **Check how far along it is.** Read the progress bar percentage, the elapsed
  timer, and the "remaining" estimate beside it.
- **See what has been produced so far.** The bottom panel counts segments,
  markers, and aligned-versus-total slides as they come in.
- **Retry a failed session.** On the failure card, click **Retry**. The pipeline
  restarts from the beginning and the page resumes tracking it.
- **Start over from scratch.** On the failure card, click **Delete & start over**,
  confirm, and re-upload.

## Troubleshooting

- **It says "Failed."** The card shows a plain-language reason and, for some
  causes, a tip. If the AI service was busy, wait a minute or two and click
  Retry. If the input was too large for the model, the tip suggests uploading
  audio instead of video, switching to a larger model in Settings, or using a
  shorter clip.
- **Progress looks stuck.** The page keeps checking in the background even if the
  live connection drops, so the bar should catch up on its own. If it sits at the
  same point for several minutes, refresh the page.
- **It says the AI service is busy or over quota.** These are usually temporary.
  Wait a short while and click Retry.
- **I saw a warning about alignment or truncated content, but it kept going.**
  Those are soft notices during processing, not failures — the session continues.
  Review the result in the Editor.
- **A poll-placement note appeared.** When polls are matched to slides during
  processing you get a brief notice of how many were placed. Nothing to do.

## FAQs

**How long does processing take?**
A typical hour of video takes about ten to fifteen minutes end to end. AI Mode is
slower than Default Mode, and a large slide deck adds a minute or two for slide
extraction.

**Why do the steps look different from last time?**
The steps shown match the way this particular session is being transcribed — AI
direct, AI enhanced, or standard — so different sessions can show different step
lists.

**What do the counts at the bottom mean?**
Segments is how many pieces of transcript have been produced, Markers is how many
slide-change markers were found, and Slides shows how many slides have been lined
up out of the total.

**It failed — can I just try again?**
Yes. Click Retry on the failure card to restart the pipeline. Retrying is built
to be safe to repeat.

**What happens when it finishes?**
The page automatically takes you to the Editor for that session.

## Permissions Required

You must be signed in to view the Processing page. The Retry and Delete actions
on the failure card are available to whoever is on the page; there are no
admin-only controls on this page.

## Source Verification
- **Files Used:** frontend/src/views/ProcessingView.vue, frontend/src/composables/useSyncController.ts, frontend/src/composables/useWsSubscriber.ts, frontend/src/router/index.ts, frontend/src/constants/help-content.ts, docs/help-center/articles.md, docs/help-center/faq.md
- **Components Used:** ProcessingView.vue ("Building your output" card, three step-sets — AI direct / AI enhanced / standard — template badge, progress bar with percent + elapsed + estimate, metrics panel for segments/markers/slides, failure card with Retry and Delete & start over)
- **APIs Used:** GET /v1/sessions/{id}, GET /v1/sessions/{id}/pipeline-config, POST /v1/sessions/{id}/retry, DELETE /v1/sessions/{id}, GET /v1/sessions/{id}/failure-reason, WS /v1/ws/sessions/{id} (processing_update, metrics_update, session_failed, slide_progress, template_autodetect, polls_autoplaced, align_gate_failed, gemini_loop_truncated)
- **Database Tables Used:** sessions (status / failure reason); processing metrics streamed over the session WebSocket
- **Permission Logic Used:** JWT presence to load (router beforeEach); no admin gate — Retry/Delete available to any signed-in viewer; delete confirms via confirm.open
- **Confidence Score:** High — the three step-sets, stage maps, progress/estimate math, metrics panel, auto-redirect to the Editor on ready, and the failure-card buttons + tips all read directly from ProcessingView.vue.
- **Evidence Links:** [frontend/src/views/ProcessingView.vue (step-sets)](../frontend/src/views/ProcessingView.vue#L39), [frontend/src/views/ProcessingView.vue (failure titles + tips)](../frontend/src/views/ProcessingView.vue#L199), [frontend/src/views/ProcessingView.vue (Retry)](../frontend/src/views/ProcessingView.vue#L246), [frontend/src/views/ProcessingView.vue (Delete & start over, confirm)](../frontend/src/views/ProcessingView.vue#L268), [frontend/src/views/ProcessingView.vue (auto-redirect on ready)](../frontend/src/views/ProcessingView.vue#L289)
