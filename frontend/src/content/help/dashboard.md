# Dashboard

The Dashboard is your at-a-glance view of the transcript pipeline.

## What's here

- **In Workflow / Processing / Published / Total** — counts of
  sessions in each lifecycle state across the system.
- **Your Queue** — the 3 most recently active sessions (global, not
  per-user yet — per-user queue is planned for Phase 7 broader).
- **Pipeline 1** (AI processing) — counts per processing stage of
  the ingest pipeline.
- **Pipeline 2** (SOP) — counts per SOP review stage. The **ATTN**
  badge lights orange when any session in a stage is past its SLA
  deadline. Click a stage tile to filter Sessions by that stage.
- **System overview** — KPIs for ingest volume + storage usage +
  classification health.
- **Stage SLA Performance** — per-stage average dwell time vs SLA.
- **Active flow alerts** — sessions that need human attention.

## What's missing here

- Per-user "my queue" view (planned, Phase 7 broader)
- Real-time updates (Pipeline 2 counts refresh on navigate-back)
