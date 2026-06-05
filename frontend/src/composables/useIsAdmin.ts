/**
 * frontend/src/composables/useIsAdmin.ts
 *
 * Purpose:
 *     Client-side admin gate for Help Center admin UI visibility. Mirrors
 *     the backend BR-001 gate (LEGACY_ADMIN_EMAIL = "johndean@vin.com" in
 *     app/security/roles.py). The server is the authoritative check; this
 *     composable just gates UX rendering so non-admins do not see admin
 *     buttons / dialogs / routes.
 *
 *     Future migration: when auth_users.role is wired into the JWT
 *     payload, this composable will read user.role instead of comparing
 *     emails. Frontend-only change; the backend gate continues to be
 *     authoritative.
 *
 * Plan: docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md §8.3
 */
import { computed, type ComputedRef } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { LEGACY_ADMIN_EMAIL_CLIENT } from '@/constants/help-content';

export function useIsAdmin(): ComputedRef<boolean> {
  const auth = useAuthStore();
  return computed(
    () => !!auth.email && auth.email === LEGACY_ADMIN_EMAIL_CLIENT,
  );
}
