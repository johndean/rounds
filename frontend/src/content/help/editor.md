# Transcript Editor

The editor is the heart of the copy-edit / medical-review / final-edit
workflow. Three-pane layout: slide rail (left) / transcript (middle) /
tabbed right rail (chat, polls, audit, etc.).

## Editing segments

- **Click a segment** to inline-edit. The textarea has browser
  spellcheck enabled (Phase 9.5 Layer 1).
- **Save** commits the edit and records a `text_edit` row in the
  correction ledger.
- **Cancel** discards.
- **Slide reassignment** — drag a slide from the left rail onto a
  segment, OR click the slide pill in the segment header.

## Speakers + Polls + Chat

- **Speakers** — the SpeakerEditPanel (top-right) lets you rename,
  merge, or reassign speakers across the session.
- **Polls + Chat** — right-rail tabs. Drag a poll or chat from
  the rail onto a segment to anchor it to that timestamp.

## Audio + Video

- **Click a segment timecode** to seek the player.
- Player position is persisted per session (browser local).

## Audit trail

The **Audit** tab on the right rail shows every correction for
this session, with undo/redo pointers. Global audit lives at
`/audit`.

## Find + replace

`Ctrl+F` opens find-in-transcript. Replace with `Ctrl+H`. Find/replace
operations are recorded as individual `text_edit` ledger rows.

## Where data comes from

Transcript from `GET /v1/sessions/{id}/segments`. Speakers from
`/speakers`. Chat from `/chat`. Polls from `/polls`. Corrections
from `/v1/sessions/{id}/corrections`.
