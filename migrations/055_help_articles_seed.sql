-- migrations/055_help_articles_seed.sql
--
-- Phase 3 of the Help Center port (plan 2026-06-05-009).
-- Seeds help_articles from the Phase 1 hardcoded HELP_CONTENT corpus
-- (frontend/src/constants/help-content.ts mirrored in
-- app/data/help_content.py). Every topic in every page+role + every
-- FAQ entry lands as a published article with a deterministic slug.
--
-- Idempotency: ON CONFLICT (slug) DO NOTHING. Re-running this migration
-- never overwrites admin edits — once an article exists with a given
-- slug, subsequent applies skip it. Slug scheme:
--   page topic: '<page_key>-<role>-<topic_index>'  (e.g. 'editor-user-0')
--   faq item:   'faq-<index>'                       (e.g. 'faq-3')
--
-- The seed below is byte-faithful to help-content.ts as of HEAD on
-- 2026-06-05. If help-content.ts is edited and admins want the new
-- copy to appear: either (a) bump the slug scheme to a date suffix
-- (e.g. '-2026-06-12') so a fresh seed migration ingests the changes
-- as new rows, or (b) hand-edit individual articles via the admin UI.
-- The first approach is preferable when many topics change at once.
--
-- Related plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md §5.5

-- ── Dashboard ───────────────────────────────────────────────────────
INSERT INTO help_articles
    (slug, title, summary, category, audience, feature_tags, content_domain, is_published, display_order)
VALUES
    ('dashboard-user-0', 'What do the cards across the top mean?',
     'Each card is a live count of one part of the workflow. AI Sessions shows recordings still being processed; SOP Sessions shows recordings moving through medical review and copy editing; Segments and Artifacts are running totals of what is in the system. Click any card to drill into the underlying list.',
     'page:dashboard', 'users', '["dashboard"]'::jsonb, 'dashboard', TRUE, 0),
    ('dashboard-user-1', 'How do I find sessions that need my attention?',
     'Look at "Your Queue" — it shows the sessions where you are the named stage assignee. If your queue is empty, everything assigned to you is done. The full list of sessions is always one click away under Sessions in the top bar.',
     'page:dashboard', 'users', '["dashboard"]'::jsonb, 'dashboard', TRUE, 1),
    ('dashboard-user-2', 'My counts look stale.',
     'The dashboard refreshes when you land on it or navigate back to it. If a number stays wrong after a refresh, log out and back in to refresh your session.',
     'page:dashboard', 'users', '["dashboard"]'::jsonb, 'dashboard', TRUE, 2),
    ('dashboard-user-3', 'Where do I start a new upload?',
     'Click Upload in the top bar. From there you pick a video or audio file, choose the AI model and prompt template, and start processing. The upload runs in the background.',
     'page:dashboard', 'users', '["dashboard"]'::jsonb, 'dashboard', TRUE, 3),
    ('dashboard-admin-0', 'What extra widgets do I see as admin?',
     'A diagnostics strip with queue depth, recent failures, and rescue links. The "All Sessions" tile lists every session regardless of which stage owns it, so you can find anything at a glance.',
     'page:dashboard', 'admin', '["dashboard"]'::jsonb, 'dashboard', TRUE, 0),
    ('dashboard-admin-1', 'How do I rescue a stuck session from here?',
     'Click into the failed session from the diagnostics list, open the Editor for that session, then go to the Admin tab on the right rail. The Rescue section has buttons for re-ingest, re-align, abort, and per-stage init.',
     'page:dashboard', 'admin', '["dashboard"]'::jsonb, 'dashboard', TRUE, 1),
    ('dashboard-admin-2', 'Where do I manage users, settings, and email templates?',
     'In the Settings page, accessible from the top bar. Users live under Settings -> Auth Users; email templates live under Settings -> Email Templates; SOP stage assignees and SLA windows live under Settings -> SOP.',
     'page:dashboard', 'admin', '["dashboard"]'::jsonb, 'dashboard', TRUE, 2),
    ('dashboard-admin-3', 'Why does the system sometimes say "Slow down"?',
     'A built-in safety limit guards the AI pipeline from accidental bursts of work. Wait a few seconds and try the action again.',
     'page:dashboard', 'admin', '["dashboard"]'::jsonb, 'dashboard', TRUE, 3)
