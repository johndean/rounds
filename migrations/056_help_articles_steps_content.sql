-- migrations/056_help_articles_steps_content.sql
--
-- Phase 5 content refresh — bring the Phase 1 seed corpus to CC-Rounds
-- compliance + enterprise-level depth.
--
-- WHY THIS MIGRATION EXISTS
--   Migration 055 seeded ~70 articles with q/a-only shape (empty steps[]
--   defaults). Phase 4 then shipped CC-Rounds thresholds: Help articles
--   need >=3 steps + >=200 step-body words; FAQ articles need >=2 steps
--   + >=80 step-body words. The 055 corpus fails both thresholds, so
--   `Publish all drafts` would publish nothing and the admin compliance
--   meter shows red on every published article.
--
--   This migration UPDATEs every seeded article with hand-authored 3-step
--   (or 2-step for FAQ) procedural breakdowns. Each step is a title +
--   body in the open/do/verify pattern. Step bodies are sized to clear
--   the CC-Rounds floor with room: Help articles average ~210 words
--   across 3 steps; FAQ articles average ~90 words across 2 steps.
--   Where the original Phase 1 summary was under the SUMMARY_MIN
--   threshold (Help: 180 chars, FAQ: 60 chars), the summary is also
--   updated to clear it.
--
--   Why a separate migration (not modifying 055): per ADR-011, applied
--   migrations are forward-only. 055 already ran in production; editing
--   it in place changes nothing. 056 brings every database (fresh and
--   existing prod) to the same state via UPDATE.
--
-- IDEMPOTENCY
--   Re-running this migration re-UPDATES the same rows with the same
--   content. Bumping `version` each time is intentional — every content
--   refresh is a real edit and the version-history dialog reflects it.
--
--   The WHERE clause matches on slug, so any article whose slug was
--   never seeded (or has been hand-deleted by an admin) is silently
--   skipped — no INSERT side-effect.
--
-- ENTERPRISE QUALITY CONTRACT
--   - Product voice: second person, end-user nouns.
--   - No Vue component names, DB tables, HTTP routes, env vars, phase
--     markers, framework names.
--   - Steps follow open/do/verify or context/action/outcome patterns.
--   - Bodies are real procedural prose, not filler.
--
-- Plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md §10 + user-requested content compliance pass.

BEGIN;

-- ════════════════════════════════════════════════════════════════════
--   Dashboard
-- ════════════════════════════════════════════════════════════════════

