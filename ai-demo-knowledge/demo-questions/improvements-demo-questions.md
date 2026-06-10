# Improvements — Demo Questions (code-verified)

> Module key: `improvements`. Every answer below is traceable to source. Paths are relative to this file (`ai-demo-knowledge/demo-questions/`), so repo-root files are reached with `../../`.

---

## User

### Q: How do I submit an improvement or bug report?
**Verified Answer:** Click "Suggest Improvement" on the Improvements page. A modal opens with Title, Surface, Priority, and Description. Title is required (the modal blocks submit with a "Title required" warning if empty). On submit it posts to the backend and the new item appears at the top of the list.
**Supporting Evidence:** Button at [ImprovementsView.vue:147](../../frontend/src/views/ImprovementsView.vue#L147); modal fields [SuggestImprovementModal.vue:36-74](../../frontend/src/components/overlays/SuggestImprovementModal.vue#L36); title validation [SuggestImprovementModal.vue:22-25](../../frontend/src/components/overlays/SuggestImprovementModal.vue#L22); POST + prepend [ImprovementsView.vue:98-106](../../frontend/src/views/ImprovementsView.vue#L98).
**Source Files:** `frontend/src/views/ImprovementsView.vue`, `frontend/src/components/overlays/SuggestImprovementModal.vue`
**API References:** `POST /v1/improvements`
**Database References:** `improvements`

### Q: What fields can I set when suggesting an improvement?
**Verified Answer:** Title (required), Description, Priority (Low/Medium/High/Critical), and Surface (mapped to the record's "area"). You cannot set status, risk, or version at creation — those default server-side.
**Supporting Evidence:** Modal fields [SuggestImprovementModal.vue:40-73](../../frontend/src/components/overlays/SuggestImprovementModal.vue#L40); the view maps `surface`→`area` [ImprovementsView.vue:98-103](../../frontend/src/views/ImprovementsView.vue#L98); create payload accepts only title/description/type/priority/area/is_security [app/api/improvements.py:43-49](../../app/api/improvements.py#L43).
**Source Files:** `frontend/src/components/overlays/SuggestImprovementModal.vue`, `frontend/src/views/ImprovementsView.vue`, `app/api/improvements.py`
**API References:** `POST /v1/improvements`
**Database References:** `improvements`

### Q: How do I find a specific improvement in the list?
**Verified Answer:** Use the status tabs (All / Pending / Under Review / Approved / In Progress / Rolled Out / Declined / Archived) or type into the search box, which filters the loaded list by title substring.
**Supporting Evidence:** Tabs [ImprovementsView.vue:46-55](../../frontend/src/views/ImprovementsView.vue#L46); title search filter [ImprovementsView.vue:57-62](../../frontend/src/views/ImprovementsView.vue#L57).
**Source Files:** `frontend/src/views/ImprovementsView.vue`
**API References:** `GET /v1/improvements`
**Database References:** `improvements`

### Q: How do I delete an improvement?
**Verified Answer:** Click "Del" on the row. A confirmation dialog appears; confirming removes it from the list. It is a soft delete — the row is marked `deleted_at` in the database, not physically removed.
**Supporting Evidence:** Del action [ImprovementsView.vue:208-212](../../frontend/src/views/ImprovementsView.vue#L208); confirm + remove [ImprovementsView.vue:114-130](../../frontend/src/views/ImprovementsView.vue#L114); soft delete SQL [app/api/improvements.py:181-183](../../app/api/improvements.py#L181).
**Source Files:** `frontend/src/views/ImprovementsView.vue`, `app/api/improvements.py`
**API References:** `DELETE /v1/improvements/{id}`
**Database References:** `improvements`

### Q: What is the "Action Plan Builder" I see when I select an improvement?
**Verified Answer:** A five-step detail view (Overview → Requirements → Implementation → Testing → Review). It shows generated requirements/implementation/testing documents and lets you copy them or export a combined `.md` file. Note: the "Save Changes" and "Regenerate" buttons are not yet wired to the backend — they show a "not yet wired" notice.
**Supporting Evidence:** Stepper [ImprovDetail.vue:25-31](../../frontend/src/components/improvements/ImprovDetail.vue#L25); copy/export [ImprovDetail.vue:108-129](../../frontend/src/components/improvements/ImprovDetail.vue#L108); save/regenerate stubs [ImprovDetail.vue:136-148](../../frontend/src/components/improvements/ImprovDetail.vue#L136).
**Source Files:** `frontend/src/components/improvements/ImprovDetail.vue`
**API References:** none (detail pane is local-state only)
**Database References:** none

---

## Executive

### Q: What does the Improvements module give the organization?
**Verified Answer:** A single shared backlog of product enhancement requests, bug reports, and operator suggestions for the Rounds app, each with submitter attribution, priority, risk, and status. The page describes itself as a "roadmap for product enhancements, bug fixes, and operator requests."
**Supporting Evidence:** Header copy [ImprovementsView.vue:138-140](../../frontend/src/views/ImprovementsView.vue#L138); single table, no tenancy [migrations/005_improvements.sql:3-24](../../migrations/005_improvements.sql#L3).
**Source Files:** `frontend/src/views/ImprovementsView.vue`, `migrations/005_improvements.sql`
**API References:** `GET /v1/improvements`
**Database References:** `improvements`

### Q: Can we see how many improvements are in each stage of the workflow?
**Verified Answer:** Yes, at the UI level — each status tab shows a count. These counts are computed in the browser from the loaded list, not from a server-side aggregate, and they cover only the currently loaded data.
**Supporting Evidence:** Per-status counts [ImprovementsView.vue:46-55](../../frontend/src/views/ImprovementsView.vue#L46); list loads all rows then counts client-side [ImprovementsView.vue:30-44](../../frontend/src/views/ImprovementsView.vue#L30).
**Source Files:** `frontend/src/views/ImprovementsView.vue`
**API References:** `GET /v1/improvements`
**Database References:** `improvements`

### Q: Is there a reporting or analytics dashboard for improvements?
**Verified Answer:** No dedicated reporting surface exists. The only metrics are the in-page status-tab counts and the header "{n} of {n}" line, both computed client-side. There is no aggregate query, export, or dashboard over the improvements table.
**Supporting Evidence:** Header count [ImprovementsView.vue:138-140](../../frontend/src/views/ImprovementsView.vue#L138); tab counts [ImprovementsView.vue:46-55](../../frontend/src/views/ImprovementsView.vue#L46). No reporting endpoint exists in [app/api/improvements.py](../../app/api/improvements.py).
**Source Files:** `frontend/src/views/ImprovementsView.vue`, `app/api/improvements.py`
**API References:** none beyond `GET /v1/improvements`
**Database References:** `improvements`

---

## Operations

### Q: How are improvement records ordered and how do we know who filed one?
**Verified Answer:** Records are returned newest-first (`submitted_at DESC`). The submitter is the email of the logged-in user who created it — it is set server-side from the JWT, so it cannot be spoofed by the client payload.
**Supporting Evidence:** Ordering [app/api/improvements.py:82](../../app/api/improvements.py#L82), [:88](../../app/api/improvements.py#L88); server-set submitter [app/api/improvements.py:103](../../app/api/improvements.py#L103).
**Source Files:** `app/api/improvements.py`
**API References:** `GET /v1/improvements`, `POST /v1/improvements`
**Database References:** `improvements`
**API References:** `GET /v1/improvements`

### Q: When an improvement is deleted, is the data gone?
**Verified Answer:** No. Delete is a soft delete — it stamps `deleted_at = now()` and the row stays in the table; all reads filter `deleted_at IS NULL`. There is no hard-delete endpoint for improvements.
**Supporting Evidence:** Soft delete [app/api/improvements.py:181-183](../../app/api/improvements.py#L181); read filters [app/api/improvements.py:81](../../app/api/improvements.py#L81), [:117](../../app/api/improvements.py#L117).
**Source Files:** `app/api/improvements.py`
**API References:** `DELETE /v1/improvements/{id}`
**Database References:** `improvements`

### Q: We changed an improvement's status in the detail pane but it didn't stick — why?
**Verified Answer:** The detail pane's admin controls and "Save Changes" button are not wired to the backend yet; the save handler emits a "not yet wired" notice instead of calling the API. The backend `PATCH /v1/improvements/{id}` endpoint exists, but no UI component currently invokes it. To change status today you would call the PATCH endpoint directly.
**Supporting Evidence:** `save()` stub [ImprovDetail.vue:143-148](../../frontend/src/components/improvements/ImprovDetail.vue#L143); PATCH endpoint exists [app/api/improvements.py:163-176](../../app/api/improvements.py#L163); API client `admin` not called by any view ([api.ts:680](../../frontend/src/services/api.ts#L680)).
**Source Files:** `frontend/src/components/improvements/ImprovDetail.vue`, `app/api/improvements.py`, `frontend/src/services/api.ts`
**API References:** `PATCH /v1/improvements/{id}`
**Database References:** `improvements`

### Q: The "Under Review", "In Progress", and "Rolled Out" tabs show zero even though records exist — is that a bug?
**Verified Answer:** Yes, it's a known data mismatch. The database stores those statuses with underscores (`under_review`, `in_progress`, `rolled_out`) while the frontend tabs filter on hyphenated ids (`under-review`, `in-progress`, `rolled-out`). Because no code normalizes between the two forms, those three tabs cannot match real rows.
**Supporting Evidence:** DB status enum (underscored) [migrations/005_improvements.sql:8](../../migrations/005_improvements.sql#L8); frontend tab ids (hyphenated) [ImprovementsView.vue:49-54](../../frontend/src/views/ImprovementsView.vue#L49).
**Source Files:** `migrations/005_improvements.sql`, `frontend/src/views/ImprovementsView.vue`
**API References:** `GET /v1/improvements`
**Database References:** `improvements`

---

## Finance

### Q: Are there any per-improvement billing, cost, or invoice fields?
**Verified Answer:** No. The improvements table has no cost, billing, invoice, currency, or financial columns. Its fields are limited to title, description, type, status, priority, risk, area, target_version, is_security, submitter, timestamps, and four markdown wizard bodies.
**Supporting Evidence:** Full column list [migrations/005_improvements.sql:3-24](../../migrations/005_improvements.sql#L3).
**Source Files:** `migrations/005_improvements.sql`
**API References:** none
**Database References:** `improvements`

---

## Compliance

### Q: What audit trail exists for improvements?
**Verified Answer:** Creating, saving a wizard step, and deleting an improvement each write an append-only row to the `audit_events` table with the actor's email and a summary. The kinds are `improvement.suggest` (with the full create payload stored as JSON), `improvement.wizard`, and `improvement.delete`.
**Supporting Evidence:** suggest audit [app/api/improvements.py:105-109](../../app/api/improvements.py#L105); wizard audit [app/api/improvements.py:155-158](../../app/api/improvements.py#L155); delete audit [app/api/improvements.py:184-186](../../app/api/improvements.py#L184); table [migrations/004_audit.sql:3-11](../../migrations/004_audit.sql#L3).
**Source Files:** `app/api/improvements.py`, `migrations/004_audit.sql`
**API References:** `POST /v1/improvements`, `PUT /v1/improvements/{id}/wizard/{step}`, `DELETE /v1/improvements/{id}`
**Database References:** `improvements`, `audit_events`

### Q: Are status/risk/version changes audited?
**Verified Answer:** No. The `PATCH /v1/improvements/{id}` endpoint that changes status, risk, target_version, and admin_notes writes no audit_events row. This is a verified audit gap — admin field changes leave no trace in the audit log.
**Supporting Evidence:** `admin_patch` has no audit insert [app/api/improvements.py:163-176](../../app/api/improvements.py#L163) (contrast with the suggest/wizard/delete handlers which do).
**Source Files:** `app/api/improvements.py`
**API References:** `PATCH /v1/improvements/{id}`
**Database References:** `improvements`, `audit_events`

### Q: Is the audit log immutable / append-only?
**Verified Answer:** The `audit_events` table is described as the global append-only event log; the Improvements module only ever INSERTs into it (never UPDATE/DELETE). Records include actor_email, kind, summary, a JSONB details blob, and occurred_at.
**Supporting Evidence:** Table comment + schema [migrations/004_audit.sql:1-11](../../migrations/004_audit.sql#L1); INSERT-only usage [app/api/improvements.py:105](../../app/api/improvements.py#L105), [:156](../../app/api/improvements.py#L156), [:185](../../app/api/improvements.py#L185).
**Source Files:** `migrations/004_audit.sql`, `app/api/improvements.py`
**API References:** n/a
**Database References:** `audit_events`

---

## Administrator

### Q: Who can access and modify improvements — is there an admin-only restriction?
**Verified Answer:** Any authenticated user (anyone with a valid JWT) can list, create, view, patch, and delete any improvement. There is no admin gate on this module — `app/api/improvements.py` does not import or call `require_admin`/`is_admin`, and the route has no `adminOnly` client guard. The endpoint named `admin_patch` is callable by any logged-in user; "admin" there is descriptive, not enforced.
**Supporting Evidence:** Only `CurrentUser` dep on every route [app/api/improvements.py:77](../../app/api/improvements.py#L77), [:94](../../app/api/improvements.py#L94), [:115](../../app/api/improvements.py#L115), [:145](../../app/api/improvements.py#L145), [:164](../../app/api/improvements.py#L164), [:180](../../app/api/improvements.py#L180); no roles import [app/api/improvements.py:14-15](../../app/api/improvements.py#L14); route has no adminOnly meta [router/index.ts:39](../../frontend/src/router/index.ts#L39).
**Source Files:** `app/api/improvements.py`, `frontend/src/router/index.ts`
**API References:** all `/v1/improvements*`
**Database References:** `improvements`
**Permission Logic Used:** JWT presence only (`CurrentUser`)

### Q: How is the admin-gate handled for improvements vs other modules?
**Verified Answer:** Other modules (help, settings, email templates/debug, sessions, locks) do enforce an admin gate via `require_admin`/`is_admin` against the hardcoded `LEGACY_ADMIN_EMAIL` (`johndean@vin.com`). Improvements intentionally does not — it has no role check at all. Role tiers from `auth_users.role` are not active anywhere, since `get_current_user` never loads the role into the User object.
**Supporting Evidence:** roles helper + legacy email [app/security/roles.py:54](../../app/security/roles.py#L54), [:62-92](../../app/security/roles.py#L62); `get_current_user` returns email-only User [app/auth.py:172-205](../../app/auth.py#L172); improvements has no roles import [app/api/improvements.py:14](../../app/api/improvements.py#L14).
**Source Files:** `app/security/roles.py`, `app/auth.py`, `app/api/improvements.py`
**API References:** all `/v1/improvements*`
**Database References:** `auth_users` (role column not read)
**Permission Logic Used:** JWT presence only for Improvements; `LEGACY_ADMIN_EMAIL` gate elsewhere

### Q: What administrative endpoints exist for managing an improvement's lifecycle?
**Verified Answer:** `PATCH /v1/improvements/{id}` updates status / risk / target_version / admin_notes (dynamic update of supplied non-null fields; 400 if none supplied). `PUT /v1/improvements/{id}/wizard/{step}` saves the markdown body of one of the four wizard steps (requirements / implementation / testing / review; 400 on an unknown step). Both exist in the API client but are not yet called from the UI.
**Supporting Evidence:** PATCH [app/api/improvements.py:163-176](../../app/api/improvements.py#L163); wizard PUT + step whitelist [app/api/improvements.py:136-160](../../app/api/improvements.py#L136); client methods [api.ts:678-681](../../frontend/src/services/api.ts#L678).
**Source Files:** `app/api/improvements.py`, `frontend/src/services/api.ts`
**API References:** `PATCH /v1/improvements/{id}`, `PUT /v1/improvements/{id}/wizard/{step}`
**Database References:** `improvements`

---

## Power User

### Q: Can I server-side filter the list to one status via the API?
**Verified Answer:** Yes — `GET /v1/improvements?status_filter=<status>` filters to that status (passing `all` or omitting it returns everything). Note the in-app UI does not use this param; it always fetches the full list and filters client-side. To filter server-side you'd call the endpoint directly with a status value matching the stored (underscored) form.
**Supporting Evidence:** Backend param + branch [app/api/improvements.py:77-89](../../app/api/improvements.py#L77); UI calls `list()` with no arg [ImprovementsView.vue:34](../../frontend/src/views/ImprovementsView.vue#L34); client method signature [api.ts:672-673](../../frontend/src/services/api.ts#L672).
**Source Files:** `app/api/improvements.py`, `frontend/src/views/ImprovementsView.vue`, `frontend/src/services/api.ts`
**API References:** `GET /v1/improvements?status_filter=`
**Database References:** `improvements`

### Q: Are there input validation limits I should know about when scripting against the API?
**Verified Answer:** Title must be 3–512 characters. Wizard step must be one of requirements/implementation/testing/review (else 400). PATCH with no fields returns 400. There is no enum validation on status/priority/risk/type — those columns are plain TEXT with no CHECK constraint, so arbitrary strings will be stored.
**Supporting Evidence:** title bounds [app/api/improvements.py:44](../../app/api/improvements.py#L44); step whitelist [app/api/improvements.py:136-148](../../app/api/improvements.py#L136); empty-patch 400 [app/api/improvements.py:166-167](../../app/api/improvements.py#L166); TEXT columns no CHECK [migrations/005_improvements.sql:7-11](../../migrations/005_improvements.sql#L7).
**Source Files:** `app/api/improvements.py`, `migrations/005_improvements.sql`
**API References:** `POST/PUT/PATCH /v1/improvements*`
**Database References:** `improvements`

### Q: Does the detail pane actually load the stored requirements/implementation/testing markdown?
**Verified Answer:** No. The detail pane generates those documents client-side from the item's fields (title, area, risk, priority, description) — it never calls `GET /v1/improvements/{id}`, and the stored `requirements_md`/`implementation_md`/`testing_md`/`review_md` columns are not read by the UI. The backend GET that returns them exists but is unused by the view.
**Supporting Evidence:** client-side doc generation [ImprovDetail.vue:43-104](../../frontend/src/components/improvements/ImprovDetail.vue#L43); view adapts summary, never calls `get()` and hardcodes a placeholder description [ImprovementsView.vue:66-83](../../frontend/src/views/ImprovementsView.vue#L66); backend GET returns the md columns [app/api/improvements.py:114-133](../../app/api/improvements.py#L114).
**Source Files:** `frontend/src/components/improvements/ImprovDetail.vue`, `frontend/src/views/ImprovementsView.vue`, `app/api/improvements.py`
**API References:** `GET /v1/improvements/{id}` (exists, not invoked by UI)
**Database References:** `improvements`

### Q: Is the "AI Model" dropdown in the detail pane connected to anything?
**Verified Answer:** No. It is a local component ref only; the selection is never sent to any backend, and the "Regenerate" button explicitly toasts that AI prompt regeneration is "not yet wired." There is no AI integration tied to the Improvements module.
**Supporting Evidence:** local `model` ref [ImprovDetail.vue:15](../../frontend/src/components/improvements/ImprovDetail.vue#L15); dropdown markup [ImprovDetail.vue:186-195](../../frontend/src/components/improvements/ImprovDetail.vue#L186); regenerate stub [ImprovDetail.vue:136-141](../../frontend/src/components/improvements/ImprovDetail.vue#L136).
**Source Files:** `frontend/src/components/improvements/ImprovDetail.vue`
**API References:** none
**Database References:** none

---

## Source Verification
- **Files Used:** `app/api/improvements.py`, `migrations/005_improvements.sql`, `migrations/004_audit.sql`, `app/security/roles.py`, `app/auth.py`, `frontend/src/views/ImprovementsView.vue`, `frontend/src/components/improvements/ImprovDetail.vue`, `frontend/src/components/overlays/SuggestImprovementModal.vue`, `frontend/src/services/api.ts`, `frontend/src/router/index.ts`
- **Components Used:** `ImprovementsView.vue`, `ImprovDetail.vue`, `SuggestImprovementModal.vue`
- **APIs Used:** `GET/POST /v1/improvements`, `GET/PUT/PATCH/DELETE /v1/improvements/{id}[/wizard/{step}]`
- **Database Tables Used:** `improvements`, `audit_events` (and `auth_users` noted as role-not-read)
- **Permission Logic Used:** JWT presence only (`CurrentUser`) for Improvements; `LEGACY_ADMIN_EMAIL` gate exists in other modules but not here
- **Confidence Score:** High — every Q/A maps to a concrete file:line; "not wired" and status-mismatch claims are verified code facts.
- **Evidence Links:** [app/api/improvements.py:103](../../app/api/improvements.py#L103), [app/api/improvements.py:163](../../app/api/improvements.py#L163), [migrations/005_improvements.sql:8](../../migrations/005_improvements.sql#L8), [ImprovementsView.vue:49](../../frontend/src/views/ImprovementsView.vue#L49), [ImprovDetail.vue:143](../../frontend/src/components/improvements/ImprovDetail.vue#L143)
