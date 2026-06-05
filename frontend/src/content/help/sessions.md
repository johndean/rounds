# Sessions

The Sessions table lists every session in the system, sortable and
filterable by the chips above the table.

## What's here

- **Code** — the operator-assigned session code (e.g. `010525_Lykins`).
- **Session** — the title (cascading from `title_long` → `title_short`
  → `title`). Click a row to open the **Session Detail** page.
- **AI Status** — ingest pipeline state (`pending` / `processing` /
  `ready` / `failed`). Failed sessions can be rescue-retried from
  the detail page.
- **SOP** — current SOP stage. Click a row's SOP cell to jump
  directly to the SOP tab.
- **Segs** / **Words** — segment + word counts for transcripts past
  the alignment step.

## Common actions

- **Filter** — click the chip strip at top to scope by status,
  stage, or AI processing state.
- **Export CSV** — currently not wired (planned).
- **Sort** — click column headers.
- **Open editor** — click any session row, then click "Open editor"
  on the detail page.

## Where data comes from

The list is populated from `GET /v1/sessions`. The filter chips
build query-string filters that the backend honors. Sessions are
soft-deleted on `DELETE /v1/sessions/{id}` (admin-only, with a
30-day recovery window via Settings → Deleted sessions).
