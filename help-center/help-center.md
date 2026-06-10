# Help Center

## What This Does

The Help Center is the in-app help panel. It slides in over whatever page you are
on and shows tips for that page first, so the help you see is matched to where
you are. It has three tabs — **This page**, **FAQ**, and **Ask AI** — plus a
search box that looks across every page's tips and the FAQ at once. At the bottom
there is a link to the full documentation.

## Who Can Use It

Anyone signed in can open the Help Center on any page. The tips adjust to your
account: admins see admin-oriented guidance for a page where it exists, and
everyone else sees the standard version. The panel header tells you which
audience the current tips are written for.

## How To Access

Click the question-mark button in the top bar to open the panel; click the close
button or press **Esc** to close it. When it opens, the search box is focused so
you can start typing right away, and the **This page** tab is selected.

## How To Create

There is nothing to create in the Help Center — it is a place to read help and
ask questions, not to author content. If the Ask AI tab is turned on for your
workspace, you can ask questions there and get answers (see How To Edit and
Common Tasks); those are conversations, not saved records.

## How To Edit

The Help Center content is read-only to you as a reader. The one interactive,
editable surface is the **Ask AI** tab, when it is enabled:

- Type your question in the box at the bottom (it needs at least a couple of
  characters).
- Press **Cmd/Ctrl + Enter**, or click **Ask**, to send it.
- The answer appears in the thread above, with a numbered list of the help
  articles it drew from.
- Click **Clear thread** to start over, or **Cancel** while an answer is still
  coming back.

If Ask AI is not enabled for your workspace, the tab still appears but shows a
"coming soon" note instead of the question box — use the search bar or the other
tabs in the meantime.

## How To Delete

There is nothing to delete. The only thing you can clear is your Ask AI
conversation, using the **Clear thread** button on that tab. Closing the panel
does not erase anything you might need later — your place in the app is kept.

## Common Tasks

- **Get help for the page you are on.** Open the panel; the **This page** tab is
  already showing tips for your current page.
- **Look something up across all help.** Type two or more characters in the
  search box. Matching tips and FAQ entries appear, with the closest title
  matches first. Click the X in the box to clear the search and return to the
  tabs.
- **Browse common questions.** Click the **FAQ** tab for the cross-cutting
  questions.
- **Ask a free-form question.** Click **Ask AI** (if enabled), type your
  question, and send it with Cmd/Ctrl + Enter. The answer cites the articles it
  came from.
- **Open the full documentation.** Click **Full docs** at the bottom of the
  panel.

## Troubleshooting

- **Search shows no results.** It matches on the words you type, so try different
  or shorter words. You need at least two characters before it searches. The
  empty state suggests trying the Ask AI tab.
- **The Ask AI tab just says "coming soon."** Ask AI is turned off for your
  workspace right now. Use the search bar or the This page and FAQ tabs instead.
- **Ask AI says I have hit a limit.** There is an hourly cap on questions. Wait a
  few minutes and try again.
- **The tips look generic for this page.** Not every page has its own tailored
  tips yet. When a page has none, the panel points you to the FAQ, search, or Ask
  AI.
- **The panel will not close.** Click the close button in its header, or press
  **Esc**.

## FAQs

**How do I open and close the Help Center?**
Click the question-mark button in the top bar to open it. Click the close button
or press Esc to close it.

**What are the three tabs?**
**This page** shows tips for the page you are on, **FAQ** has the cross-cutting
questions, and **Ask AI** lets you ask a free-form question (when it is enabled).

**How does search work?**
Type two or more characters and it matches your words against every page's tips
and the FAQ, listing title matches first. It is word-matching, not a
conversation — for free-form questions use Ask AI.

**Is Ask AI always available?**
No. It is controlled per workspace. When it is on, you get a working question box
whose answers cite the help articles they came from; when it is off, the tab
shows a "coming soon" note.

**Why do the tips differ between me and a teammate?**
The panel shows audience-specific tips. Admins see admin guidance where it
exists; everyone else sees the standard tips. The header names which audience the
current tips are for.