ON CONFLICT (slug) DO NOTHING;

-- ── Sessions ────────────────────────────────────────────────────────
INSERT INTO help_articles
    (slug, title, summary, category, audience, feature_tags, content_domain, is_published, display_order)
VALUES
    ('sessions-user-0', 'How do I find a specific session?',
     'Use the search box at the top of the list to filter by session name. The status chips on the right of each row tell you where the session is in the pipeline — ingesting, processing, ready, or failed.',
     'page:sessions', 'users', '["sessions"]'::jsonb, 'sessions', TRUE, 0),
    ('sessions-user-1', 'What does each status mean?',
     'Ingesting: the upload is being prepared. Processing: AI transcription and slide alignment are running. Ready: the session is finished and the Editor is available. Failed: something went wrong — open the session to see the reason.',
     'page:sessions', 'users', '["sessions"]'::jsonb, 'sessions', TRUE, 1),
    ('sessions-user-2', 'How do I open the editor for a session?',
     'Click anywhere on the row to open the session detail page, then click the Editor button on the right. Or click directly on the session name.',
     'page:sessions', 'users', '["sessions"]'::jsonb, 'sessions', TRUE, 2),
    ('sessions-user-3', 'Can I delete a session?',
     'Only admins can delete or archive sessions. If you need a session removed, contact your admin.',
     'page:sessions', 'users', '["sessions"]'::jsonb, 'sessions', TRUE, 3),
    ('sessions-admin-0', 'How do soft-delete and restore work?',
     'Soft-delete moves the session out of the active list but keeps the data intact — open the Trash tab to restore. Permanent purge actually removes the data and cannot be undone, so the system asks twice before purging.',
     'page:sessions', 'admin', '["sessions"]'::jsonb, 'sessions', TRUE, 0),
    ('sessions-admin-1', 'Why can some people soft-delete but not others?',
     'Soft-delete is reserved for admins and for one external partner account. Everyone else sees the buttons disabled.',
     'page:sessions', 'admin', '["sessions"]'::jsonb, 'sessions', TRUE, 1),
    ('sessions-admin-2', 'A session is stuck — what do I do?',
     'Open the session, then open the Editor, then the Admin tab on the right rail. The Rescue section has Re-Ingest (restart the whole pipeline), Re-Align (rebuild slide-to-segment matches), Init Stage Assignees (for legacy sessions), Auto-Place Polls, and Abort (force-fail). Each button confirms before firing.',
     'page:sessions', 'admin', '["sessions"]'::jsonb, 'sessions', TRUE, 2),
    ('sessions-admin-3', 'How do I bulk-act on multiple sessions?',
     'Bulk actions are not exposed in the UI today. For bulk operations, use the diagnostics endpoints — your admin handbook has the curl recipes.',
     'page:sessions', 'admin', '["sessions"]'::jsonb, 'sessions', TRUE, 3)
ON CONFLICT (slug) DO NOTHING;

-- ── Editor ──────────────────────────────────────────────────────────
INSERT INTO help_articles
    (slug, title, summary, category, audience, feature_tags, content_domain, is_published, display_order)
