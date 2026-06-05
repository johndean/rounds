# Phase 1 — Rollback Report

**Generated**: 2026-06-04 against tip `6df4170` (post-F1.E)

Per-phase rollback procedure. Anchor point: tag `stakeholder-remediation-baseline-2026-06-04` on both `origin` and `production`.

## Universal rollback (full revert of all stakeholder remediation work)

```bash
cd /c/Users/JohnDean/rounds
git checkout stakeholder-remediation-baseline-2026-06-04
git push --force-with-lease origin main  # (with explicit user authorization only)
git push --force-with-lease production main  # (with explicit user authorization only)
```

**Warning**: `--force-with-lease` requires explicit user authorization per session convention C7. Force-push is a destructive action. The preferred mechanism is per-phase revert (below), not full force-reset.

## Per-phase rollback procedures

### Phase 2 — Help Center

**Strategy**: revert the 2-3 commits that comprise Phase 2. Component is greenfield with two integration touchpoints.

```bash
git revert <phase-2-commit-sha>
cd frontend && npx vue-tsc --noEmit && npm run build
git push origin main
# (with auth) git push production main
```

**Rollback time**: < 10 minutes. **Data loss risk**: zero (no DB writes).
**Feature flag rollback (faster)**: leave the code, set `VITE_HELP_ASK_AI_ENABLED=false` (already default) AND a global `VITE_HELP_ENABLED=false` kill switch. Topbar button hides; drawer host stays mounted but never renders.

### Phase 3 — Chat Count panel
**BLOCKED on stakeholder clarification.** No rollback procedure defined until premise confirmed.

### Phase 4 — Video ↔ Segment timestamp sync

**Strategy**: revert backend schema + API change first (correction-ledger `time_edit` kind, SegmentPatch fields), then frontend wiring.

```bash
# Frontend revert
git revert <phase-4-frontend-commit>

# Backend revert (after frontend is reverted)
git revert <phase-4-backend-commit>

# Migration revert (CAREFUL — only if no time_edit ledger rows have been written)
# Check first:
psql $DATABASE_URL -c "SELECT COUNT(*) FROM audit_events WHERE kind = 'sop.time_edit'"
# If zero rows, revert migration normally. If non-zero, leave migration in place
# and accept the unused enum value (no harm).
```

**Rollback time**: 15-30 minutes (including migration check).
**Data loss risk**: low — existing `start_ms`/`end_ms` data unchanged.

### Phase 5 — Segment formatting

**Strategy**: revert frontend + backend export changes. Snapshot tests in `tests/test_export_formats.py` should pass against the pre-Phase-5 baseline.

```bash
git revert <phase-5-commits>
pytest tests/test_export_formats.py  # confirm baseline behavior restored
cd frontend && npx vue-tsc --noEmit
```

**Rollback time**: < 15 minutes.
**Data loss risk**: zero — segment text data unchanged. (Existing `\n` characters in segments are preserved either way; only the rendering differs.)
**Caveat**: any exports generated DURING Phase 5 that were delivered to stakeholders cannot be retroactively reformatted — those stay as shipped.

### Phase 6 — Poll & Chat reordering

**Strategy**: 3-step revert. Frontend → backend endpoint → migration (only if zero non-NULL `order_index` rows).

```bash
# Frontend
git revert <phase-6-frontend-commit>

# Backend endpoint
git revert <phase-6-backend-endpoint-commit>

# Migration check
psql $DATABASE_URL -c "SELECT COUNT(*) FROM chat_messages WHERE order_index IS NOT NULL"
psql $DATABASE_URL -c "SELECT COUNT(*) FROM polls WHERE order_index IS NOT NULL"
# Zero rows in both → safe to revert migration (drop columns).
# Non-zero rows → leave migration; revert only the COALESCE in queries.
```

**Rollback time**: 20-40 minutes.
**Data loss risk**: if `order_index` was populated, reverting the migration drops user-customized order. Recommended: keep migration even if frontend is reverted; the COALESCE fallback to `sent_at_ms`/`opened_at_ms` makes the column harmless.

### Phase 7 — Workflow automation

**Quick-win revert** (just the resolver wire-up):

```bash
git revert <phase-7-quickwin-commit>
# Confirms F1.E falls back to inline f-strings — same behavior as 2026-06-04 deploy
```

**Rollback time**: < 5 minutes. **Data loss risk**: zero (additive change).

**Broader Phase 7 revert** (queue + ownership):

```bash
git revert <phase-7-queue-commit>
git revert <phase-7-sopview-assignees-commit>
git revert <phase-7-router-commit>
```

**Rollback time**: 15-30 minutes.
**Data loss risk**: zero (frontend display only; `sop_state.assignees` already populated, just stops being displayed).
**Feature flag rollback (faster)**: ship Phase 7 broader behind `QUEUE_ENABLED` env flag. Default OFF.

### Phase 8 — Open Builder permissions fix

**Strategy**: revert the 1-2 commits. Single helper extraction.

```bash
git revert <phase-8-commit>
pytest tests/test_admin_role.py  # confirm old email-literal behavior restored
```

**Rollback time**: < 10 minutes.
**Data loss risk**: zero (auth_users.role rows remain; just stop being consulted).
**Caveat**: any new admins promoted via Settings → Auth & logins during the Phase 8 deploy window will LOSE admin access on rollback. Stakeholder must accept this or hold off on promoting new admins until Phase 8 stability is confirmed.

### Phase 9 — Spellcheck research
**No rollback needed.** Research deliverable only, no code shipped.

### Phase 9.5 (future, if GO) — LanguageTool + Hunspell

```bash
# Disable feature flag first
railway variables set SPELLCHECK_LT_ENABLED=false
# Frontend will gracefully fall back to browser-native spellcheck

# Then revert code
git revert <phase-9.5-commits>

# Optionally stop the LanguageTool Docker service in Railway dashboard
```

**Rollback time**: < 5 minutes via flag; full code revert ~30 min.

## Phase 10 — Validation
**No rollback needed.** Validation produces evidence artifacts; rolling back individual phases reverts the validated state.

## Cross-cutting rollback principles

1. **Feature-flag every risky phase.** Faster rollback (env var flip + service restart) than git revert + deploy.
2. **Keep migrations forward-only.** If a phase adds a column, the rollback procedure should NOT drop the column unless guaranteed empty. The COALESCE pattern (Phase 6) makes nullable schema additions effectively reversible.
3. **Document the SHA in each commit message** so rollback procedure can be precise.
4. **Two-remote rollback**: both `origin` AND `production` must be reverted. Per session convention C7, the `production` push requires explicit user authorization at rollback time too.
5. **Health-check after rollback.** Hit `/v1/version`, hit `/health`, smoke the affected UI route.

## Rollback decision tree

```
Did the phase ship to production?
├─ NO  → just revert on origin, no production action
└─ YES → did any user data get created in the new schema?
          ├─ NO  → standard git revert + push both remotes
          └─ YES → leave migration in place; revert only application code;
                   accept that the schema is now "ahead" of the code (harmless if nullable)
```
