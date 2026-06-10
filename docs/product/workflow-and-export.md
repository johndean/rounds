# Workflow & Export

How a transcript moves from "ready" to "published," and how you get the finished
file out of rounds.vin.

> Developer-facing twin: [../specs/workflow-and-export.spec.md](../specs/workflow-and-export.spec.md)

## What this gives you

**A fixed review workflow (SOP).** Every session walks through the same stages
in order: **Prep → Copy Draft → Medical → Copy Final → CMS → Captions → QA →
Complete.** Each stage has an owner and an SLA in hours. The current owner clicks
Done to advance the session to the next stage.

**Per-session stage assignments.** Defaults come from the session type, but an
admin can reassign the person on any stage from the Session Detail page. The SOP
page shows the current owner and status of every stage at a glance.

**Deadline reminders.** When a stage runs past its SLA, the assignee gets a
reminder email on the next hourly check — capped at one email per stage per day,
so nobody gets spammed.

**Exports in six formats.** From the Export menu in the Editor you can download:

| Format | Best for | Filler words |
|---|---|---|
| **docx** | Word document for editing/review | Removed for readability |
| **txt** | Plain text | Removed |
| **srt** | Subtitles | Kept (stay aligned to audio) |
| **vtt** | Web captions | Kept |
| **html** | Self-contained styled page | Removed |
| **zip** | Everything at once + original media | Both — clean docx *and* full captions |

Every export is generated fresh from the current transcript, so it always
reflects your latest edits. Unresolved speakers appear as **(Unknown)** so gaps
are easy to spot.

**Stage advancement is guarded.** A session can only move through legal
transitions (uploading → transcribing → normalizing → fusing → aligning → ready → complete; failed is reachable from any active stage).
You cannot accidentally skip or reverse the lifecycle.

## Known gaps

- **No bulk export.** You export one session at a time; there is no "export all
  selected" action.
- **No custom export templates per download.** Formatting is fixed per format;
  prompt/style templates are chosen at upload, not at export.
- **Caption burn-in (text overlaid on the video file) is not wired** in the UI.
- **No stage-level SLA trend reporting** — you see whether a stage is overdue,
  not historical dwell-time charts (see [reporting.md](reporting.md)).
