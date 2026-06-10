# Video & Synchronization

The video player in the Editor and how it stays in step with the transcript and
slides.

> Developer-facing twin: [../specs/video-sync.spec.md](../specs/video-sync.spec.md)

## What this gives you

**A video player in the Editor.** The left pane shows the recording with
play/pause and a scrubber. Drag the scrubber to move through the recording; the
scrubber marks where each slide begins.

**Click-to-seek from the transcript.** Click a segment and the video jumps to
that segment's start time. As the video plays, the current segment highlights in
the transcript and the slide rail scrolls to the slide that is on screen.

**Slide alignment.** During processing the system samples the video, detects
slide changes, and lines each transcript segment up with the slide that was
showing. That alignment is what powers the click-to-seek and the live
highlighting.

**Captions.** Toggle the CC button to show captions over the video. Captions are
generated from your corrected transcript and refresh whenever you edit a
segment, so they always match what you see. Filler words are preserved in
captions so they stay aligned to the audio.

## Known gaps

- **Playback speed control is fixed at 1×** — other speeds are not yet wired.
- **No fullscreen mode.**
- **No audio-only playback** — a video file is expected for the player.
- **No timeline zoom** — the scrubber maps the whole recording at a fixed scale.
- **No live position tooltip** while scrubbing.