VALUES
    ('editor-user-0', 'How do I edit a transcript segment?',
     'Click on the segment text in the middle pane to start editing. Type your change, then click Save. Use Cancel to drop the edit. Every save is reversible — open the Audit tab on the right to see your edit history and undo any change.',
     'page:editor', 'users', '["editor"]'::jsonb, 'editor', TRUE, 0),
    ('editor-user-1', 'How do I change who said a segment?',
     'Use the Speakers panel on the top right to rename, merge, or reassign speakers across the whole session. Changes apply to every segment that references the speaker, so a one-time rename fixes the entire transcript at once.',
     'page:editor', 'users', '["editor"]'::jsonb, 'editor', TRUE, 1),
    ('editor-user-2', 'How do I move a chat or poll to a different time?',
     'Drag the chat card or poll card from the right rail onto the transcript segment where it should appear. The card snaps to that segment''s start time. You can drag again to re-anchor at any point, or drag it back to the right rail to detach it.',
     'page:editor', 'users', '["editor"]'::jsonb, 'editor', TRUE, 2),
    ('editor-user-3', 'What do the colored chips above the transcript do?',
     'They are filters. Click "Filler" to show only segments that contain filler words; click "Punctuation" to surface punctuation discrepancies; "Drift" finds places where the AI alignment looks shaky. Click a chip again to clear the filter.',
     'page:editor', 'users', '["editor"]'::jsonb, 'editor', TRUE, 3),
    ('editor-user-4', 'How do I export the finished transcript?',
     'Click the Export menu at the top of the Editor. Pick docx, srt, vtt, txt, or zip. The download starts immediately. Filler words like "um" and "uh" are removed from docx and txt for readability; srt and vtt keep them so the captions stay aligned to the audio.',
     'page:editor', 'users', '["editor"]'::jsonb, 'editor', TRUE, 4),
    ('editor-admin-0', 'What does the Admin tab''s Rescue section do?',
     'Five operator buttons that re-run pipeline stages on a stuck session. Re-Ingest restarts the whole pipeline from upload; Re-Align rebuilds slide-to-segment matches; Init Session Stages assigns SOP stages for legacy sessions that predate that hook; Auto-Place Polls backfills poll anchors; Abort hard-fails the session.',
     'page:editor', 'admin', '["editor"]'::jsonb, 'editor', TRUE, 0),
    ('editor-admin-1', 'When should I retry versus abort a session?',
     'Retry when the failure was transient — a network blip, a Gemini quota cap, a one-off task crash. Abort when the source media is bad and the session should not continue. The Abort button asks twice before firing.',
     'page:editor', 'admin', '["editor"]'::jsonb, 'editor', TRUE, 1),
    ('editor-admin-2', 'Where can I see who edited what?',
     'Open the Audit tab on the right rail. Every edit is logged with the user, the timestamp, and the before/after text. Undo and Redo move a session-wide pointer backward and forward through the log.',
     'page:editor', 'admin', '["editor"]'::jsonb, 'editor', TRUE, 2)
ON CONFLICT (slug) DO NOTHING;

-- ── Session detail ──────────────────────────────────────────────────
INSERT INTO help_articles
    (slug, title, summary, category, audience, feature_tags, content_domain, is_published, display_order)
VALUES
    ('session-detail-user-0', 'What are Sources?',
     'Sources are the files that make up the session: the video or audio recording, the slide deck PDF, and optionally a chat or poll manifest from the original meeting. The Sources panel shows each file with its role and processing status.',
     'page:session-detail', 'users', '["session-detail"]'::jsonb, 'sessions', TRUE, 0),
    ('session-detail-user-1', 'How do I attach a slide deck after upload?',
     'Click "Add file" in the Sources panel, pick the PDF, and the system kicks off slide extraction. New slides appear in the slide rail in the Editor once extraction completes.',
     'page:session-detail', 'users', '["session-detail"]'::jsonb, 'sessions', TRUE, 1),
    ('session-detail-user-2', 'What does Chat Participants show?',
     'Every speaker the system found in the chat log or the AI transcript. You can rename, merge, or remove speakers here — changes propagate to every segment that references the speaker.',
     'page:session-detail', 'users', '["session-detail"]'::jsonb, 'sessions', TRUE, 2),
    ('session-detail-user-3', 'How do I edit the session title or metadata?',
     'Click the title at the top of the page to inline-edit. Date, presenter, and other fields each have an Edit button. Saves are immediate; there is no separate Save button at the page level.',
     'page:session-detail', 'users', '["session-detail"]'::jsonb, 'sessions', TRUE, 3),
    ('session-detail-user-4', 'Where does the export download live?',
     'Open the Editor, then use the Export menu at the top of the editor toolbar. Picking a format generates the file and starts the download immediately.',
     'page:session-detail', 'users', '["session-detail"]'::jsonb, 'sessions', TRUE, 4),
    ('session-detail-admin-0', 'How do I re-run a failed pipeline stage?',
     'Open the Editor for the session, then go to the Admin tab. Each rescue button confirms before firing. Re-Ingest restarts everything from scratch; Re-Align rebuilds just the slide-to-segment matches; Abort forces the session to failed status if it is hung.',
     'page:session-detail', 'admin', '["session-detail"]'::jsonb, 'sessions', TRUE, 0),
    ('session-detail-admin-1', 'When should I retry versus abort?',
     'Retry when the failure looks transient — a network blip, a Gemini rate limit, a one-off ffmpeg crash. Abort when the source media is bad and the session should not continue. Aborted sessions can be deleted from the Sessions list.',
     'page:session-detail', 'admin', '["session-detail"]'::jsonb, 'sessions', TRUE, 1),
    ('session-detail-admin-2', 'Can I edit who is assigned to which SOP stage?',
     'Yes — the Stage Assignments card lets you set a person per stage. Each stage carries a default SLA in hours; the deadline email fires when the SLA elapses if email notifications are turned on.',
     'page:session-detail', 'admin', '["session-detail"]'::jsonb, 'sessions', TRUE, 2)