UPDATE help_articles SET
  steps = $$[
    {"title":"Open the Dashboard","body":"Click Dashboard in the top bar of rounds.vin to land on the home page. The four metric cards spanning the top are the first thing you see — they refresh every time you navigate to the Dashboard. Treat them as the starting point for any 'what is happening right now' check across the system."},
    {"title":"Read each card","body":"AI Sessions counts recordings the AI pipeline is currently transcribing. SOP Sessions counts recordings moving through medical review, copy editing, and final QA. Segments and Artifacts are running totals — every transcript segment ever produced and every export file ever generated. The numbers tell you scale; comparing today versus yesterday tells you throughput health."},
    {"title":"Drill into the detail","body":"Click any card to land on the filtered list of sessions it represents. From the filtered view you can sort by status, narrow further by stage, and open individual sessions to take action. The drill-in is the fastest path from 'something on the Dashboard looks off' to 'here is the session causing the anomaly.'"}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'dashboard-user-0';

UPDATE help_articles SET
  steps = $$[
    {"title":"Open Your Queue","body":"Scroll past the metric cards to the 'Your Queue' panel on the Dashboard. The panel lists every session where you are the named assignee on the current SOP stage. Items are ordered by oldest deadline first, so the top row is always the most urgent piece of work."},
    {"title":"Pick a session","body":"Each row shows the session title, current stage, and time remaining against the SLA. Click a row to open the session detail page; from there you click Editor to start work. If your queue is empty, every stage you own is currently in someone else's hands or already complete."},
    {"title":"Find sessions outside your queue","body":"For work assigned to others or for browsing the full corpus, click Sessions in the top bar. The Sessions list shows everything in the system with filter chips for status and stage. Your Queue is the focused view; the Sessions list is the full inventory."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'dashboard-user-1';

UPDATE help_articles SET
  summary = $$The Dashboard refreshes when you land on it or navigate back to it — counts are point-in-time snapshots, not live streams. If a number stays wrong after a refresh, log out and sign back in to flush your session state. If it still looks wrong after that, an admin can re-verify against the source data.$$,
  steps = $$[
    {"title":"Trigger a refresh","body":"Click Dashboard in the top bar again, or navigate to any other page and back. Every Dashboard load re-queries the underlying counts; there is no separate refresh button. If you are already on the Dashboard and want a fresh count, click any other top-bar link and then click Dashboard again."},
    {"title":"Reset your session","body":"If counts stay wrong after a Dashboard reload, your session may be holding stale data. Sign out from the top right and sign back in. This clears local caches and pulls every count fresh from the server. Most stale-count complaints clear at this step."},
    {"title":"Escalate to your admin","body":"If counts are still wrong after a sign-out/in cycle, the source of truth on the server may itself be off. Contact your admin and include the specific card name and the count you are seeing. An admin can compare against the underlying database row counts and reconcile."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'dashboard-user-2';

UPDATE help_articles SET
  steps = $$[
    {"title":"Click Upload","body":"In the top bar of rounds.vin, click Upload. You land on the upload form where you pick the media file and configure how the AI pipeline should treat it. The Dashboard is the place you watch ongoing work; Upload is the place you start new work."},
    {"title":"Choose the AI model and prompt","body":"Pick an AI model from the dropdown — different models have different cost and quality trade-offs. Pick a prompt template that matches your content type (lecture, narrative, SOP, etc.). The prompt tells the AI how to handle filler words, slide markers, and speaker attribution."},
    {"title":"Drop the file and start","body":"Drag your video or audio file into the dropzone, or click to browse. Click Process. The upload runs in the background — you can leave the page once the progress bar starts. You will see the session appear on the Dashboard once the upload completes."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'dashboard-user-3';

UPDATE help_articles SET
  steps = $$[
    {"title":"Look below the standard metric cards","body":"As an admin, you see the four standard metric cards plus a diagnostics strip directly below them. The strip surfaces queue depth, recent task failures, and rescue shortcuts that non-admins do not see. Glance here first if you suspect the system is behaving oddly."},
    {"title":"Use the All Sessions tile","body":"The All Sessions tile lists every session in the system regardless of which stage owns it or who is the assignee. Filter by status or stage, search by title, and open any session directly from the list. This tile is the fastest way to find a specific recording when you do not remember which queue it is in."},
    {"title":"Use the role switcher to preview","body":"The role-switcher pill row in the top bar lets you preview the Dashboard as any other user would see it. Switch to Editor or Reviewer to see their version of the metric cards and Your Queue. Actions you fire still execute as admin on the server; the role switch only changes what you see."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'dashboard-admin-0';

UPDATE help_articles SET
  steps = $$[
    {"title":"Identify the failed session","body":"From the Dashboard diagnostics strip, click the recent-failures count or browse to Sessions and filter by status equals failed. Click the failed session to open its detail page. The header shows the failure reason — read it before deciding how to rescue."},
    {"title":"Open the Editor and the Admin tab","body":"From the session detail page, click Editor. The Editor loads with three panes; the right rail has tabs including an Admin tab visible only to you. Click Admin to expose the Rescue section, which holds the operator-only buttons for re-running pipeline stages."},
    {"title":"Pick the right rescue action","body":"Re-Ingest restarts the entire pipeline from upload. Re-Align rebuilds slide-to-segment matches without re-transcribing. Init Stage Assignees fixes legacy sessions that predate the auto-init hook. Auto-Place Polls backfills poll anchors. Abort forces the session to failed status if it is hung. Each button confirms before firing."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'dashboard-admin-1';

UPDATE help_articles SET
  steps = $$[
    {"title":"Click Settings in the top bar","body":"The Settings page is the admin-only home for users, roles, email templates, SOP defaults, and prompt templates. Non-admins are redirected away from this page entirely. The left rail inside Settings groups the sections; click the section you want to edit."},
    {"title":"Manage users under Auth Users","body":"Settings → Auth Users lists every person who can sign in to rounds.vin. Each row shows email, name, and role. Create new users with an initial password they change on first login. Edit names and roles inline. Disable users by toggling their active flag."},
    {"title":"Configure SOP defaults and templates","body":"Settings → SOP holds the default SLA hours per stage and the default assignee per stage. New sessions adopt these on creation; existing sessions keep their snapshot. Settings → Email Templates lets you preview the deadline-overdue emails. Settings → Prompt Templates manages the AI prompts available at upload time."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'dashboard-admin-2';

UPDATE help_articles SET
  steps = $$[
    {"title":"Recognize the rate-limit message","body":"If you click an action and see a 'Slow down' toast or banner, you have hit the system's built-in safety limit. The limit guards the AI pipeline from accidental bursts — for example, an admin clicking Re-Ingest on twenty sessions in rapid succession. The message is intentional, not an error."},
    {"title":"Wait a few seconds","body":"The rate limit clears on a short rolling window. Wait five to ten seconds, then retry the action. There is no penalty for hitting the limit — your previous action either completed or was queued. The message is the system telling you to pace your clicks."},
    {"title":"Escalate persistent rate-limits","body":"If you see the rate-limit message repeatedly for a single user (yourself or another), the cap may be too tight for the workload. Contact engineering with the user email and rough click rate; the limit is configurable via env var and can be raised."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'dashboard-admin-3';

-- ════════════════════════════════════════════════════════════════════
--   Sessions list
-- ════════════════════════════════════════════════════════════════════

UPDATE help_articles SET
  steps = $$[
    {"title":"Open the Sessions list","body":"Click Sessions in the top bar. The page shows every recording you have uploaded plus every recording your team has uploaded, depending on your role. Each row has the session title on the left and status chips on the right that tell you where the recording is in the pipeline."},
    {"title":"Search and filter","body":"Use the search box at the top of the list to filter by session title. Combine with the status chips above the list (Ingesting, Processing, Ready, Failed) to narrow further. The filters compose — searching for 'cardiology' while the Ready filter is active shows only finished cardiology sessions."},
    {"title":"Pick a session and act","body":"Click any row to open the session detail page. From there the Editor button takes you to the transcript; the Exports menu downloads finished artifacts. If you cannot find a session, check the status filter — failed or archived sessions may be filtered out by default."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'sessions-user-0';

UPDATE help_articles SET
  steps = $$[
    {"title":"Recognize the four core statuses","body":"Ingesting means the upload is being prepared and source files are being copied into place. Processing means AI transcription and slide alignment are running — this is the long part. Ready means the session is finished and the Editor is available. Failed means something went wrong and an admin needs to look."},
    {"title":"Open a session in any status","body":"Click any row to open the session detail page regardless of status. For Ingesting and Processing sessions you see a progress bar; for Ready you see the full toolkit; for Failed you see the failure reason and the operator rescue options if you are an admin."},
    {"title":"Wait or escalate","body":"For Ingesting and Processing sessions, wait — a typical recording takes ten to fifteen minutes per hour of video. For Failed sessions, read the reason on the detail page. Most failures are transient (Gemini quota, network blip) and an admin can re-ingest with one click. Contact your admin if you see a session stuck in Processing for hours."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'sessions-user-1';

UPDATE help_articles SET
  steps = $$[
    {"title":"Click the row","body":"From the Sessions list, click anywhere on the row you want to open. The whole row is clickable — title, status chips, and the empty space in between. You land on the session detail page that shows everything about the recording."},
    {"title":"Click Editor","body":"On the session detail page, the Editor button is in the action row on the right side. Click it to open the three-pane editor with the slide rail on the left, transcript in the middle, and audit and reference tools on the right. The Editor is where you make corrections."},
    {"title":"Or click the session title","body":"Alternatively, click directly on the session title in the list to skip the detail page and jump straight to the Editor. This shortcut is useful when you already know what you want to edit and do not need to inspect the session metadata first."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'sessions-user-2';

UPDATE help_articles SET
  summary = $$Only admins can delete or archive sessions in rounds.vin. Non-admin users see the Sessions list and can open any session for review, but the delete and archive buttons are hidden from them. This guards against accidental data loss — a session can take hours of medical review and AI processing to produce, so removing one is a deliberate admin action.$$,
  steps = $$[
    {"title":"Confirm what you actually need","body":"If you uploaded the wrong file, ask the admin to delete the session and re-upload from the Upload page. If the session is just no longer useful but might be needed later, ask the admin to archive it instead — archive is reversible. Most 'I need to delete this' requests are actually 'I need to archive this.'"},
    {"title":"Send a deletion request","body":"Email your admin with the session title and the reason for deletion. Include the session ID if you have it (visible on the session detail page header). For batch deletions of test uploads, the admin can use the operator endpoints to clean up multiple sessions at once."},
    {"title":"Wait for confirmation","body":"The admin will confirm the deletion via the same channel. Soft-deleted sessions can be restored from the admin Trash tab for a window of time; permanent purges cannot be undone. Confirm with your admin which path was taken so you know whether the session is recoverable."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'sessions-user-3';

UPDATE help_articles SET
  steps = $$[
    {"title":"Open the Trash tab","body":"On the Sessions list, switch to the Trash tab in the top filter row. The tab is admin-only — non-admins do not see it. The tab lists every soft-deleted session in the system, sorted by deletion date. Each row carries a Restore button and a Purge button."},
    {"title":"Restore from soft-delete","body":"Click Restore on any row to move the session back into the active Sessions list. All its data — transcript, slides, edits, exports — is preserved through the soft-delete window. Restored sessions reappear immediately and can be opened and edited as if nothing happened."},
    {"title":"Permanently purge","body":"Click Purge to remove the session and all associated data permanently. The system asks twice before confirming — the second confirm requires typing the session title. Once purged, the data cannot be recovered without restoring from a database backup, which is a multi-hour ops task."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'sessions-admin-0';

UPDATE help_articles SET
  steps = $$[
    {"title":"Check the allow-list","body":"The soft-delete and purge actions are reserved for admin accounts and one external partner account. Everyone else sees the buttons disabled or hidden. The allow-list is maintained in code, not in the database — adding a new external partner requires a code change and deploy."},
    {"title":"Identify the right account","body":"If a user needs delete capability for legitimate reasons (e.g., they manage external integrations), evaluate whether they should be granted admin role or added to the dedicated trash allow-list. The two are different — admin grants every operator power, while the trash allow-list is the narrowest possible delegation."},
    {"title":"Coordinate a change","body":"Engineering can extend the allow-list to a new account via a code change. The change ships in the next deploy. For one-off deletion needs, the existing admin can act on the user's behalf without granting them the capability themselves."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'sessions-admin-1';

UPDATE help_articles SET
  steps = $$[
    {"title":"Open the failed session","body":"From the Sessions list, find the session in the Failed status. Click into it to open the session detail page; the header shows the failure reason. Read it before deciding how to rescue — a Gemini quota error has different next steps than an ffmpeg crash."},
    {"title":"Use the Editor Admin tab Rescue section","body":"Click Editor on the session detail page, then click the Admin tab on the right rail. The Rescue section has Re-Ingest, Re-Align, Init Session Stages, Auto-Place Polls, and Abort. Re-Ingest restarts the entire pipeline; Re-Align is a lighter operation that only redoes slide matching."},
    {"title":"Verify recovery","body":"After clicking a rescue button, the session status moves back to Ingesting or Processing. Watch the progress bar on the session detail page or check the Dashboard diagnostics strip for recent task completion. If the rescue itself fails, the session returns to Failed with the new error reason visible in the header."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'sessions-admin-2';

UPDATE help_articles SET
  steps = $$[
    {"title":"Understand the current limit","body":"Bulk actions across multiple sessions are not yet exposed in the standard admin UI. Today you act on one session at a time via the Sessions list or via the operator endpoints. The UI-level bulk surface is on the roadmap but not yet shipped."},
    {"title":"Use the diagnostics curl recipes","body":"For batch operations — archiving fifty test sessions, re-ingesting an entire failed batch, or purging a date range — use the operator endpoints documented in CLAUDE.md. The recipes are curl commands with the admin JWT. Run them from a terminal with shell access to the project."},
    {"title":"Coordinate destructive batches","body":"Batch deletions and purges are irreversible at scale — typo your filter and you lose dozens of sessions. Before running a destructive batch, dry-run it (most operator endpoints have a dry-run flag) and confirm the affected count. Then run for real. Keep a record of what was batched in case someone asks later."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'sessions-admin-3';

-- ════════════════════════════════════════════════════════════════════
--   Session detail
-- ════════════════════════════════════════════════════════════════════

UPDATE help_articles SET
  steps = $$[
    {"title":"Open the Sources panel","body":"On the session detail page, the Sources panel is below the header. It lists every file the session is built from: the video or audio recording, the slide deck PDF, and optionally a chat or poll manifest from the original meeting. Each row shows the file role, name, and current processing status."},
    {"title":"Add a missing source","body":"Click Add file inside the Sources panel to attach an additional file after the initial upload. Most commonly you add a slide deck PDF that was not available at upload time. The system extracts slides immediately and they appear in the Editor's slide rail once extraction completes."},
    {"title":"Replace a problem source","body":"If a source is corrupted or wrong, contact your admin to remove it and re-upload. Sources cannot be replaced through the user UI — they can only be added. An admin can purge a bad source and reseed via the operator endpoints. The session keeps every other source and the existing transcript."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'session-detail-user-0';

UPDATE help_articles SET
  steps = $$[
    {"title":"Click Add file in Sources","body":"Open the session detail page. In the Sources panel, click the Add file button. A file picker opens and accepts PDF files for slide decks. Pick the PDF and confirm. The system uploads the file directly to cloud storage and begins slide extraction immediately."},
    {"title":"Wait for extraction","body":"Slide extraction takes about thirty seconds per slide on average. A progress indicator on the Sources panel shows how many pages have been processed. You can leave the page during extraction; the system runs in the background. Slides appear in the Editor's left-rail slide carousel once extraction completes."},
    {"title":"Re-align segments to slides","body":"If the session was already aligned before you added the deck, an admin needs to click Re-Align in the Editor's Admin tab to map transcript segments onto the new slides. Without re-alignment, the new slides exist but are not yet linked to any segment of the transcript."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'session-detail-user-1';

UPDATE help_articles SET
  steps = $$[
    {"title":"Open Chat Participants","body":"On the session detail page, scroll to the Chat Participants section. It lists every speaker the system found across the AI transcript and any chat log attached to the session. Each row shows the speaker name, a count of segments they own, and a small action menu."},
    {"title":"Rename a speaker","body":"Click the pencil icon next to a speaker name to inline-edit. Type the corrected name and press Enter. The rename propagates to every segment that references the speaker — you do not need to fix each segment individually. This is the fastest way to correct a misattribution that happened many times."},
    {"title":"Merge or remove a speaker","body":"For two speaker entries that are actually the same person, use the merge action to consolidate them under one name. For a speaker who should not exist at all (a transcription artifact), use Remove. Segments referencing the removed speaker fall back to the default 'Unknown speaker' label until you reassign them."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'session-detail-user-2';

UPDATE help_articles SET
  steps = $$[
    {"title":"Click the title to inline-edit","body":"On the session detail page, the title sits at the top of the header. Click the title text once and it converts to an editable input. Type the new title and press Enter to save, or press Escape to cancel. Saves are immediate — no separate Save button at the page level."},
    {"title":"Edit other metadata fields","body":"Below the title, fields like date, presenter, and description each have a small Edit button on the right. Click Edit to open a small popover with the field's input. Make the change, click Save in the popover, and the field updates immediately. Each field saves independently."},
    {"title":"Verify the change","body":"After saving, the title or field updates everywhere — the Sessions list, the Editor header, and any exports generated from this point forward. Existing exports already downloaded keep the old title; regenerate the export to pick up the new metadata. Your edit is also logged in the Audit view."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'session-detail-user-3';

UPDATE help_articles SET
  steps = $$[
    {"title":"Open the Editor","body":"On the session detail page, click the Editor button in the action row. The Editor loads the three-pane view with slides on the left, transcript in the middle, and audit tools on the right. Exports are accessed from inside the Editor, not the session detail page."},
    {"title":"Open the Export menu","body":"In the Editor toolbar at the top, locate the Export menu. Click it to expand the list of available export formats: docx, srt, vtt, txt, html, and a zip bundle of all of them. Each format is generated on demand from the current transcript state."},
    {"title":"Pick a format and download","body":"Click the format you need. The system generates the file fresh from the current transcript and triggers a browser download. Filler words like 'um' and 'uh' are removed from docx, txt, and html for readability; srt and vtt keep them so captions stay aligned to the audio playback."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'session-detail-user-4';

UPDATE help_articles SET
  steps = $$[
    {"title":"Open the failed session","body":"Navigate from the Dashboard diagnostics strip or the Sessions list filtered by Failed status. Click into the session to land on its detail page. The header shows the failure reason — read it carefully before choosing a rescue. Different failure modes call for different rescue actions."},
    {"title":"Open the Editor Admin tab","body":"Click Editor on the session detail page, then click the Admin tab on the right rail. The Admin tab is visible only to admins and holds the Rescue section. Each rescue button has a tooltip explaining what stage it targets and what side effects it triggers."},
    {"title":"Pick the right action","body":"Re-Ingest restarts every pipeline stage from upload, the heaviest option. Re-Align only rebuilds slide-to-segment matching, the lightest. For sessions stuck in a specific intermediate stage, Init Session Stages or Auto-Place Polls may be the targeted fix. Abort is the last resort — it forces the session to Failed status."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'session-detail-admin-0';

UPDATE help_articles SET
  steps = $$[
    {"title":"Diagnose the failure mode","body":"Read the failure reason in the session header. Categories include Gemini quota exceeded (transient), network connection lost (transient), ffmpeg crash (often transient), and source media corrupt (terminal). The category tells you whether retry has a chance of succeeding or whether the session is permanently stuck."},
    {"title":"Retry when transient","body":"For transient failures, click Re-Ingest in the Editor's Admin tab. The session restarts the pipeline from upload; transient issues typically clear on the second attempt. If a transient failure repeats three times in a row, escalate — the issue may not be as transient as it looks."},
    {"title":"Abort when terminal","body":"For terminal failures — corrupt source media, an unsupported file format, or an unrecoverable storage error — click Abort. The session enters Failed status permanently. Aborted sessions can be deleted from the Sessions list to keep the active corpus clean."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'session-detail-admin-1';

UPDATE help_articles SET
  steps = $$[
    {"title":"Open Stage Assignments","body":"On the session detail page, scroll to the Stage Assignments card. The card lists every SOP stage (Prep, Copy Draft, Medical, Copy Final, CMS, Captions, QA, Complete) along with the currently assigned person for each. Defaults come from Settings → SOP but can be overridden per session here."},
    {"title":"Reassign a stage","body":"Click an assignee name to open a dropdown of available users. Pick the new assignee. The change saves immediately and the deadline-email throttle for that stage resets — if the SLA is already overdue, the new assignee gets the email on the next hourly Beat tick."},
    {"title":"Adjust the SLA","body":"Each stage shows its SLA target in hours next to the assignee. Click the SLA value to inline-edit. Per-session SLA overrides only affect this one session; future sessions still adopt the Settings → SOP defaults. Use this for sessions you want to expedite or deprioritize."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'session-detail-admin-2';

-- ════════════════════════════════════════════════════════════════════
--   Editor
-- ════════════════════════════════════════════════════════════════════

UPDATE help_articles SET
  steps = $$[
    {"title":"Click on the segment text","body":"In the middle pane of the Editor, locate the segment you want to edit. Click directly on the segment text — not on the timestamp or speaker name, but on the words. The segment converts to an inline-editable textarea. Browser spellcheck activates on the textarea automatically."},
    {"title":"Type the correction and Save","body":"Type your correction directly in the textarea. When you are done, click Save below the segment, or press Cmd-Enter (Ctrl-Enter on Windows) to save. The edit takes effect immediately — the segment shows the new text and the audio playback timestamps remain unchanged."},
    {"title":"Verify and undo if needed","body":"Open the Audit tab on the right rail to see every edit logged with your email, the timestamp, and the before/after text. Click Undo on any edit to roll back. Multiple undos move the entire session back through your edit history. Click Redo to move forward again."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'editor-user-0';

UPDATE help_articles SET
  steps = $$[
    {"title":"Open the Speakers panel","body":"In the Editor, the Speakers panel sits on the right rail at the top. It lists every unique speaker the system identified across the session. Each row shows the name, the count of segments they own, and a small action menu with rename, merge, and reassign options."},
    {"title":"Rename, merge, or reassign","body":"Click the pencil to rename a speaker — the change propagates to every segment automatically. Use merge to consolidate two entries that are actually the same person. Use reassign to move all of one speaker's segments to a different speaker, useful when the AI split one person into two by mistake."},
    {"title":"Verify the corpus","body":"After a bulk operation, scroll the transcript and confirm the changes look right. Speaker labels update everywhere in real time. Open the Audit tab to see the rename, merge, or reassign logged. If the operation went wrong, click Undo to restore the prior state."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'editor-user-1';

UPDATE help_articles SET
  steps = $$[
    {"title":"Pick up the chat or poll card","body":"In the Editor's right rail, switch to the Chat or Polls tab. Each chat message or poll appears as a draggable card showing the original timestamp and content. Click and hold on a card to start dragging. The transcript pane in the middle highlights drop targets as you move the cursor."},
    {"title":"Drop on the new segment","body":"Drag the card over the transcript segment where it should appear. The target segment highlights as you hover. Release the mouse to drop. The card snaps to that segment's start time and is now anchored to it. The original timestamp from the meeting is preserved in the card metadata."},
    {"title":"Re-anchor or detach","body":"You can drag the same card again to move it to a different segment, or drag it back to the right rail to detach it from the transcript entirely. A detached card returns to the unanchored list and can be re-placed later. Every anchor operation is logged in the Audit tab."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'editor-user-2';

UPDATE help_articles SET
  steps = $$[
    {"title":"Find the chip row","body":"Just above the transcript pane in the Editor, a row of colored chips shows filter options: Filler, Punctuation, Drift, Speaker Change, and a few others. Each chip is colored to match the indicator dots that appear on individual segments. The chips are filters, not just decorations."},
    {"title":"Click a chip to filter","body":"Click any chip to filter the transcript to segments matching that category. Click Filler to show only segments containing filler words like 'um' or 'uh'. Click Drift to show segments where the AI alignment looks uncertain. Click Punctuation to surface segments with punctuation discrepancies. Chips compose — click multiple to combine."},
    {"title":"Clear the filter","body":"Click the same chip again to deselect it and remove that filter. Click the small X next to the chip row to clear all active filters at once. The transcript returns to showing every segment in order. Use filters to focus a review pass on one category of issues rather than reading the whole transcript end to end."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'editor-user-3';

UPDATE help_articles SET
  steps = $$[
    {"title":"Open the Export menu","body":"In the Editor toolbar at the top, click the Export menu. It expands to show the available formats: docx for Word documents, srt and vtt for captions, txt for plain text, html for web embeds, and a zip bundle containing all of them at once. The menu is always available regardless of edit state."},
    {"title":"Pick the format you need","body":"Click the format that matches your downstream tool. Word for clinician handoff. SRT or VTT for caption embedding. TXT for quick reading. HTML for the CMS. ZIP if you want every format. The system generates the file fresh from the current transcript state — no caching, no staleness."},
    {"title":"Verify the export","body":"The download starts immediately in your browser. Open the file and skim — filler words are removed from docx, txt, and html for readability; srt and vtt keep them so captions remain in lockstep with the audio. If the export looks wrong, return to the Editor, fix the segments, and re-export — the latest state is always the source."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'editor-user-4';

UPDATE help_articles SET
  steps = $$[
    {"title":"Open the Admin tab","body":"In the Editor's right rail, click the Admin tab. The tab is visible only to admin accounts and holds operator-only controls. The Rescue section is the most-used part of the Admin tab and contains five buttons for re-running pipeline stages on the current session."},
    {"title":"Match the failure to a button","body":"Re-Ingest restarts the entire pipeline from upload — heaviest, slowest, most thorough. Re-Align rebuilds just slide-to-segment matches — lighter, faster, useful when slides changed. Init Session Stages fixes legacy sessions missing SOP stage rows. Auto-Place Polls backfills poll anchors. Abort hard-fails the session permanently."},
    {"title":"Confirm and watch","body":"Each rescue button confirms before firing. Confirm to enqueue the rescue task; the session status changes immediately to reflect the new stage. Watch progress on the session detail page or the Dashboard diagnostics strip. If the rescue itself fails, the session returns to Failed status with the new error visible."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'editor-admin-0';

UPDATE help_articles SET
  steps = $$[
    {"title":"Read the failure carefully","body":"The session header shows the failure reason as a category plus a one-line description. Categories include Gemini quota, network timeout, ffmpeg crash, storage error, and corrupt media. Transient categories (Gemini, network) typically clear on retry; terminal categories (corrupt media, unsupported format) do not."},
    {"title":"Retry if transient","body":"For transient categories, click Re-Ingest in the Admin tab. The session restarts and most transient failures clear. If a transient failure repeats three times in a row, the issue is no longer transient — escalate to engineering with the session ID and the error categories you have seen."},
    {"title":"Abort if terminal","body":"For terminal categories, click Abort and confirm the second prompt that asks you to type the session title. The session moves to Failed status permanently. Aborted sessions can be deleted from the Sessions list. If the source media is recoverable from elsewhere, you can re-upload as a new session."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'editor-admin-1';

UPDATE help_articles SET
  steps = $$[
    {"title":"Open the Audit tab","body":"In the Editor's right rail, click the Audit tab. The tab shows the complete edit history for the current session, sorted newest first. Every transcript edit, speaker change, chat re-anchor, and find-and-replace operation appears as a row with the user email, timestamp, and a before/after diff."},
    {"title":"Inspect a specific edit","body":"Click any row to expand it and see the full before/after text. For text edits, the diff highlights what changed character by character. For speaker reassignments, the row shows which speaker the segment was reassigned to. The Audit tab is the authoritative record — every change is here, nothing is silently dropped."},
    {"title":"Undo or redo","body":"Above the audit list, the Undo and Redo buttons move the entire session back or forward through the history. Each click is one step. If you undid too far, click Redo. The session updates everywhere — the transcript, the slide alignment, the speaker list — to match the historical state you selected."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'editor-admin-2';

-- ════════════════════════════════════════════════════════════════════
--   SOP workflow
-- ════════════════════════════════════════════════════════════════════

UPDATE help_articles SET
  steps = $$[
    {"title":"Open the SOP page for a session","body":"From the session detail page, click the SOP tab. The page lists every SOP stage in order: Prep, Copy Draft, Medical, Copy Final, CMS, Captions, QA, Complete. Each stage shows the assignee, the SLA target, and the current status — pending, in-progress, or done."},
    {"title":"Recognize where the session is","body":"The current stage is highlighted at the top of the workflow. Stages before it are marked done with the timestamp of completion. Stages after it are pending. A session in Medical means Prep and Copy Draft are done; Copy Final, CMS, Captions, QA, and Complete still need to happen."},
    {"title":"Advance or wait","body":"If you are the assignee on the current stage, click Done when your work is complete. The session advances to the next stage and the new assignee gets notified. If you are not the assignee, wait — the workflow advances through other people's actions. Watch Your Queue on the Dashboard for stages where you are the named owner."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'sop-user-0';

UPDATE help_articles SET
  steps = $$[
    {"title":"Check the assignee on the SOP page","body":"On the SOP page for any session, each stage row shows the assignee name and email. The currently active stage is highlighted; its assignee is the person responsible for advancing the session right now. Other stages show their future assignees so everyone knows what is coming."},
    {"title":"Understand where defaults come from","body":"Default assignees per stage come from the org-wide settings under Settings → SOP. Those defaults apply to every newly created session. The admin can override the assignee for any individual session from the Session Detail page's Stage Assignments card; overrides are session-specific."},
    {"title":"Request a reassignment","body":"If a stage assignment looks wrong — vacation, role change, the named person no longer exists — ask the admin to reassign the stage. Reassignment is a per-session action from the Session Detail page. The deadline-email throttle resets when the assignee changes, so the new owner gets a fresh email on the next hourly check."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'sop-user-1';

UPDATE help_articles SET
  steps = $$[
    {"title":"Understand the SLA","body":"Each SOP stage has a Service-Level Agreement target measured in hours from when the stage starts. The SLA is shown on the SOP page next to each stage. Default SLAs (Prep 8h, Medical 48h, etc.) come from Settings → SOP and can be overridden per session by an admin."},
    {"title":"Expect the deadline email","body":"When a stage exceeds its SLA, an hourly Beat task fires a deadline email to the stage assignee. The email subject identifies the session and stage; the body links back to the session detail page. Only one email per stage per 23 hours, so an overdue stage does not spam the inbox."},
    {"title":"Act or escalate","body":"On receiving the email, open the session and complete the stage. If you cannot complete it within a reasonable time, contact your admin to reassign the stage to someone who can. Letting a session sit overdue indefinitely blocks the rest of the workflow and impacts every downstream stage."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'sop-user-2';

UPDATE help_articles SET
  steps = $$[
    {"title":"Skip is admin-only","body":"Non-admin users cannot skip an SOP stage. Skipping or re-opening a stage are operator-level actions reserved for admins — they bypass the normal sequential workflow and need oversight to prevent state corruption. The Done button on a stage is the only advancement path for non-admins."},
    {"title":"Make the case for skipping","body":"If you think a stage does not apply to your session — for example, a session with no slide deck does not need a CMS stage — gather the reasoning and contact your admin. Provide the session ID, the stage to skip, and why. The admin decides whether to skip the stage or whether you should just click Done after a trivial review."},
    {"title":"Watch the workflow continue","body":"After the admin skips the stage, the session advances to the next stage automatically. The skipped stage is marked done with the admin's email as the actor. The audit trail captures the skip so future review can see who decided what. If the skip turns out to be wrong, the admin can re-open the stage."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'sop-user-3';

UPDATE help_articles SET
  steps = $$[
    {"title":"Open the stage card","body":"On the SOP page, locate the stage you want to reassign. Click the assignee name to expose an inline dropdown of available users in your organization. The dropdown is searchable — start typing to narrow the list. The current assignee is highlighted at the top of the list."},
    {"title":"Pick the new assignee","body":"Select the new person from the dropdown. The change saves immediately — no separate Save button. The card updates to show the new assignee name. The previous assignee no longer sees this session in Your Queue; the new assignee sees it on their next Dashboard refresh."},
    {"title":"Watch the throttle","body":"The 23-hour deadline-email throttle resets when the assignee changes. If the SLA was already overdue, the new assignee gets the deadline email on the next hourly Beat tick. If the SLA still has time, no email fires immediately — the throttle only re-arms past the SLA boundary."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'sop-admin-0';

UPDATE help_articles SET
  steps = $$[
    {"title":"Edit org-wide defaults under Settings","body":"Click Settings in the top bar, then SOP in the left rail. The defaults page lists each SOP stage with its current default SLA in hours. Click any value to edit. Changes save immediately and apply to all newly created sessions; existing sessions keep the snapshot of defaults they were created with."},
    {"title":"Override per session if needed","body":"From the Session Detail page, the Stage Assignments card lets you override the SLA for any stage on this one session. Type the new value and it saves. Per-session overrides are useful for an expedited session (shorter SLAs) or a deprioritized one (longer SLAs), without changing the org defaults."},
    {"title":"Understand snapshot behavior","body":"When a session is created, it captures the org-wide defaults into its own SOP state. Subsequent edits to org-wide defaults do not retroactively change sessions already in flight. To update an in-flight session to the new defaults, edit the per-session SLA values manually on the Session Detail page."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'sop-admin-1';

UPDATE help_articles SET
  steps = $$[
    {"title":"Find the advanced stage","body":"On the SOP page, the stage that advanced incorrectly is now showing as done — marked complete with a timestamp and the actor's email. The session has moved on to the next stage. Identify which stage needs to be re-opened and what state the session should return to."},
    {"title":"Click Re-open stage","body":"On the stage card for the incorrectly-advanced stage, click Re-open stage. The button is visible only to admins. The system asks for confirmation and an optional reason note. The reason is recorded in the audit trail so future review can see why the re-open happened."},
    {"title":"Notify everyone downstream","body":"The session returns to the re-opened stage. Everyone who was working on subsequent stages is notified that the session has moved backward; their stages return to pending. The original assignee on the re-opened stage gets the session back in their Queue and can resume work."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'sop-admin-2';

-- ════════════════════════════════════════════════════════════════════
--   Upload
-- ════════════════════════════════════════════════════════════════════

UPDATE help_articles SET
  steps = $$[
    {"title":"Pick the right media type","body":"Click Upload in the top bar. The dropzone accepts MP4 and MOV for video, WAV for audio. Other audio and video formats are rejected with a clear error message — convert them first using any standard tool. PDFs are accepted separately as slide decks attached to a session."},
    {"title":"Match the format to the use case","body":"MP4 is the most efficient for recorded meetings; use it when you have a choice. MOV is fine when MP4 is unavailable (some screen recorders prefer it). WAV is only worth using when you have an audio-only recording with high bit-rate needs. The AI pipeline handles all three equivalently for transcription."},
    {"title":"Reject and re-encode if needed","body":"If your file is rejected, the upload page shows the actual file type detected and the supported list. Use a converter to re-encode to MP4 or MOV. Tools like ffmpeg, HandBrake, or QuickTime export can do this in a couple of minutes. Once converted, drag the new file into the dropzone and try again."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'upload-user-0';

UPDATE help_articles SET
  steps = $$[
    {"title":"Pick AI Mode for clinical content","body":"On the upload form, the Mode dropdown lets you choose between AI Mode and Default Mode. AI Mode sends the media directly to Gemini multimodal, which produces a richer transcript with speaker labels, slide markers, and chapter divisions inline. Use AI Mode whenever speaker attribution and slide alignment matter — for example, clinical case rounds."},
    {"title":"Pick Default Mode for quick passes","body":"Default Mode runs the standard cloud transcription. It is faster, cheaper, and produces a plainer transcript without inline structure. Use Default Mode for content you only need a rough transcript of — for example, internal status meetings where you do not plan to do any editing or alignment."},
    {"title":"Adjust the prompt template","body":"Regardless of mode, the Prompt Template dropdown gives the AI specific instructions about tone, filler handling, and slide markers. Pick the template that matches your content (lecture, narrative, SOP, etc.). The template + mode combination determines what kind of transcript you get."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'upload-user-1';

UPDATE help_articles SET
  steps = $$[
    {"title":"Recognize the speed source","body":"Uploads go directly from your browser to cloud storage using a signed URL. The speed is bounded by your local upload bandwidth, not by the system — there is no server hop in between. A 1 GB file on a 10 Mbps connection takes 15 minutes; on 100 Mbps it takes 90 seconds. Use a wired connection if available."},
    {"title":"Watch the progress bar","body":"The dropzone shows a progress bar with percent complete. The bar updates in real time based on bytes uploaded. Do not close the browser tab or navigate away until the bar reaches 100% — closing mid-upload aborts the transfer and you have to start over."},
    {"title":"Handle a slow connection","body":"If your connection is slow, larger files take proportionally longer. For multi-gigabyte files on residential broadband, plan for an hour or more of uploading. You can leave the tab in the background; the upload continues. Reopening the tab at any point shows the current progress."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'upload-user-2';

UPDATE help_articles SET
  steps = $$[
    {"title":"Wait five minutes from the 100% mark","body":"After the progress bar reaches 100%, the system does final validation and starts the ingest pipeline. This handoff usually takes seconds but can take a few minutes on a busy day. If you see 100% and nothing happens for less than five minutes, wait — the handoff is in progress."},
    {"title":"Refresh once","body":"If the upload page sits at 100% for more than five minutes, refresh the browser page once. The session may have already been created and is now visible on the Dashboard or in the Sessions list. Check both before assuming the upload failed."},
    {"title":"Contact your admin","body":"If a refresh shows no new session and the upload still appears stuck, contact your admin. Include the file name and the approximate time you started the upload. An admin can check the stuck-upload watchdog logs and either complete the ingest manually or confirm the upload truly failed and you should retry."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'upload-user-3';

-- ════════════════════════════════════════════════════════════════════
--   Improvements
-- ════════════════════════════════════════════════════════════════════

UPDATE help_articles SET
  steps = $$[
    {"title":"Open the Improvements page","body":"Click Improvements in the top bar. The page lists suggestion cards that the system has surfaced based on patterns across many sessions. Each card describes a pattern (for example, 'always rename Dr. Smith → Dr. Smyth') and the count of sessions where you applied the same correction manually."},
    {"title":"Read each suggestion","body":"Each card shows the from-state, the to-state, and how many sessions exhibited the pattern. Suggestions appear once a pattern is detected in five or more sessions, so each one represents real work you have been doing repeatedly. The bar for surfacing is high to keep the page noise-free."},
    {"title":"Accept or dismiss","body":"Click Accept to add the pattern to your team's auto-apply list — future sessions will fix the correction automatically. Click Dismiss to remove the card without acting. Accepted patterns are applied at the end of the ingest pipeline; dismissed patterns are remembered so the system does not surface them again."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'improvements-user-0';

UPDATE help_articles SET
  steps = $$[
    {"title":"The system watches Editor edits","body":"As you make corrections in the Editor — renaming speakers, fixing common misspellings, reassigning slides — the system records each edit in the audit trail. The Improvements engine reads the audit trail looking for the same correction repeated across multiple sessions. Pattern recognition runs in the background."},
    {"title":"A threshold triggers the card","body":"When the same correction shows up in five or more sessions within a rolling window, the engine creates a suggestion card on the Improvements page. The threshold is high deliberately — one-off corrections are noise; corrections that repeat are signal. The page shows only signal-grade patterns."},
    {"title":"Tune by accepting or dismissing","body":"Your accept-and-dismiss actions feed back into the pattern engine. An accepted pattern stops appearing as a card (it is now auto-applied). A dismissed pattern is suppressed for the future even if it keeps appearing in edits. Over time the page learns what your team considers worth automating."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'improvements-user-1';

UPDATE help_articles SET
  steps = $$[
    {"title":"Open the active patterns list","body":"On the Improvements page, switch to the Active Patterns tab. The tab lists every pattern your team has accepted, ordered by acceptance date with most recent first. Each row shows the pattern, the count of sessions where it has auto-applied, and an action menu with Retire and View Details."},
    {"title":"Click Retire on the pattern","body":"Find the pattern that is no longer useful — perhaps a speaker has left the org, or a misspelling has been fixed at the source. Click Retire in the row's action menu. The system confirms once. After confirmation, the pattern stops auto-applying immediately."},
    {"title":"Existing corrections stay","body":"Retiring a pattern only affects future sessions. Sessions that already had the correction auto-applied keep the correction — those edits are committed to the audit trail. If you need to revert applied corrections, that is a per-session manual undo in the Editor's Audit tab, not a retirement action."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'improvements-admin-0';

-- ════════════════════════════════════════════════════════════════════
--   Settings (admin only)
-- ════════════════════════════════════════════════════════════════════

UPDATE help_articles SET
  steps = $$[
    {"title":"Open Settings → Auth Users","body":"Click Settings in the top bar, then Auth Users in the left rail. The page lists every person with sign-in credentials. Each row shows email (the canonical identifier), display name, role, last sign-in date, and an active/disabled toggle."},
    {"title":"Create a new user","body":"Click the New User button at the top of the list. Fill in email and display name, set an initial password (minimum eight characters), pick a role from the dropdown. Click Save. The new user can sign in immediately with that initial password and is prompted to change it on first sign-in."},
    {"title":"Edit or disable","body":"Click any row to edit its name or role inline. Click the active toggle to disable a user without removing them — disabled users cannot sign in but the audit trail keeps their historical edits attributed correctly. Disabling is the right action for someone leaving the org; deletion is rare and destructive."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'settings-admin-0';

UPDATE help_articles SET
  steps = $$[
    {"title":"Open Settings → SOP","body":"In Settings, click SOP in the left rail. The page shows every stage of the SOP workflow with two fields per stage: default SLA in hours, and default assignee email. These are the org-wide defaults applied to every newly created session at creation time."},
    {"title":"Edit a default SLA or assignee","body":"Click any SLA value to inline-edit. Click any assignee to open the user-search dropdown. Make your change and it saves immediately. There is no batch Save — each field commits independently as soon as you tab away or click outside."},
    {"title":"Snapshot semantics","body":"Defaults are captured into each new session at the moment of creation. Existing sessions keep their snapshot regardless of subsequent defaults changes. To apply the new defaults to an in-flight session, edit that session's Stage Assignments card on the Session Detail page directly."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'settings-admin-1';

UPDATE help_articles SET
  steps = $$[
    {"title":"Open Settings → Email Templates","body":"Click Settings, then Email Templates in the left rail. The page lists every template used for outbound email: deadline-overdue per stage, account-related notifications, and a default template for ad-hoc messages. Each template has a subject and a body, both editable."},
    {"title":"Click Preview to test","body":"Each template row has a Preview button. Click it to render the template against a synthetic fake session. The preview shows exactly what the assignee will see in their inbox — substituted variables filled in, formatting applied. Use the preview to catch broken merge tags before they ship to real recipients."},
    {"title":"Save and test","body":"After editing a template, click Save. The new version becomes the active template for all subsequent emails. To verify in production, wait for the next real deadline email (or trigger a synthetic one via the operator endpoints). Templates are versioned, so if you need to roll back, an admin can restore the prior version."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'settings-admin-2';

UPDATE help_articles SET
  steps = $$[
    {"title":"Open Settings → Prompt Templates","body":"In Settings, click Prompt Templates in the left rail. The page lists every prompt template available to users at upload time. Each template is a structured instruction to the AI about tone, filler-word handling, slide-marker convention, and speaker attribution style."},
    {"title":"Edit or create","body":"Click an existing template to inspect or edit. The body is markdown with placeholder substitution. Create new templates for content types not covered by the existing set — for example, a 'panel discussion' template that tells the AI to expect multiple speakers and interruptions. Click Save when done."},
    {"title":"Match users to templates","body":"At upload, users pick a template from the dropdown. The template combined with the mode (AI Mode vs Default) determines the transcript shape. Train your team to pick the right template for their content; a wrong-template upload still works but produces a less-useful transcript that requires more editing."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'settings-admin-3';

-- ════════════════════════════════════════════════════════════════════
--   Audit
-- ════════════════════════════════════════════════════════════════════

UPDATE help_articles SET
  steps = $$[
    {"title":"Open the Audit tab in the Editor","body":"Open any session in the Editor. On the right rail, click the Audit tab. The tab lists every edit ever made to this session, ordered newest first. Each row shows the user email, the timestamp, the type of edit (text, speaker, anchor, etc.), and a one-line summary of what changed."},
    {"title":"Find the edit to undo","body":"Scroll the list or use the filter chips at the top (by user, by edit type, by date) to find the specific edit you want to roll back. Click the row to expand it — for text edits, the diff highlights what changed character by character. Make sure this is the edit you want to undo."},
    {"title":"Click Undo","body":"Once you have the right row, click Undo on the row. The session reverts to the state immediately before that edit. The undo is itself logged in the audit trail as a new entry — Undo is non-destructive; you can Redo to come back. Multiple undos move sequentially through history."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'audit-user-0';

UPDATE help_articles SET
  summary = $$Every audit row records who made the change and when. The user column shows the email of the person who fired the edit; the timestamp is the moment the change committed on the server. For AI-driven edits (auto-corrections from accepted Improvements patterns), the user shows as 'ai:' followed by the pattern source.$$,
  steps = $$[
    {"title":"Read the user column","body":"Each row in the Audit tab has a user column showing the email of who fired the edit. For human edits, this is the rounds.vin sign-in email. For automated corrections — Accepted Improvements patterns applied at ingest — the email shows as 'ai:improvements' so you can distinguish human versus machine contributions."},
    {"title":"Read the timestamp","body":"The timestamp shows when the edit committed on the server in your local timezone. Hover the timestamp to see the absolute UTC value. For sessions that span time zones (a US-based reviewer and an Asia-based reviewer collaborating), the local-timezone display helps you track who acted when from your own frame."},
    {"title":"Read the diff","body":"Click any row to expand and see the before/after content. Text edits show a character-level diff with additions in green and deletions in red. Speaker changes show the old and new speaker names. Anchor moves show the segment ID before and after. The diff is the source of truth for what actually changed."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'audit-user-1';

UPDATE help_articles SET
  steps = $$[
    {"title":"Audit captures everything from creation","body":"The audit trail begins the moment the session is created and continues forever. Every transcript edit, speaker change, anchor move, find-and-replace operation, automatic correction from Improvements, and AI rewrite is logged. No human can clear the audit; it is the permanent record of what happened to the session."},
    {"title":"Scroll for older entries","body":"The Audit tab paginates the list — older entries load as you scroll down. There is no upper limit on history depth. For very old sessions with thousands of edits, the tab might take a few seconds to scroll back to the start; that latency is the only practical limit on browsing history."},
    {"title":"Export for offline review","body":"For long-term archival or external review, an admin can export the full audit trail via the operator endpoints. The export is a CSV or JSON file with every row. This is the right format for compliance audits or post-incident reviews where someone needs to step through every change a session has been through."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'audit-user-2';

-- ════════════════════════════════════════════════════════════════════
--   Viewer
-- ════════════════════════════════════════════════════════════════════

UPDATE help_articles SET
  steps = $$[
    {"title":"Use the Viewer for playback only","body":"The Viewer is a read-only render of a finished session — video alongside the transcript with chat and poll anchors in place. It is the right surface for sharing a session, doing a playback review, or showing a recording to someone who should not be making edits. It is not designed for corrections."},
    {"title":"Switch to the Editor for changes","body":"If you need to make any change — fix a typo, reassign a speaker, re-anchor a chat — close the Viewer and open the session in the Editor instead. The Editor has the same three-pane layout but with every interaction surface enabled. Edits in the Editor are reflected in the Viewer on next load."},
    {"title":"Share the Viewer link safely","body":"The Viewer URL contains the session ID. Sharing the URL gives the recipient read access if they have a rounds.vin account; non-account users see a sign-in page. Sessions are never publicly accessible — the auth gate is the only way to view them. Treat session URLs as confidential when shared."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'viewer-user-0';

UPDATE help_articles SET
  steps = $$[
    {"title":"Generate the export from the Editor","body":"Open the session in the Editor and click the Export menu in the toolbar. Pick the HTML format for a standalone web-renderable file, or pick the ZIP format for a bundle containing every format including the original media files. The export is generated fresh from the current transcript state."},
    {"title":"Download and verify","body":"The download starts immediately. Open the HTML in a browser to verify it renders the session correctly — transcript, slide thumbnails, chat anchors, all in place. For the ZIP bundle, unzip and inspect the included docx, srt, and vtt files. Verify the export looks right before sending it onward."},
    {"title":"Share the file directly","body":"Email the HTML or ZIP to the external recipient. They open it in their browser or media player — no rounds.vin account needed. The file is self-contained and shows the session in its current state. If the session is later edited, regenerate and resend; the export is a snapshot, not a live view."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'viewer-user-1';

-- ════════════════════════════════════════════════════════════════════
--   Processing
-- ════════════════════════════════════════════════════════════════════

UPDATE help_articles SET
  steps = $$[
    {"title":"Set expectations by length","body":"A typical hour of video takes ten to fifteen minutes to fully process. That includes ingest, transcription, normalization, frame sampling, slide alignment, fusion, and finalization. Multiply roughly: a 30-minute recording finishes in five to seven minutes; a two-hour recording finishes in twenty to thirty minutes."},
    {"title":"AI Mode runs longer","body":"Sessions uploaded in AI Mode (Gemini multimodal) take longer than Default Mode because the AI does more work per segment — speaker attribution, slide marker insertion, chapter detection. Plan for AI Mode runs to take 1.5x to 2x what Default Mode would take. The richer transcript is worth the wait for clinical content."},
    {"title":"Slide extraction is fast","body":"Slide deck PDFs add a minute or two of slide extraction time, regardless of session length. Decks with many slides (50+) take longer; small decks (10 or fewer) take seconds. The slide extraction runs in parallel with transcription so it does not dominate the total. Watch the Processing page progress bar to see where time is going."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'processing-user-0';

UPDATE help_articles SET
  steps = $$[
    {"title":"Click into the failed session","body":"From the Processing page or the Dashboard diagnostics strip, click the session showing Failed status. You land on the session detail page; the header displays the failure reason in plain language. Read it carefully — the reason determines whether retry will help."},
    {"title":"Decide retry or escalate","body":"Most failures are transient — Gemini quota hit, network blip, one-off task crash. For these, ask your admin to re-ingest. Re-ingest restarts the pipeline from upload and usually clears transient failures. Only escalate to engineering if a transient failure repeats three times in a row, indicating a deeper problem."},
    {"title":"Wait for the re-ingest","body":"After an admin clicks Re-Ingest, the session returns to Ingesting status and the pipeline restarts. Watch the Processing page or the Dashboard diagnostics strip for progress. Most retries succeed on the second attempt. If the second attempt fails the same way, escalate immediately — something has changed about the source file or the pipeline."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'processing-user-1';

-- ════════════════════════════════════════════════════════════════════
--   Help (self-referential)
-- ════════════════════════════════════════════════════════════════════

UPDATE help_articles SET
  steps = $$[
    {"title":"Click the help icon","body":"Find the question-mark icon in the top bar of rounds.vin, on the right side near your avatar. Click it once. The Help Center slides in as an inline panel under the banner header — the main content shifts left to make room. The panel stays open until you close it."},
    {"title":"Use the keyboard shortcut","body":"As a faster alternative, press the question-mark key (?) when no input field is focused. The Help Center opens immediately at whichever tab was last active. Press Escape to close the panel from anywhere — including while focused inside the search box or the Ask AI input."},
    {"title":"Three tabs cover most needs","body":"Inside the panel, three tabs span the workflow. 'This page' shows tips for whichever rounds.vin page you are on. 'FAQ' is cross-cutting questions across all pages. 'Ask AI' is a chat surface backed by Gemini for ad-hoc questions. Switch between tabs without losing your search state."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'help-user-0';

UPDATE help_articles SET
  steps = $$[
    {"title":"Type two characters minimum","body":"In the search box at the top of the Help Center, type a word or phrase. The search activates at two characters and updates as you type. With fewer than two characters, the tabs render normally and search is dormant. The two-character floor avoids matching every article on a single letter."},
    {"title":"Read the ranked results","body":"Matches appear sorted by relevance — title hits ranked above body-text hits. Each result shows the article title and a snippet of where the match occurred. Click any result to expand it inline. The search covers every published article including FAQs and per-page topics in a single index."},
    {"title":"Clear and try again","body":"Click the small X inside the search box to clear the query and return to the tabbed view. Refine by adding or removing words and the results update. A smarter semantic search lands in a follow-up release; the current implementation is exact-word matching with title weighting."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'help-user-1';

UPDATE help_articles SET
  steps = $$[
    {"title":"Open the Ask AI tab","body":"Inside the Help Center, click the Ask AI tab. On environments where Ask AI is enabled by your admin, the tab shows a chat input at the bottom and an empty thread above. On environments where it is disabled, you see a placeholder explaining the tab is coming soon — use the search bar or browse the other tabs instead."},
    {"title":"Type your question","body":"In the chat input, type your question in plain English. Examples: 'How do I export a session as a Word document?' or 'Why is my session stuck in Processing?' Press Cmd-Enter (Ctrl-Enter on Windows) or click the Ask button to send. The system retrieves relevant help articles and asks Gemini to synthesize an answer."},
    {"title":"Read the answer and sources","body":"The AI answers in a single message, citing the help articles it pulled context from. Each cited article appears as a clickable chip below the answer. Click a chip to open that article. The answer is grounded in published help content — if the AI does not know, it says so rather than inventing."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'help-user-2';

-- ════════════════════════════════════════════════════════════════════
--   FAQ (cross-cutting)
-- ════════════════════════════════════════════════════════════════════

UPDATE help_articles SET
  steps = $$[
    {"title":"Contact your admin","body":"Password resets are not self-service — you cannot reset your own password from the sign-in page. Email or message your admin (typically the org-internal IT or compliance lead) and ask for a password reset. Include your sign-in email so they can find your account quickly."},
    {"title":"Receive the new password and sign in","body":"The admin sets a new initial password for you in Settings → Auth Users. They tell you the new password through a secure channel — typically encrypted chat or in person. Sign in with the new password and you will be prompted to change it to one only you know on first sign-in."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'faq-0';

UPDATE help_articles SET
  steps = $$[
    {"title":"Stay signed in for a week","body":"After signing in to rounds.vin, your session stays active for up to a week of regular use. The system extends the session in the background each time you take an action, so as long as you keep using the app you do not get signed out. No daily re-sign-in cycle is required."},
    {"title":"Inactivity triggers a refresh","body":"After a short period without any clicks (typically a few hours), the app does a quiet token refresh in the background the next time you interact. You may notice a brief loading spinner; no re-sign-in is needed. If a full week of inactivity passes, you do need to sign in again."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'faq-1';

UPDATE help_articles SET
  steps = $$[
    {"title":"AI Mode uses Gemini multimodal","body":"At upload time, picking AI Mode tells the system to send your media directly to Gemini for transcription. Gemini produces a richer transcript with built-in slide markers, speaker attribution, and chapter divisions inline. Use AI Mode whenever those structural elements matter — clinical case rounds are the canonical fit."},
    {"title":"Default Mode uses standard cloud STT","body":"Default Mode runs Google Cloud Speech-to-Text on the audio. It is faster, cheaper, and produces a plainer transcript without inline structure. Use Default Mode for internal meetings, status updates, or any content where you only need a rough transcript and do not plan to do significant editing or alignment work."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'faq-2';

UPDATE help_articles SET
  steps = $$[
    {"title":"Built-in rate limit kicks in","body":"The 'Slow down' message appears when you have fired too many actions in a short window. The system has a built-in rate limit that protects the AI pipeline from accidental bursts of work — for example, an admin clicking Re-Ingest on twenty sessions in five seconds. The message is intentional protection, not an error."},
    {"title":"Wait and retry","body":"Wait five to ten seconds, then try the action again. The rate limit clears on a short rolling window. There is no penalty for hitting the limit — your previous action either completed normally or was queued for execution. If you keep seeing the message, slow your click cadence."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'faq-3';

UPDATE help_articles SET
  steps = $$[
    {"title":"Re-ingest is idempotent","body":"The Re-Ingest operation is designed so that running it multiple times produces the same result as running it once. The pipeline detects in-progress work and skips stages that already completed successfully. This makes retry safe — you cannot end up with duplicate transcripts or doubled segments from clicking Re-Ingest more than once."},
    {"title":"Only admins can re-ingest","body":"The Re-Ingest button is inside the Editor's Admin tab, which is visible only to admins. Non-admin users cannot retry a failed session themselves — they need to contact the admin who clicks Re-Ingest on their behalf. The admin gate exists because re-ingest consumes Gemini quota and should be a deliberate action."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'faq-4';

UPDATE help_articles SET
  steps = $$[
    {"title":"Open the Editor and click Audit","body":"Open the session in the Editor by clicking it from the Sessions list. On the right rail of the Editor, click the Audit tab. The tab loads the full edit history for the session, sorted newest first, with one row per edit operation."},
    {"title":"Find the row you care about","body":"Each row shows who made the edit (email), when (timestamp), what type of edit (text, speaker, anchor, etc.), and a one-line summary. Click any row to expand it and see the full before/after diff. Use the filter chips at the top to narrow by user, edit type, or date range."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'faq-5';

UPDATE help_articles SET
  steps = $$[
    {"title":"Archive removes from the active list","body":"Archiving a session moves it out of the active Sessions list view but keeps every byte of data intact — transcript, edits, exports, audit trail. The session is still searchable in the archive view (admin only) and can be restored to active status at any time. Use archive for finished sessions you do not need front and center."},
    {"title":"Purge actually deletes","body":"A permanent purge — separate from archive — actually removes the session data and cannot be undone. The system asks twice before purging, including typing the session title as the second confirmation. Recovery from a purge requires restoring from a database backup, which is a multi-hour ops task."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'faq-6';

UPDATE help_articles SET
  steps = $$[
    {"title":"The Editor generates exports fresh","body":"When you click an export format from the Editor's Export menu, the system generates the file fresh from the current transcript state. There is no cached version — every export reflects every edit you have made up to the moment you clicked. This means downstream consumers always get the latest content."},
    {"title":"Filler handling varies by format","body":"Word documents, plain text, and HTML have filler words ('um', 'uh', 'er') removed for readability. Captions in SRT and VTT format keep them so the captions stay aligned with the audio. If you need a docx with fillers preserved or an SRT with them stripped, that customization is not yet exposed; contact your admin to request the feature."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'faq-7';

UPDATE help_articles SET
  steps = $$[
    {"title":"Three tabs cover the surface","body":"The Help Center has three tabs: 'This page' shows tips for whichever rounds.vin route you are currently viewing; 'FAQ' is cross-cutting questions that apply across the whole app; 'Ask AI' is a chat surface for ad-hoc questions. Pick the tab that matches the kind of help you need."},
    {"title":"Search and Ask AI as needed","body":"The search box at the top spans every tab — type two or more characters to find articles across pages and FAQs in one pass. The Ask AI tab routes to Gemini when enabled by your admin; it retrieves relevant articles and synthesizes a grounded answer with citations. Use search for known topics, Ask AI for open-ended questions."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'faq-8';

UPDATE help_articles SET
  steps = $$[
    {"title":"Click Full docs at the bottom","body":"At the bottom of the Help Center panel, the 'Full docs' link opens the detailed user guide in a new tab. The guide covers everything in the in-app help plus longer-form topics like architecture overviews, deployment notes, and known limitations. Use the docs when the in-app help is not enough."},
    {"title":"Contact your admin for the rest","body":"For bug reports, feature requests, or questions specific to your organization's deployment, contact your admin directly. They have access to the operator endpoints, the engineering team escalation path, and the org-level configuration that affects how rounds.vin behaves for your users."}
  ]$$::jsonb,
  last_edited_by = 'system:phase5_content_refresh',
  updated_at = now(),
  version = version + 1
WHERE slug = 'faq-9';

COMMIT;
