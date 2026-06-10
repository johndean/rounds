/**
 * docs/help-center/HELP_CONTENT.ts
 *
 * Canonical Help Center content export for rounds.vin. This is the
 * documentation-tree mirror of the live frontend constant at
 * `frontend/src/constants/help-content.ts` — the two must stay in sync.
 * The in-app help panel (HelpPanel.vue, via stores/help.ts) consumes the
 * `HELP_CONTENT` export to seed its **pages** + **faq** tabs; this copy
 * is the offline / review-friendly source of the same data.
 *
 * Structure mirrors po.vin's help-content.ts so future phases (CMS backend
 * in mig 053–056, AI bulk rewrites, version history) can layer overrides on
 * top without reshaping the consumer components.
 *
 * CRITICAL CONTENT RULES (do not break when editing):
 *   - Plain language. No backend implementation details.
 *   - No Vue component names, no DB schema terms, no phase markers,
 *     no HTTP routes, no env var names.
 *   - Roles, stages, queues, statuses ARE user-facing — keep them.
 *   - 3–5 topics per page+role; ~10 FAQs total.
 *   - Never reference features the code doesn't actually ship. If you
 *     say a button exists, the button must exist in the UI.
 *
 * Plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md §6.4
 */

export interface HelpTopic { q: string; a: string; }
export interface HelpEntry { intro: string; topics: HelpTopic[]; }
export interface HelpPage {
  title: string;
  all?: HelpEntry;
  user?: HelpEntry;
  admin?: HelpEntry;
}
export interface HelpContentShape {
  pages: Record<string, HelpPage>;
  faq: HelpTopic[];
  contact: { email: string; slack: string; docs: string; };
}

/**
 * Mirror of the backend's LEGACY_ADMIN_EMAIL constant (BR-001). Used by
 * HelpPanel to choose between 'user' and 'admin' content per page.
 * Future migration to auth_users.role retires this client-side mirror.
 */
export const LEGACY_ADMIN_EMAIL_CLIENT = 'johndean@vin.com';

