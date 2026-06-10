# Signing in and access

## What This Does

Signing in is how you get into rounds.vin. You enter the email and password
your administrator set up for you, and the app keeps you signed in while you
work so you can move between the dashboard, your sessions, and the editor
without signing in again each time.

## Who Can Use It

Anyone with an account can sign in. Accounts are created for you by an
administrator — there is no public sign-up and no "create account" link on the
sign-in screen. If you do not have an account yet, ask your administrator to
add you.

## How To Access

Open rounds.vin in your browser. If you are not signed in, the app sends you
straight to the sign-in screen. You will see:

- An **Email** field — enter the address your account was created under.
- A **Password** field.
- A **Keep me signed in** option.
- A **Sign in** button.

Type your email and password and click **Sign in**. When it works, you are
taken to your dashboard (or back to whatever page you were trying to reach
before you were asked to sign in).

## How To Create

You cannot create your own account from the sign-in screen. New accounts are
set up by an administrator, who gives you a starting password. The first time
you sign in, use the email and password they gave you.

## How To Edit

There is no self-service "change my password" or "edit my profile" screen in
the app today. If your email or password needs to change, ask your
administrator to update it for you.

## How To Delete

You cannot remove your own account. Account removal is handled by an
administrator.

## Common Tasks

**Sign in.** Enter your email and password and click **Sign in**.

**Stay signed in.** Leave the **Keep me signed in** option on. Your session
lasts for a fixed window of activity, so you will not be asked to sign in again
in the middle of a working session. When that window ends, you will be returned
to the sign-in screen and can sign in again.

**Sign out.** Use the sign-out control in the top bar. This clears your session
on this device and returns you to the sign-in screen.

**Get back to where you were.** If your session ends while you are on a
specific page and you sign in again, the app returns you to that page rather
than dropping you on a generic landing screen.

## Troubleshooting

**"Incorrect email or password."** Double-check the email address — it must
match exactly the one your account was created under — and re-type the
password. Passwords are case-sensitive. If you still cannot get in, ask your
administrator to confirm your account is active and to reset your password.

**I get sent back to the sign-in screen on every page.** Your session has
ended or your browser is blocking the app from remembering you. Sign in once
more with **Keep me signed in** turned on. If you are in a private/incognito
window, the app may not be able to remember your session between page loads.

**The app says "Slow down" or refuses an action.** A safety limit protects the
processing pipeline from too many things happening at once. Wait a few seconds
and try again. If you see a message about being "at the maximum number of
concurrent sessions," finish or clean up an in-progress session before starting
a new one.

**I am signed in but cannot reach a certain page.** A small number of pages are
reserved for administrators. If you are redirected back to your dashboard when
you try to open one, that page is not available to your account — that is
expected.

## FAQs

**I forgot my password — what do I do?**
Contact your administrator to set a new password, then sign in with it.

**How long do I stay signed in?**
You stay signed in for a fixed window of activity. When it ends you are
returned to the sign-in screen and can sign in again.

**Can I change my own password in the app?**
No. Password changes are handled by an administrator.

**Why was I sent to the sign-in screen in the middle of working?**
Your session window ended, or your browser cleared the app's stored session.
Sign in again — you will be returned to the page you were on.

**Is there a sign-up link?**
No. Accounts are created by an administrator.

## Permissions Required

You need an active account (an email and password set up by an administrator)
to sign in. Once signed in, you can reach the standard pages — dashboard,
sessions, session detail, upload, editor, and the help center. A small set of
administrator-only pages will redirect you back to your dashboard if your
account is not the administrator account.

---

## Source Verification
- **Files Used:** frontend/src/views/LoginView.vue, frontend/src/stores/auth.ts, frontend/src/router/index.ts, app/api/auth.py, app/auth.py, app/services/auth_users.py, app/middleware/rate_limit.py, app/middleware/envelope.py, docs/help-center/faq.md, frontend/src/constants/help-content.ts
- **Components Used:** LoginView.vue (sign-in form), router `beforeEach` guard, useAuthStore (login/logout/bootstrap)
- **APIs Used:** POST /v1/auth/login ([app/api/auth.py:15](../app/api/auth.py#L15)), GET /v1/auth/me ([app/api/auth.py:31](../app/api/auth.py#L31))
- **Database Tables Used:** auth_users (login lookup, bcrypt verify) — [app/auth.py:100](../app/auth.py#L100); AUTH_USERS env CSV fallback
- **Permission Logic Used:** JWT presence (router guard [frontend/src/router/index.ts:59](../frontend/src/router/index.ts#L59)) + client-side adminOnly guard comparing `auth.email` to LEGACY_ADMIN_EMAIL `johndean@vin.com` ([frontend/src/router/index.ts:63](../frontend/src/router/index.ts#L63)). Role-based auth (app/security/roles.py) is scaffold-only and not wired into the login path.
- **Confidence Score:** Medium — sign-in flow, token, and guard are fully code-verified; the seed/in-app FAQ claim of a "5 failed attempts in 15 minutes" account lockout is NOT IMPLEMENTED IN CODE (no attempt counter or lockout exists in app/auth.py or app/services/auth_users.py), so it was deliberately omitted from the body.
- **Evidence Links:** [app/auth.py:100](../app/auth.py#L100) (authenticate, no lockout), [app/auth.py:153](../app/auth.py#L153) (8-hour token), [frontend/src/views/LoginView.vue:88](../frontend/src/views/LoginView.vue#L88) ("Keep me signed in for 8 hours"), [app/middleware/rate_limit.py:43](../app/middleware/rate_limit.py#L43) (concurrent-session 429), [frontend/src/router/index.ts:63](../frontend/src/router/index.ts#L63) (adminOnly redirect)
