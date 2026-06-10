# Settings

## What This Does

Settings is the workspace control panel. It groups every system-wide preference
into one place with a list of sections down the left and the active section's
form on the right. From here you manage who can sign in, set workspace defaults
(name, language, time zone), tune how the AI transcribes and classifies, shape
the export and email behavior, maintain the prompt templates that uploads choose
from, and reach the diagnostics and deleted-session recovery tools.

The sections you will see are: General, Team & roles, Types & stage defaults,
AI models, Upload & storage, Discrepancy classification, Export, Prompt
templates, Session manifest, Email, Auth & logins, Diagnostics, and Deleted
sessions.

## Who Can Use It

Settings is intended for admins. The page itself opens for anyone signed in, but
the work it does — listing logins, changing defaults, editing templates — runs
against admin-only operations on the server. If your account is not an admin,
those sections load empty and show an "Admin only" message instead of data, and
your changes will not save. In practice, treat Settings as an admin area.

## How To Access

Click **Settings** in the top bar. You land on the General section by default.
Click any section name in the left-hand list to switch to it; the address bar
updates so you can bookmark or share a link straight to a specific section.

## How To Create

What you can create here depends on the section:

- **Auth & logins** — add a new login. Enter the person's email, set an initial
  password (at least 10 characters), choose whether they are a user or an admin,
  and click **Add user**. Share the password with them privately — it is stored
  scrambled and can never be shown again, so if it is lost you reset it rather
  than look it up.
- **Prompt templates** — create a new template that tells the AI how to
  transcribe a session: the tone to use, how to treat filler words, and the
  slide-marker convention. Templates you create here become selectable on the
  Upload page.
- **Email** — build and save notification templates.

## How To Edit

- **General** — change the workspace name, default language, and time zone, then
  click **Save**.
- **Auth & logins** — for any login you can switch its role between user and
  admin, disable or re-enable it, or reset its password. Resetting asks for a new
  password (again at least 10 characters); the new password is never echoed back.
- **Types & stage defaults** — set the default owner and the deadline (in hours)
  for each workflow stage. New sessions pick up these defaults when they are
  created; sessions that already exist keep the values they started with.
- **AI models, Upload & storage, Discrepancy classification, Export, Session
  manifest** — adjust the matching system defaults in each section's form and
  save.
- **Email** — open a template, edit it, and use its **Preview** to see exactly
  what a recipient will get before you rely on it.

Most sections save when you click the section's **Save** button. Auth & logins
applies each action (role, status, reset, delete) immediately.

## How To Delete

- **Auth & logins** — click **Delete** on a login to remove its access right
  away. You are asked to confirm first, and it cannot be undone. The system will
  refuse to delete the last remaining active admin so you cannot lock everyone
  out.
- **Deleted sessions** — this section is where soft-deleted sessions can be
  restored or permanently purged. Purging removes the data for good.

There is no "delete the whole Settings page" — Settings is the control panel
itself, not a record you remove.

## Common Tasks

- **Add a teammate.** Auth & logins → fill in email + initial password → pick
  user or admin → Add user → send them the password privately.
- **Make someone an admin (or take it away).** Auth & logins → find their row →
  **Make admin** / **Make user**.
- **Lock out a departing teammate.** Auth & logins → **Disable** their row (keeps
  the record) or **Delete** it (removes access entirely).
- **Reset a forgotten password.** Auth & logins → **Reset password** on their row
  → type a new one → share it privately.
- **Change the workspace time zone or name.** General → edit → Save.
- **Add a new transcription style.** Prompt templates → create a template → it
  shows up on the Upload page.

## Troubleshooting

- **A section loads empty and says "Admin only."** Your account is not an admin,
  so that section's data is not available to you. Ask an admin to make the change
  or to grant you admin access.
- **"No logins in the database."** The login list is empty. Either add a login
  with the form, or — if logins existed before and vanished — use the **Seed from
  environment** button shown in that empty state to restore them. It is safe to
  click more than once.
- **The Add user button stays greyed out.** The helper line under the form tells
  you why: you still need an email, or the password is shorter than 10
  characters. Fix what it names and the button turns on.