ON CONFLICT (slug) DO NOTHING;

-- ── SOP / Upload / Improvements / Settings / Audit / Viewer / Processing / Help ──
INSERT INTO help_articles
    (slug, title, summary, category, audience, feature_tags, content_domain, is_published, display_order)
VALUES
    ('sop-user-0', 'What are the SOP stages?',
     'Prep, Copy Draft, Medical, Copy Final, CMS, Captions, QA, Complete. The session moves forward when the assignee clicks Done on the current stage.',
     'page:sop', 'users', '["sop"]'::jsonb, 'sop', TRUE, 0),
    ('sop-user-1', 'Who is the assignee for each stage?',
     'Defaults come from Settings -> SOP, but the admin can override per-session on the Session Detail page. The current assignee for each stage is shown right on the SOP page.',
     'page:sop', 'users', '["sop"]'::jsonb, 'sop', TRUE, 1),
    ('sop-user-2', 'What happens if the SLA elapses?',
     'A deadline email goes to the stage assignee on the next hourly check. Only one email per stage per day so you do not get spammed.',
     'page:sop', 'users', '["sop"]'::jsonb, 'sop', TRUE, 2),
    ('sop-user-3', 'Can I skip a stage?',
     'Only the admin can skip or re-open a stage. If you think a stage does not apply to your session, ask your admin to advance it.',
     'page:sop', 'users', '["sop"]'::jsonb, 'sop', TRUE, 3),
    ('sop-admin-0', 'How do I reassign a stage?',
     'Click the assignee name on the stage card and pick someone else from the dropdown. The deadline email throttle resets for that stage; if the SLA is already overdue, the new assignee gets the email on the next hourly check.',
     'page:sop', 'admin', '["sop"]'::jsonb, 'sop', TRUE, 0),
    ('sop-admin-1', 'How do I change the SLA hours for a stage?',
     'Per-session overrides live on the Session Detail page. Org-wide defaults live under Settings -> SOP. Changes only affect sessions created after the change; existing sessions keep their snapshot.',
     'page:sop', 'admin', '["sop"]'::jsonb, 'sop', TRUE, 1),
    ('sop-admin-2', 'A stage advanced when it should not have — what now?',
     'Use the "Re-open stage" button on the stage card. The session goes back to that stage; everyone downstream is notified.',
     'page:sop', 'admin', '["sop"]'::jsonb, 'sop', TRUE, 2),

    ('upload-user-0', 'What file types can I upload?',
     'MP4, MOV, and WAV for video and audio. PDFs for slide decks. The upload page rejects other types up front.',
     'page:upload', 'users', '["upload"]'::jsonb, 'processing', TRUE, 0),
    ('upload-user-1', 'What is the difference between AI Mode and Default Mode?',
     'AI Mode sends the media directly to Gemini for a richer transcript with speaker labels and slide markers. Default Mode runs the standard cloud transcription, which is faster and cheaper but plainer. Pick AI Mode for clinical content where speaker attribution and slide alignment matter; pick Default for quick passes.',
     'page:upload', 'users', '["upload"]'::jsonb, 'processing', TRUE, 1),
    ('upload-user-2', 'Why is my upload slow?',
     'Uploads go directly from your browser to cloud storage, so the speed is your local upload speed. Large videos take time. The page shows a progress bar — leave the tab open until it reaches 100%.',
     'page:upload', 'users', '["upload"]'::jsonb, 'processing', TRUE, 2),
    ('upload-user-3', 'My upload says it is stuck.',
     'If progress sits at 100% for more than five minutes, refresh the page and try once more. If it still hangs, contact your admin.',
     'page:upload', 'users', '["upload"]'::jsonb, 'processing', TRUE, 3),

    ('improvements-user-0', 'How do I use the suggestions here?',
     'Each card is a suggestion you can accept or dismiss. Accepting an "always rename X to Y" suggestion adds it to your team''s name-fix list so future sessions auto-apply the correction.',
     'page:improvements', 'users', '["improvements"]'::jsonb, 'improvements', TRUE, 0),
    ('improvements-user-1', 'Where do these patterns come from?',
     'The system watches the edits your team makes in the Editor. When the same correction shows up in five or more sessions, it surfaces here as a pattern worth automating.',
     'page:improvements', 'users', '["improvements"]'::jsonb, 'improvements', TRUE, 1),
    ('improvements-admin-0', 'How do I retire a pattern that is no longer helpful?',
     'Open the pattern card and click "Retire". Future sessions will no longer auto-apply it; existing sessions keep the corrections that were already applied.',
     'page:improvements', 'admin', '["improvements"]'::jsonb, 'improvements', TRUE, 0),

    ('settings-admin-0', 'Auth Users — what do I edit here?',
     'The list of people who can sign in to rounds.vin. Each row has email, name, and role. New users get an initial password you set on creation; they change it on first login.',
     'page:settings', 'admin', '["settings"]'::jsonb, 'settings', TRUE, 0),
    ('settings-admin-1', 'SOP defaults — what changes when I edit these?',
     'You set the default SLA hours per stage and the default assignee. New sessions adopt these on creation; existing sessions keep the snapshot they were created with.',
     'page:settings', 'admin', '["settings"]'::jsonb, 'settings', TRUE, 1),
    ('settings-admin-2', 'Email Templates — how do I preview before sending?',
     'Each template has a Preview button. The preview renders against a fake session so you can see exactly what the assignee will receive.',
     'page:settings', 'admin', '["settings"]'::jsonb, 'settings', TRUE, 2),
    ('settings-admin-3', 'Prompt Templates — what are these for?',
     'Each prompt template tells the AI how to transcribe a session — what tone to use, how to handle filler words, what slide-marker convention to use. Pick a template per session at upload time.',
     'page:settings', 'admin', '["settings"]'::jsonb, 'settings', TRUE, 3),

    ('audit-user-0', 'How do I undo an edit?',
     'Open the Audit tab in the Editor, find the edit you want to roll back, and click Undo. The whole session moves back one step. Click Redo to move forward again.',
     'page:audit', 'users', '["audit"]'::jsonb, 'editor', TRUE, 0),
    ('audit-user-1', 'Can I see who made a change?',
     'Yes — every audit row shows the user email, the timestamp, and the before/after text.',
     'page:audit', 'users', '["audit"]'::jsonb, 'editor', TRUE, 1),
    ('audit-user-2', 'How far back does the audit history go?',
     'Every edit since the session was created. Nothing is ever deleted from the audit log.',
     'page:audit', 'users', '["audit"]'::jsonb, 'editor', TRUE, 2),

    ('viewer-user-0', 'Can I edit from the Viewer?',
     'No — the Viewer is read-only. To make edits, open the session in the Editor instead.',
     'page:viewer', 'users', '["viewer"]'::jsonb, 'sessions', TRUE, 0),
    ('viewer-user-1', 'How do I share a session with someone outside rounds.vin?',
     'Export the session as an HTML or zip from the Editor. The download contains everything someone needs to view it offline.',
     'page:viewer', 'users', '["viewer"]'::jsonb, 'sessions', TRUE, 1),

    ('processing-user-0', 'How long does processing take?',
     'A typical hour of video takes about ten to fifteen minutes to fully process. AI Mode is slower than Default Mode. Large slide decks add a minute or two for slide extraction.',
     'page:processing', 'users', '["processing"]'::jsonb, 'processing', TRUE, 0),
    ('processing-user-1', 'I see "Failed" — what now?',
     'Click the session to see the failure reason. Most failures are transient — a Gemini quota hit, a network blip — and an admin can re-ingest the session with one click.',
     'page:processing', 'users', '["processing"]'::jsonb, 'processing', TRUE, 1),

    ('help-user-0', 'How do I open the Help Center?',
     'Click the question-mark button in the top bar, or press the ? key when no input is focused. Press Esc to close.',
     'page:help', 'users', '["help"]'::jsonb, 'general', TRUE, 0),
    ('help-user-1', 'How does the search work?',
     'Type two or more characters and the search bar finds matching topics across every page and the FAQ. Right now search is exact-word matching; a smarter semantic search lands in the next release.',
     'page:help', 'users', '["help"]'::jsonb, 'general', TRUE, 1),
    ('help-user-2', 'When will Ask AI work?',
     'The Ask AI tab is in the next release. For now use the search bar above or browse the tabs.',
     'page:help', 'users', '["help"]'::jsonb, 'general', TRUE, 2)
