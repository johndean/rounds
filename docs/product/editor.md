# Editor

The workspace where you review and correct a transcript.

> Developer-facing twin: [../specs/editor.spec.md](../specs/editor.spec.md)

## What this gives you

**A three-pane layout.** Slides and the video on the left, the transcript in the
middle, reference and audit tools on the right.

**Inline text editing.** Click any segment to edit it, type your change, and
click Save (or Cancel to drop it). Every save is reversible — nothing is ever
lost.

**Full undo/redo with history.** The Audit tab on the right rail lists every
edit with who made it, when, and the before/after text. Undo moves the whole
session back one step; Redo moves it forward. History runs back to session
creation and is never deleted.

**Filter chips.** The colored chips above the transcript filter it down: Filler,
Punctuation, Drift, Low-confidence, and content categories like Medication, Name,
Number, and Date. Click a chip to isolate that class of segment; click again to
clear. The fastest way to sweep a transcript for one kind of issue at a time.

**Reference comparison.** A read-only speech-to-text reference sits alongside the
AI transcript so you can see exactly where the two disagree.

**Reassign segments to slides.** If a segment landed on the wrong slide, reassign
it from a grid of slide thumbnails.

**Speaker controls.** Rename, merge, reassign, and add speakers from the Speakers
panel — see [speakers.md](speakers.md).

**Chat & poll placement.** Drag chat and poll cards from the right rail onto the
transcript — see [polls-chat-resources.md](polls-chat-resources.md).

**Discrepancy review.** A dedicated view surfaces the segments the AI was least
sure about, sorted by priority — see [quality-ai.md](quality-ai.md).

**Export.** The Export menu downloads the finished transcript in any supported
format — see [workflow-and-export.md](workflow-and-export.md).

**Single-editor locking.** One person edits a session at a time. If a teammate
holds the editor you will see who; an admin can force-take control.

## Known gaps

- **No real-time collaboration** — editing is serialized via locks, not merged
  live.
- **No per-segment comment threads** — the audit shows who changed what, but
  there is no discussion thread on a segment.
- **No character-level diff view** — the audit shows before/after text, not
  inline highlighting of exactly what changed.
- **Find & Replace is present but bulk-apply is limited** — single-segment edits
  are fully supported; sweeping replacements are still maturing.
- **Slide focus does not persist across tab switches.**