- **My change did not save.** If you are not an admin, saves are rejected on the
  server. Confirm you are signed in as an admin and try again.

## FAQs

**Why can I open Settings but not change anything?**
The page opens for any signed-in account, but the changes run against admin-only
operations. Without admin access the sections load empty and saves are refused.

**Where do I manage who can sign in?**
The **Auth & logins** section. Each row shows the email, role, status, last
sign-in, and when the password was last set, with buttons to reset the password,
flip the role, disable or enable, and delete.

**How long do passwords need to be?**
At least 10 characters, both when adding a login and when resetting one.

**Can I see a user's current password?**
No. Passwords are stored scrambled and never shown. If one is lost, reset it to a
new value rather than looking it up.

**What do prompt templates do?**
Each template tells the AI how to transcribe — tone, how to handle filler words,
and the slide-marker convention. You pick a template per session on the Upload
page.

**If I change a stage's default deadline, does it affect sessions already in
flight?**
No. Defaults apply to sessions created after the change. Existing sessions keep
the values they were created with.

## Permissions Required

You must be signed in to open Settings. Every section's data and every save
depends on admin-level access, which the server enforces; non-admin accounts see
empty sections and an "Admin only" message and cannot save. Admin status today is
tied to a specific account rather than a general role tier.

## Source Verification
- **Files Used:** frontend/src/views/SettingsView.vue, frontend/src/components/settings/SectionGeneral.vue, frontend/src/components/settings/SectionAuthUsers.vue, frontend/src/components/AppHeader.vue, frontend/src/router/index.ts, frontend/src/composables/useIsAdmin.ts, frontend/src/constants/help-content.ts, docs/help-center/articles.md, docs/help-center/faq.md
- **Components Used:** SettingsView.vue (left-nav section list + content pane, 13 sections), SectionGeneral.vue (org name / locale / timezone + Save), SectionAuthUsers.vue (add login, role toggle, disable/enable, reset password, delete, reseed-from-env empty state), AppHeader.vue (Settings nav link, visible to all)
- **APIs Used:** GET/PUT /v1/settings (org_name, default_locale, default_timezone), GET /v1/settings/auth-users, POST /v1/settings/auth-users, PATCH /v1/settings/auth-users/{id} (role / is_active), POST /v1/settings/auth-users/{id}/reset-password, DELETE /v1/settings/auth-users/{id}, POST /v1/diag/reseed-auth-users
- **Database Tables Used:** org_settings, auth_users
- **Permission Logic Used:** JWT presence to load the page (no client route guard on /settings); admin authorization enforced server-side on /v1/settings/auth-users* (returns 403 → "Admin only" toast). Admin identity = LEGACY_ADMIN_EMAIL gate (johndean@vin.com); auth_users.role exists but is the data being edited, not the live get_current_user gate.
- **Confidence Score:** High — section list, add/reset/role/disable/delete flows, and the 10-char password rule read directly from SettingsView.vue and SectionAuthUsers.vue; admin gating confirmed as server-side 403 handling, not a client redirect.
- **Evidence Links:** [frontend/src/views/SettingsView.vue (section list)](../frontend/src/views/SettingsView.vue#L38), [frontend/src/components/settings/SectionAuthUsers.vue (add + 10-char rule)](../frontend/src/components/settings/SectionAuthUsers.vue#L115), [frontend/src/components/settings/SectionAuthUsers.vue (403 → Admin-only toast)](../frontend/src/components/settings/SectionAuthUsers.vue#L82), [frontend/src/router/index.ts (no /settings guard; only /admin/help is adminOnly)](../frontend/src/router/index.ts#L44)

> Maintainer note: the seed help-content.ts says of Settings, "Non-admins are
> redirected away from this page." The router (router/index.ts) does NOT guard
> /settings — only /admin/help carries meta.adminOnly. Non-admins reach the page;
> the gate is server-side (403 on the auth-users endpoints, surfaced as an
> "Admin only" toast in SectionAuthUsers.vue). This article describes the
> verified behavior (page opens, data/saves blocked) rather than a redirect.
