# Login Screen

Route: `#/login` (public). View: [frontend/src/views/LoginView.vue](../../frontend/src/views/LoginView.vue).

## Purpose

Single sign-in form for the operator console. Collects an email + password, exchanges them for a JWT via the auth store, and on success redirects to the originally-requested route (or `/dashboard`). It is the only public (unauthenticated) route in the app — every other route requires an authenticated session ([frontend/src/router/index.ts:53-68](../../frontend/src/router/index.ts#L53-L68)).

## User Types

Any user with valid credentials in the backend auth store. The login form itself draws no distinction between user roles — it submits email + password and the backend decides whether to issue a token. Role-based tiers are not enforced here (see Permissions).

## Entry Points

- The router guard redirects any unauthenticated navigation to `#/login`, carrying the attempted path in a `next` query param ([frontend/src/router/index.ts:59-62](../../frontend/src/router/index.ts#L59-L62)).
- A failed token bootstrap (bad/expired JWT) clears the token in the auth store ([frontend/src/stores/auth.ts:36-41](../../frontend/src/stores/auth.ts#L36-L41)); the next guarded navigation then lands here.
- Direct navigation to `#/login`.

## Navigation Paths

- On successful sign-in: `router.replace(target)` where `target = route.query.next || '/dashboard'` ([frontend/src/views/LoginView.vue:40-41](../../frontend/src/views/LoginView.vue#L40-L41)).
- The screen exposes no other navigation links. There is no "forgot password", "sign up", or "SSO" link in the template — those affordances are absent (`IMPLEMENTATION NOT FOUND`).

## Components

All markup is inline in `LoginView.vue`; no shared child components are imported (only the `toast` composable and the auth store).

- `main.login` wrapper with a `login__bg` decorative div ([LoginView.vue:47-48](../../frontend/src/views/LoginView.vue#L47-L48)).
- `form.login__card` — submit handler `signIn` ([LoginView.vue:49](../../frontend/src/views/LoginView.vue#L49)).
- `login__brand` block — VIN logo (`/assets/VIN.svg`) plus the "TRANSCRIPT.SOFTWARE" wordmark and "VIN Transcript Operations Console" subtitle ([LoginView.vue:50-56](../../frontend/src/views/LoginView.vue#L50-L56)).
- `login__title` ("Sign in"), a `login__pill` build badge, and a `login__lead` description ([LoginView.vue:58-62](../../frontend/src/views/LoginView.vue#L58-L62)).
- Email input — `v-model="email"`, `type="email"`, `autofocus`, `data-test-id="login-email"` ([LoginView.vue:64-74](../../frontend/src/views/LoginView.vue#L64-L74)).
- Password input — `v-model="pw"`, `type="password"`, `data-test-id="login-password"` ([LoginView.vue:76-85](../../frontend/src/views/LoginView.vue#L76-L85)).
- A "Keep me signed in for 8 hours" checkbox rendered `checked` ([LoginView.vue:87-91](../../frontend/src/views/LoginView.vue#L87-L91)). Note: this checkbox is static markup — it has no `v-model` and its value is never read by `signIn`. The "8 hours" copy is descriptive only; the actual token TTL is decided by the backend `/v1/auth/login` response.
- Submit button — label toggles between "Sign in" and "Signing in…" via `busy`, disabled while `busy`, `data-test-id="login-submit"` ([LoginView.vue:93-95](../../frontend/src/views/LoginView.vue#L93-L95)).
- `login__foot` showing the build SHA ([LoginView.vue:97-99](../../frontend/src/views/LoginView.vue#L97-L99)).

The build badge text (`bundleShort`) is derived from `import.meta.env.VITE_BUILD_SHA`, defaulting to `dev` for local builds ([LoginView.vue:13-16](../../frontend/src/views/LoginView.vue#L13-L16)).

## Actions

- **Submit form** (`signIn`) — triggered by the form's `@submit` or the submit button ([LoginView.vue:26-42](../../frontend/src/views/LoginView.vue#L26-L42)):
  1. `e.preventDefault()`.
  2. Client-side guard: if either `email` or `pw` is empty, push a `warn` toast "Email and password required" and return ([LoginView.vue:28-31](../../frontend/src/views/LoginView.vue#L28-L31)).
  3. Set `busy = true`, call `auth.login(email, pw)`, then `busy = false`.
  4. On failure, toast `auth.error ?? 'Sign in failed'` with tone `error`.
  5. On success, toast `Welcome back, <email-localpart>` with tone `success`, then `router.replace(target)`.

The auth store's `login` lowercases + trims the email, calls `authApi.login`, stores the returned `access_token`, then calls `authApi.me()` to capture the canonical email ([frontend/src/stores/auth.ts:44-64](../../frontend/src/stores/auth.ts#L44-L64)).

## States

- **Idle** — submit button reads "Sign in", inputs enabled.
- **Submitting** — `busy = true`; submit button reads "Signing in…" and is disabled ([LoginView.vue:93-95](../../frontend/src/views/LoginView.vue#L93-L95)). Inputs themselves are not disabled during submit.

## Empty States

Not applicable — this is a form, not a data list. The only "empty" handling is the client-side required-field check that toasts when email or password is blank ([LoginView.vue:28-31](../../frontend/src/views/LoginView.vue#L28-L31)).

## Error States

There is no inline error region in the template. All errors surface as toasts:
- Missing field → `warn` toast "Email and password required".
- Login failure → `error` toast with `auth.error` ([LoginView.vue:35-38](../../frontend/src/views/LoginView.vue#L35-L38)). The store maps HTTP 401 to "Incorrect email or password"; any other error becomes the thrown message or "Login failed" ([frontend/src/stores/auth.ts:54-60](../../frontend/src/stores/auth.ts#L54-L60)).

## Loading States

The only loading indicator is the `busy` flag, surfaced as the "Signing in…" button label and the disabled button ([LoginView.vue:32-34](../../frontend/src/views/LoginView.vue#L32-L34), [LoginView.vue:93-95](../../frontend/src/views/LoginView.vue#L93-L95)). No spinner component is used.

## Permissions

This route is `meta: { public: true }`, so the router guard lets it through without any auth check ([frontend/src/router/index.ts:29](../../frontend/src/router/index.ts#L29), [:54-57](../../frontend/src/router/index.ts#L54)).

The login form does not perform any role check. Authorization in this app is JWT-presence-based: `isAuthenticated` is simply `Boolean(email && getToken())` ([frontend/src/stores/auth.ts:28](../../frontend/src/stores/auth.ts#L28)). There is no role tier evaluated at login — the backend `/v1/auth/login` issues a token if credentials match, and `/v1/auth/me` returns only `{ email }` ([frontend/src/services/api.ts:33](../../frontend/src/services/api.ts#L33)). The client-side admin gate (`auth.email === LEGACY_ADMIN_EMAIL`) exists only for the `adminOnly` route guard ([frontend/src/router/index.ts:51](../../frontend/src/router/index.ts#L51), [:63-66](../../frontend/src/router/index.ts#L63)) and is not exercised by login.

## Connected APIs

Traced through `auth.login` ([frontend/src/stores/auth.ts:48-52](../../frontend/src/stores/auth.ts#L48-L52)) → `authApi`:

- `POST /v1/auth/login` — form-encoded `{ username, password }`, `anonymous: true` (no bearer header) ([frontend/src/services/api.ts:28-32](../../frontend/src/services/api.ts#L28-L32)). Backend: [app/api/auth.py:15](../../app/api/auth.py#L15).
- `GET /v1/auth/me` — called immediately after a successful login to capture the canonical email ([frontend/src/services/api.ts:33](../../frontend/src/services/api.ts#L33)). Backend: [app/api/auth.py:31](../../app/api/auth.py#L31).

## Data Sources

- **Auth store** ([frontend/src/stores/auth.ts](../../frontend/src/stores/auth.ts)) — owns `email`, `error`, `isLoading`, `isAuthenticated`, `login`, `bootstrap`, `logout`. The JWT is persisted to `localStorage` via `services/http.ts` `setToken`/`getToken`; the email is persisted under key `rounds_user_email_v1` ([frontend/src/stores/auth.ts:12](../../frontend/src/stores/auth.ts#L12)).
- **Build SHA** — `import.meta.env.VITE_BUILD_SHA`, injected at Docker build time ([LoginView.vue:13-16](../../frontend/src/views/LoginView.vue#L13-L16)).
- **`toast` composable** ([frontend/src/composables/useToast](../../frontend/src/composables/useToast.ts)) — used for all user feedback.

## Source Verification
- **Files Used:** frontend/src/views/LoginView.vue, frontend/src/stores/auth.ts, frontend/src/router/index.ts, frontend/src/services/api.ts, app/api/auth.py
- **Components Used:** none (inline markup only; toast composable used)
- **APIs Used:** POST /v1/auth/login, GET /v1/auth/me
- **Database Tables Used:** none directly from the view (backend `/v1/auth/*` reads the auth store; not touched by this view)
- **Permission Logic Used:** JWT presence only (route is `meta.public`; no role check at login)
- **Confidence Score:** High — the view is short, fully read, and every API call traces to a verified backend route.
- **Evidence Links:** [LoginView.vue:26-42](../../frontend/src/views/LoginView.vue#L26-L42), [auth.ts:44-64](../../frontend/src/stores/auth.ts#L44-L64), [api.ts:27-34](../../frontend/src/services/api.ts#L27-L34), [router/index.ts:54-67](../../frontend/src/router/index.ts#L54-L67), [app/api/auth.py:15](../../app/api/auth.py#L15)