ON CONFLICT (slug) DO NOTHING;

-- ── FAQ (cross-cutting) ─────────────────────────────────────────────
INSERT INTO help_articles
    (slug, title, summary, category, audience, feature_tags, content_domain, is_published, display_order)
VALUES
    ('faq-0', 'I forgot my password — what do I do?',
     'Contact your admin to set a new initial password. Five failed sign-in attempts in fifteen minutes will briefly lock the account; wait it out, then sign in with the new password.',
     'faq:auth', 'users', '[]'::jsonb, 'general', TRUE, 0),
    ('faq-1', 'How long do sessions last?',
     'You stay signed in for up to a week of activity. After a short period of inactivity the app may quietly refresh your session in the background so you do not lose your place.',
     'faq:auth', 'users', '[]'::jsonb, 'general', TRUE, 1),
    ('faq-2', 'What is the difference between AI Mode and Default Mode?',
     'AI Mode uses Gemini for transcription with built-in slide markers and speaker attribution. Default Mode uses standard cloud transcription, which is faster and cheaper but plainer. Pick AI Mode for clinical content where attribution matters; pick Default for quick passes.',
     'faq:processing', 'users', '[]'::jsonb, 'processing', TRUE, 2),
    ('faq-3', 'Why does the app sometimes say "Slow down"?',
     'A safety limit guards the AI pipeline from accidental bursts of work. Wait a few seconds and try the action again.',
     'faq:processing', 'users', '[]'::jsonb, 'processing', TRUE, 3),
    ('faq-4', 'Can I retry a failed session safely?',
     'Yes. Re-ingest restarts the pipeline from upload; the system is built so re-runs are idempotent. Only admins can fire re-ingest.',
     'faq:processing', 'users', '[]'::jsonb, 'processing', TRUE, 4),
    ('faq-5', 'Where can I see who edited a transcript?',
     'Open the session in the Editor, then click the Audit tab on the right rail. Every edit is logged with the user, timestamp, and before/after text.',
     'faq:editor', 'users', '[]'::jsonb, 'editor', TRUE, 5),
    ('faq-6', 'What happens when I archive a session?',
     'Archive moves the session out of the active Sessions list but keeps the data intact. Admins can restore it any time. Permanent purge actually removes the data and cannot be undone.',
     'faq:sessions', 'users', '[]'::jsonb, 'sessions', TRUE, 6),
    ('faq-7', 'Where do exports come from?',
     'The Export menu in the Editor generates the file fresh from the current transcript every time. Filler words are stripped from docx and txt; srt and vtt keep them so captions stay aligned to the audio.',
     'faq:editor', 'users', '[]'::jsonb, 'editor', TRUE, 7),
    ('faq-8', 'How do I use this help panel?',
     'The "This page" tab shows tips for the page you are on. FAQ has cross-cutting questions. Ask AI is in the next release. Search any tab from the box at the top.',
     'faq:help', 'users', '[]'::jsonb, 'general', TRUE, 8),
    ('faq-9', 'Where can I learn more?',
     'Click "Full docs" at the bottom of this panel for the detailed user guide. For bug reports or feature ideas, reach your admin.',
     'faq:help', 'users', '[]'::jsonb, 'general', TRUE, 9)
ON CONFLICT (slug) DO NOTHING;
