# Rounds Help

Rounds is the VIN transcript operations console. It turns Zoom rounds
recordings into auditable, searchable, CMS-ready transcripts via an
SOP-gated review pipeline.

## Common workflows

- **Upload a new session** — go to **Upload**, drag a Zoom recording
  (or chat / manifest / slides files) into the dropzone, set the
  Session Type if known, and confirm. The ingest pipeline transcribes,
  aligns to slides, and parks the session at the *prep* SOP stage.
- **Edit a transcript** — go to **Sessions**, click a session row,
  click **Open editor**. Inline-edit any segment by clicking it.
  Slide reassignment, speaker reassignment, polls, chat anchors,
  and per-segment QA flags all live in the editor.
- **Advance an SOP stage** — open a session, click its **SOP** tab,
  review the checks for the current stage, and click the
  **Advance** button when complete. The next assignee is notified
  via email if `SOP_DEADLINE_EMAIL_ENABLED` is true.
- **Customize email templates** — go to **Settings → Email →
  Open builder**. Edit per-Type or default-for-all-types templates
  for both stage-transition (entry) and deadline-overdue events.

## Keyboard shortcuts

- **⌘.** or **Ctrl+.** — Open the Tweaks panel (theme, density, etc.)
- **⌘K** or **Ctrl+K** — Open the command palette (route search)
- **Esc** — Close any open drawer / modal

## Where to find more

- API reference: open `/docs` for the FastAPI Swagger UI
- Project plans: see `docs/plans/` in the repo
- Audit history: every correction, reassignment, and SOP transition
  is recorded under **Audit** (per-session) or **/audit** (global).