**Where is the full documentation?**
The **Full docs** link at the bottom of the panel.

## Permissions Required

You must be signed in to open the Help Center. The tips you see depend on whether
your account is an admin — admins get admin-oriented guidance where it exists,
everyone else gets the standard tips — but the panel itself is available to every
signed-in account. Whether the Ask AI tab is usable depends on a workspace-level
setting, not on your individual role.

## Source Verification
- **Files Used:** frontend/src/components/help/HelpPanel.vue, frontend/src/components/help/HelpAskComposer.vue, frontend/src/stores/help.ts, frontend/src/services/helpApi.ts, frontend/src/components/AppHeader.vue, frontend/src/constants/help-content.ts, frontend/src/composables/useIsAdmin.ts, frontend/src/components/help/HelpFaqAccordion.vue, frontend/src/services/helpArticlesApi.ts, docs/help-center/faq.md, docs/help-center/articles.md
- **Components Used:** AppHeader.vue (top-bar "?" button → help.toggle; fetches /v1/version on mount to set the Ask AI flag), HelpPanel.vue (three tabs, search box, audience-based role label, Esc-to-close, Full-docs link, FAQ API-with-fallback), HelpAskComposer.vue (Ask AI thread, Cmd/Ctrl+Enter, Ask/Cancel/Clear thread, citations), HelpFaqAccordion.vue
- **APIs Used:** GET /v1/version (help_ask_ai_enabled flag), GET /v1/help/articles (FAQ tab, with hardcoded fallback), POST /v1/help/ask (Ask AI answer + sources; 429 hourly rate limit)
- **Database Tables Used:** none read directly by this panel for the page-tip content (it is bundled in constants/help-content.ts); FAQ tab reads published help articles via /v1/help/articles when present
- **Permission Logic Used:** JWT presence to use the app; audience selection (admin vs everyone) via LEGACY_ADMIN_EMAIL_CLIENT === 'johndean@vin.com' (useIsAdmin / HelpPanel role computed); Ask AI availability gated by the backend help_ask_ai_enabled flag, not by role
- **Confidence Score:** High — tabs, search threshold (≥2 chars), Esc-close, role label, FAQ API/fallback, and the Ask-AI enabled/coming-soon split all read directly from HelpPanel.vue, HelpAskComposer.vue, the help store, and AppHeader.vue.
- **Evidence Links:** [frontend/src/components/AppHeader.vue (? button → help.toggle)](../frontend/src/components/AppHeader.vue#L165), [frontend/src/components/AppHeader.vue (help_ask_ai_enabled from /v1/version)](../frontend/src/components/AppHeader.vue#L58), [frontend/src/components/help/HelpPanel.vue (three tabs + Esc close)](../frontend/src/components/help/HelpPanel.vue#L233), [frontend/src/components/help/HelpPanel.vue (Ask AI enabled vs coming-soon)](../frontend/src/components/help/HelpPanel.vue#L346), [frontend/src/components/help/HelpAskComposer.vue (Cmd/Ctrl+Enter submit + citations)](../frontend/src/components/help/HelpAskComposer.vue#L49), [frontend/src/stores/help.ts (search ≥2 chars)](../frontend/src/stores/help.ts#L104)

> Maintainer note: the panel footer and the seed copy both say "Press ? to open."
> No global "?" keydown handler is wired anywhere in frontend/src (grep for the
> "?" key found none; HelpPanel only binds Esc-to-close). The verified way to open
> the panel is the top-bar question-mark button (AppHeader.vue: @click="help.toggle").
> This article documents the button (verified) and Esc-to-close (verified) and
> deliberately does not assert the "?" keypress works. Likewise, the seed FAQ says
> "Ask AI is in the next release" — but the code wires a real POST /v1/help/ask
> backend behind the help_ask_ai_enabled flag, so this article describes Ask AI as
> conditionally enabled rather than uniformly unavailable.
