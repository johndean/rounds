# Upload & Processing

How recordings get into rounds.vin and become a first-pass transcript.

> Developer-facing twin: [../specs/upload-processing.spec.md](../specs/upload-processing.spec.md)

## What this gives you

**Direct-to-cloud upload.** On the Upload page you pick a recording and the file
uploads straight from your browser to cloud storage. Because the transfer is
direct, the speed is your local upload speed — large videos take a while, and the
progress bar runs to 100%. You can navigate away; the upload continues.

**Supported files.** Video and audio as MP4, MOV, or WAV; slide decks as PDF.
Other types are rejected up front. You can also bring a chat or poll log from the
original meeting.

**Two transcription modes.**

- **AI Mode** sends the media to Gemini and returns a richer transcript with
  speaker labels and slide markers. Use it for clinical content where attribution
  and slide alignment matter.
- **Default Mode** uses standard cloud transcription — faster and cheaper, but
  plainer.

**Prompt templates.** Each session uses a prompt template that tells the AI what
tone to use and how to handle filler words and slide markers. Admins maintain
templates under Settings; you choose one per session at upload.

**An automatic processing pipeline.** Once the upload completes, the system runs
a sequence of steps in the background — transcribe the audio, normalize the text,
sample the video for slide changes, find slide boundaries, and align the
transcript to the slides. The **Processing** page shows the current stage and a
live progress bar. A typical hour of video finishes in ten to fifteen minutes.

**When it's done, the Editor opens.** The session status flips to **ready**, the
SOP workflow begins, and you can start correcting.

**Add files after the fact.** You can attach a slide deck (or other source) to an
existing session from the Session Detail page; slide extraction runs and new
slides appear in the Editor's slide rail.

## Known gaps

- **No pause/resume** for in-flight uploads.
- **No slide-deck preview** before processing — upload goes straight to the
  queue.
- **Lenient chat/manifest validation** — a malformed chat or poll log may be
  silently skipped rather than flagged.
- **No automatic template detection** — you pick the prompt template manually.
- **Stuck-upload recovery is automatic but invisible** — if an upload hangs past
  five minutes a watchdog can re-queue it, but there is no manual "resume" button;
  refresh and retry, or ask an admin to re-ingest.
