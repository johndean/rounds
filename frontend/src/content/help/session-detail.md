# Session Detail

The Session Detail page is the operations view of one session.

## What's here

### Top KPI strip
Segments / Sources / Words / something / Duration. Below the strip,
an alignment health indicator (e.g. "98% accuracy / 92 segments") and
any pipeline-stage warnings.

### Session Files
The files uploaded for this session (recording, chat log, slides,
manifest). Click **Add file** to upload new artifacts post-ingest.

### Stage Assignees
The 8 SOP stages, each with a person or group assigned. Click a row
to reassign inline. Changes are recorded in the audit ledger.

### Publishing links
URLs the session is linked to once published (Zoom recording, CMS,
podcast feed, etc.).

### Pipeline strip
Color-coded timeline showing which slides + segments are aligned,
flagged, or complete.

### Segment-level widgets row
- **Segment Confidence** — per-segment confidence histogram
- **Slide Assignment** — slides + their segment counts
- **Review Queue** — segments flagged for review
- **Chat Participants** (new in Phase 3, 2026-06-04) — list of
  speakers who posted in the live chat, with their message counts.
  Ordered by count desc.

## Common actions

- **Reassign a stage** — click any assignee row in Stage Assignees,
  pick a new person or group, save.
- **Retry ingest** — if AI Status is `failed`, an admin can click
  **Retry** to re-enqueue the pipeline.
- **Open editor** — top-right button takes you to the inline
  transcript editor.
- **Apply Type defaults** — if you change the Type, a banner
  appears letting you replace per-stage assignees with the Type's
  default matrix in one click.

## Where data comes from

Session shell from `GET /v1/sessions/{id}`. Stage assignees from
`/stage-assignees`. Chat participants from `/chat-participants`
(new endpoint, Phase 3).