export const HELP_CONTENT: HelpContentShape = {
  pages: {
    // ── Dashboard ────────────────────────────────────────────
    dashboard: {
      title: 'Dashboard',
      user: {
        intro: 'Your home base. The metric cards along the top show how the system is doing right now, and the lists below them surface the work that needs you.',
        topics: [
          { q: 'What do the cards across the top mean?', a: 'Each card is a live count of one part of the workflow. AI Sessions shows recordings still being processed; SOP Sessions shows recordings moving through medical review and copy editing; Segments and Artifacts are running totals of what is in the system. Click any card to drill into the underlying list.' },
          { q: 'How do I find sessions that need my attention?', a: 'Look at "Your Queue" — it shows the sessions where you are the named stage assignee. If your queue is empty, everything assigned to you is done. The full list of sessions is always one click away under Sessions in the top bar.' },
          { q: 'My counts look stale.', a: 'The dashboard refreshes when you land on it or navigate back to it. If a number stays wrong after a refresh, log out and back in to refresh your session.' },
          { q: 'Where do I start a new upload?', a: 'Click Upload in the top bar. From there you pick a video or audio file, choose the AI model and prompt template, and start processing. The upload runs in the background.' },
        ],
      },
      admin: {
        intro: 'You see every queue and every metric, plus the diagnostics row below the standard cards. The role-switcher in the top bar lets you preview the dashboard as any other user.',
        topics: [
          { q: 'What extra widgets do I see as admin?', a: 'A diagnostics strip with queue depth, recent failures, and rescue links. The "All Sessions" tile lists every session regardless of which stage owns it, so you can find anything at a glance.' },
          { q: 'How do I rescue a stuck session from here?', a: 'Click into the failed session from the diagnostics list, open the Editor for that session, then go to the Admin tab on the right rail. The Rescue section has buttons for re-ingest, re-align, abort, and per-stage init.' },
          { q: 'Where do I manage users, settings, and email templates?', a: 'In the Settings page, accessible from the top bar. Users live under Settings → Auth Users; email templates live under Settings → Email Templates; SOP stage assignees and SLA windows live under Settings → SOP.' },
          { q: 'Why does the system sometimes say "Slow down"?', a: 'A built-in safety limit guards the AI pipeline from accidental bursts of work. Wait a few seconds and try the action again.' },
        ],
      },
    },

    // ── Sessions ─────────────────────────────────────────────
    sessions: {
      title: 'Sessions',
      user: {
        intro: 'The Sessions page is the home of every video or audio recording you have uploaded. Each row shows the session name, processing status, current stage, and a few quick counts.',
        topics: [
          { q: 'How do I find a specific session?', a: 'Use the search box at the top of the list to filter by session name. The status chips on the right of each row tell you where the session is in the pipeline — ingesting, processing, ready, or failed.' },
          { q: 'What does each status mean?', a: 'Ingesting: the upload is being prepared. Processing: AI transcription and slide alignment are running. Ready: the session is finished and the Editor is available. Failed: something went wrong — open the session to see the reason.' },
          { q: 'How do I open the editor for a session?', a: 'Click anywhere on the row to open the session detail page, then click the Editor button on the right. Or click directly on the session name.' },
          { q: 'Can I delete a session?', a: 'Only admins can delete or archive sessions. If you need a session removed, contact your admin.' },
        ],
      },
      admin: {
        intro: 'You see every session in the system and can soft-delete, restore, or permanently purge any of them.',
        topics: [
          { q: 'How do soft-delete and restore work?', a: 'Soft-delete moves the session out of the active list but keeps the data intact — open the Trash tab to restore. Permanent purge actually removes the data and cannot be undone, so the system asks twice before purging.' },
          { q: 'Why can some people soft-delete but not others?', a: 'Soft-delete is reserved for admins and for one external partner account. Everyone else sees the buttons disabled.' },
          { q: 'A session is stuck — what do I do?', a: 'Open the session, then open the Editor, then the Admin tab on the right rail. The Rescue section has Re-Ingest (restart the whole pipeline), Re-Align (rebuild slide-to-segment matches), Init Stage Assignees (for legacy sessions), Auto-Place Polls, and Abort (force-fail). Each button confirms before firing.' },
          { q: 'How do I bulk-act on multiple sessions?', a: 'Bulk actions are not exposed in the UI today. For bulk operations, use the diagnostics endpoints — your admin handbook has the curl recipes.' },
        ],
      },
    },

    // ── Session Detail ───────────────────────────────────────
    'session-detail': {
      title: 'Session detail',
      user: {
        intro: 'The Session Detail page shows everything about one recording — uploaded files, slides, AI status, SOP stage assignments, and quick links to the Editor and exports.',
        topics: [
          { q: 'What are Sources?', a: 'Sources are the files that make up the session: the video or audio recording, the slide deck PDF, and optionally a chat or poll manifest from the original meeting. The Sources panel shows each file with its role and processing status.' },
          { q: 'How do I attach a slide deck after upload?', a: 'Click "Add file" in the Sources panel, pick the PDF, and the system kicks off slide extraction. New slides appear in the slide rail in the Editor once extraction completes.' },
          { q: 'What does Chat Participants show?', a: 'Every speaker the system found in the chat log or the AI transcript. You can rename, merge, or remove speakers here — changes propagate to every segment that references the speaker.' },
          { q: 'How do I edit the session title or metadata?', a: 'Click the title at the top of the page to inline-edit. Date, presenter, and other fields each have an Edit button. Saves are immediate; there is no separate Save button at the page level.' },
          { q: 'Where does the export download live?', a: 'Open the Editor, then use the Export menu at the top of the editor toolbar. Picking a format generates the file and starts the download immediately.' },
        ],
      },
      admin: {
        intro: 'You see everything the user sees plus the rescue tools. If a session is stuck on any pipeline stage, this page plus the Editor Admin tab are where you fix it.',
        topics: [
          { q: 'How do I re-run a failed pipeline stage?', a: 'Open the Editor for the session, then go to the Admin tab. Each rescue button confirms before firing. Re-Ingest restarts everything from scratch; Re-Align rebuilds just the slide-to-segment matches; Abort forces the session to failed status if it is hung.' },
          { q: 'When should I retry versus abort?', a: 'Retry when the failure looks transient — a network blip, a Gemini rate limit, a one-off ffmpeg crash. Abort when the source media is bad and the session should not continue. Aborted sessions can be deleted from the Sessions list.' },
          { q: 'Can I edit who is assigned to which SOP stage?', a: 'Yes — the Stage Assignments card lets you set a person per stage. Each stage carries a default SLA in hours; the deadline email fires when the SLA elapses if email notifications are turned on.' },
        ],
      },
    },

    // ── Editor ───────────────────────────────────────────────
    editor: {
      title: 'Editor',
      user: {
        intro: 'The Editor is where you review and correct a transcript. Three panes: slides on the left, transcript in the middle, audit and reference tools on the right.',
        topics: [
          { q: 'How do I edit a transcript segment?', a: 'Click on the segment text in the middle pane to start editing. Type your change, then click Save. Use Cancel to drop the edit. Every save is reversible — open the Audit tab on the right to see your edit history and undo any change.' },
          { q: 'How do I change who said a segment?', a: 'Use the Speakers panel on the top right to rename, merge, or reassign speakers across the whole session. Changes apply to every segment that references the speaker, so a one-time rename fixes the entire transcript at once.' },
          { q: 'How do I move a chat or poll to a different time?', a: 'Drag the chat card or poll card from the right rail onto the transcript segment where it should appear. The card snaps to that segment\'s start time. You can drag again to re-anchor at any point, or drag it back to the right rail to detach it.' },
          { q: 'What do the colored chips above the transcript do?', a: 'They are filters. Click "Filler" to show only segments that contain filler words; click "Punctuation" to surface punctuation discrepancies; "Drift" finds places where the AI alignment looks shaky. Click a chip again to clear the filter.' },
          { q: 'How do I export the finished transcript?', a: 'Click the Export menu at the top of the Editor. Pick docx, srt, vtt, txt, or zip. The download starts immediately. Filler words like "um" and "uh" are removed from docx and txt for readability; srt and vtt keep them so the captions stay aligned to the audio.' },
        ],
      },
      admin: {
        intro: 'You see everything the editor user sees plus the Admin tab on the right rail. Use the Admin tab\'s Rescue section only when a session is stuck or needs to be re-processed from scratch.',
        topics: [
          { q: 'What does the Admin tab\'s Rescue section do?', a: 'Five operator buttons that re-run pipeline stages on a stuck session. Re-Ingest restarts the whole pipeline from upload; Re-Align rebuilds slide-to-segment matches; Init Session Stages assigns SOP stages for legacy sessions that predate that hook; Auto-Place Polls backfills poll anchors; Abort hard-fails the session.' },
          { q: 'When should I retry versus abort a session?', a: 'Retry when the failure was transient — a network blip, a Gemini quota cap, a one-off task crash. Abort when the source media is bad and the session should not continue. The Abort button asks twice before firing.' },
          { q: 'Where can I see who edited what?', a: 'Open the Audit tab on the right rail. Every edit is logged with the user, the timestamp, and the before/after text. Undo and Redo move a session-wide pointer backward and forward through the log.' },
        ],
      },
    },

    // ── SOP ──────────────────────────────────────────────────
    sop: {
      title: 'SOP workflow',
      user: {
        intro: 'The SOP workflow tracks a session through medical review, copy editing, and final approval. Each stage has an assignee, an SLA in hours, and a Done/Next button.',
        topics: [
          { q: 'What are the SOP stages?', a: 'Prep, Copy Draft, Medical, Copy Final, CMS, Captions, QA, Complete. The session moves forward when the assignee clicks Done on the current stage.' },
          { q: 'Who is the assignee for each stage?', a: 'Defaults come from Settings → SOP, but the admin can override per-session on the Session Detail page. The current assignee for each stage is shown right on the SOP page.' },
          { q: 'What happens if the SLA elapses?', a: 'A deadline email goes to the stage assignee on the next hourly check. Only one email per stage per day so you do not get spammed.' },
          { q: 'Can I skip a stage?', a: 'Only the admin can skip or re-open a stage. If you think a stage does not apply to your session, ask your admin to advance it.' },
        ],
      },
      admin: {
        intro: 'You can advance, skip, or re-open any stage; reassign the person on any stage; and see how the session has moved through the workflow.',
        topics: [
          { q: 'How do I reassign a stage?', a: 'Click the assignee name on the stage card and pick someone else from the dropdown. The deadline email throttle resets for that stage; if the SLA is already overdue, the new assignee gets the email on the next hourly check.' },
          { q: 'How do I change the SLA hours for a stage?', a: 'Per-session overrides live on the Session Detail page. Org-wide defaults live under Settings → SOP. Changes only affect sessions created after the change; existing sessions keep their snapshot.' },
          { q: 'A stage advanced when it should not have — what now?', a: 'Use the "Re-open stage" button on the stage card. The session goes back to that stage; everyone downstream is notified.' },
        ],
      },
    },

    // ── Upload ───────────────────────────────────────────────
    upload: {
      title: 'Upload',
      user: {
        intro: 'The Upload page is where new sessions start. Pick a video or audio file, configure the processing options, and start the pipeline.',
        topics: [
          { q: 'What file types can I upload?', a: 'MP4, MOV, and WAV for video and audio. PDFs for slide decks. The upload page rejects other types up front.' },
          { q: 'What is the difference between AI Mode and Default Mode?', a: 'AI Mode sends the media directly to Gemini for a richer transcript with speaker labels and slide markers. Default Mode runs the standard cloud transcription, which is faster and cheaper but plainer. Pick AI Mode for clinical content where speaker attribution and slide alignment matter; pick Default for quick passes.' },
          { q: 'Why is my upload slow?', a: 'Uploads go directly from your browser to cloud storage, so the speed is your local upload speed. Large videos take time. The page shows a progress bar — leave the tab open until it reaches 100%.' },
          { q: 'My upload says it is stuck.', a: 'If progress sits at 100% for more than five minutes, refresh the page and try once more. If it still hangs, contact your admin.' },
        ],
      },
    },

    // ── Improvements ─────────────────────────────────────────
    improvements: {
      title: 'Improvements',
      user: {
        intro: 'The Improvements page surfaces patterns the system has noticed across many sessions — speakers who frequently get misidentified, slide decks that consistently drift, prompt templates that struggle on certain content types.',
        topics: [
          { q: 'How do I use the suggestions here?', a: 'Each card is a suggestion you can accept or dismiss. Accepting an "always rename X to Y" suggestion adds it to your team\'s name-fix list so future sessions auto-apply the correction.' },
          { q: 'Where do these patterns come from?', a: 'The system watches the edits your team makes in the Editor. When the same correction shows up in five or more sessions, it surfaces here as a pattern worth automating.' },
        ],
      },
      admin: {
        intro: 'You can publish or retire team-wide patterns and see the analytics behind each one.',
        topics: [
          { q: 'How do I retire a pattern that is no longer helpful?', a: 'Open the pattern card and click "Retire". Future sessions will no longer auto-apply it; existing sessions keep the corrections that were already applied.' },
        ],
      },
    },

    // ── Settings ─────────────────────────────────────────────
    settings: {
      title: 'Settings',
      admin: {
        intro: 'Admin-only home for users, roles, email templates, SOP defaults, prompt templates, and rescue diagnostics. Non-admins are redirected away from this page.',
        topics: [
          { q: 'Auth Users — what do I edit here?', a: 'The list of people who can sign in to rounds.vin. Each row has email, name, and role. New users get an initial password you set on creation; they change it on first login.' },
          { q: 'SOP defaults — what changes when I edit these?', a: 'You set the default SLA hours per stage and the default assignee. New sessions adopt these on creation; existing sessions keep the snapshot they were created with.' },
          { q: 'Email Templates — how do I preview before sending?', a: 'Each template has a Preview button. The preview renders against a fake session so you can see exactly what the assignee will receive.' },
          { q: 'Prompt Templates — what are these for?', a: 'Each prompt template tells the AI how to transcribe a session — what tone to use, how to handle filler words, what slide-marker convention to use. Pick a template per session at upload time.' },
        ],
      },
    },

    // ── Audit ────────────────────────────────────────────────
    audit: {
      title: 'Audit',
      user: {
        intro: 'The Audit view shows every change made to a session — transcript edits, speaker re-assignments, chat or poll moves, find-and-replace operations.',
        topics: [
          { q: 'How do I undo an edit?', a: 'Open the Audit tab in the Editor, find the edit you want to roll back, and click Undo. The whole session moves back one step. Click Redo to move forward again.' },
          { q: 'Can I see who made a change?', a: 'Yes — every audit row shows the user email, the timestamp, and the before/after text.' },
          { q: 'How far back does the audit history go?', a: 'Every edit since the session was created. Nothing is ever deleted from the audit log.' },
        ],
      },
    },

    // ── Viewer ───────────────────────────────────────────────
    viewer: {
      title: 'Viewer',
      user: {
        intro: 'The Viewer is a read-only render of a finished session — the video alongside the transcript with chat and poll anchors in place. Use it for sharing or playback after the editing is done.',
        topics: [
          { q: 'Can I edit from the Viewer?', a: 'No — the Viewer is read-only. To make edits, open the session in the Editor instead.' },
          { q: 'How do I share a session with someone outside rounds.vin?', a: 'Export the session as an HTML or zip from the Editor. The download contains everything someone needs to view it offline.' },
        ],
      },
    },

    // ── Processing ───────────────────────────────────────────
    processing: {
      title: 'Processing',
      user: {
        intro: 'The Processing page is what you see while a session is being ingested or transcribed. It shows the current pipeline stage and a live progress bar.',
        topics: [
          { q: 'How long does processing take?', a: 'A typical hour of video takes about ten to fifteen minutes to fully process. AI Mode is slower than Default Mode. Large slide decks add a minute or two for slide extraction.' },
          { q: 'I see "Failed" — what now?', a: 'Click the session to see the failure reason. Most failures are transient — a Gemini quota hit, a network blip — and an admin can re-ingest the session with one click.' },
        ],
      },
    },

    // ── Help (self-referential) ──────────────────────────────
    help: {
      title: 'Help',
      user: {
        intro: 'You are looking at it. The Help Center is contextual — open it on any page and it shows tips for that page first.',
        topics: [
          { q: 'How do I open the Help Center?', a: 'Click the question-mark button in the top bar, or press the ? key when no input is focused. Press Esc to close.' },
          { q: 'How does the search work?', a: 'Type two or more characters and the search bar finds matching topics across every page and the FAQ. Right now search is exact-word matching; a smarter semantic search lands in the next release.' },
          { q: 'When will Ask AI work?', a: 'The Ask AI tab is in the next release. For now use the search bar above or browse the tabs.' },
        ],
      },
    },
  },

  // ── Cross-cutting FAQs ────────────────────────────────────
  faq: [
    { q: 'I forgot my password — what do I do?', a: 'Contact your admin to set a new initial password. Five failed sign-in attempts in fifteen minutes will briefly lock the account; wait it out, then sign in with the new password.' },
    { q: 'How long do sessions last?', a: 'You stay signed in for up to a week of activity. After a short period of inactivity the app may quietly refresh your session in the background so you do not lose your place.' },
    { q: 'What is the difference between AI Mode and Default Mode?', a: 'AI Mode uses Gemini for transcription with built-in slide markers and speaker attribution. Default Mode uses standard cloud transcription, which is faster and cheaper but plainer. Pick AI Mode for clinical content where attribution matters; pick Default for quick passes.' },
    { q: 'Why does the app sometimes say "Slow down"?', a: 'A safety limit guards the AI pipeline from accidental bursts of work. Wait a few seconds and try the action again.' },
    { q: 'Can I retry a failed session safely?', a: 'Yes. Re-ingest restarts the pipeline from upload; the system is built so re-runs are idempotent. Only admins can fire re-ingest.' },
    { q: 'Where can I see who edited a transcript?', a: 'Open the session in the Editor, then click the Audit tab on the right rail. Every edit is logged with the user, timestamp, and before/after text.' },
    { q: 'What happens when I archive a session?', a: 'Archive moves the session out of the active Sessions list but keeps the data intact. Admins can restore it any time. Permanent purge actually removes the data and cannot be undone.' },
    { q: 'Where do exports come from?', a: 'The Export menu in the Editor generates the file fresh from the current transcript every time. Filler words are stripped from docx and txt; srt and vtt keep them so captions stay aligned to the audio.' },
    { q: 'How do I use this help panel?', a: 'The "This page" tab shows tips for the page you are on. FAQ has cross-cutting questions. Ask AI is in the next release. Search any tab from the box at the top.' },
    { q: 'Where can I learn more?', a: 'Click "Full docs" at the bottom of this panel for the detailed user guide. For bug reports or feature ideas, reach your admin.' },
  ],

  // ── Contact ───────────────────────────────────────────────
  contact: {
    email: 'johndean@vin.com',
    slack: '#rounds-help',
    docs:  'rounds.vin/docs',
  },
};
