# Session Management

Finding, organizing, and managing the lifecycle of your sessions.

> Developer-facing twin: [../specs/session-management.spec.md](../specs/session-management.spec.md)

## What this gives you

**A list of every session.** The Sessions page shows each recording with its
name, processing status, current SOP stage, presenter, and quick counts. Search
by name and filter by status or stage to find what you need.

**A clear status lifecycle.** A session moves through:

| Status | Meaning |
|---|---|
| **uploading** | Files are transferring / awaiting ingest |
| **transcribing** | Speech-to-text is running |
| **normalizing** | Filler-word and terminology cleanup |
| **fusing** | Detecting slide boundaries |
| **aligning** | Matching transcript segments to slides |
| **ready** | Finished processing; the Editor is available |
| **complete** | Finalized |
| **failed** | Something went wrong — open it to see why |

> AI Mode can jump `uploading → ready` directly. `failed` and `complete` are
> terminal. "Archived" is **not** a status — it is the soft-delete (Trash) flag;
> "published / sent to CMS" is the SOP `cms`/`complete` stage, not a session status.

**A Session Detail page.** One place for everything about a recording: its source
files, slides, AI status, key counts (segments, words, confidence, coverage,
duration), SOP stage assignments, and quick links to the Editor and exports. Edit
the title and metadata inline.

**Stage assignments.** Every session carries the eight SOP stages, each with an
assignee that defaults from the session type and can be overridden per session.

**Soft-delete, restore, and purge (admins).** Admins can soft-delete a session
(it moves to Trash but keeps its data), restore it later, or permanently purge
it. Purge cannot be undone, so the system confirms twice. Soft-delete is limited
to admins and one external partner account.

**Editing locks.** While one person edits a session, others cannot edit it
concurrently; an admin can force-take a lock if needed.

**Rate-limit protection.** A safety limit caps how many sessions a single user
can process at once, which is why the app may briefly say "Slow down."

## Known gaps

- **No bulk session actions** in the UI — soft-delete, restore, and reassign are
  one session at a time.
- **No session templates** beyond session-type defaults.
- **No session-level version history** — the per-correction audit covers edits,
  but you cannot snapshot and roll back a whole session.
- **No per-field session audit** — the audit trail covers transcript corrections,
  not every metadata field change.
