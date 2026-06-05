/**
 * frontend/src/utils/routeToPageKey.ts
 *
 * Purpose:
 *     Single-source map from Vue Router route names to Help Center pageKeys.
 *     Used by the help store to resolve "what page is the user on?" so the
 *     "This page" tab can show context-relevant content.
 *
 * Responsibilities:
 *     - One map: route.name (string) → pageKey (string)
 *     - Unknown route → 'dashboard' fallback (matches po.vin convention)
 *
 * Critical invariants:
 *     - pageKey values MUST match keys in frontend/src/constants/help-content.ts
 *       HELP_CONTENT.pages. Drift produces blank "This page" tabs.
 *
 * Related ADRs: ADR-009 (Vue port discipline — see CLAUDE.md Help Center note).
 */

// Keys MUST match the `name:` strings declared in frontend/src/router/index.ts
// — Vue Router's `route.name` is exactly that string at runtime. The router
// uses lowercase/kebab-case route names; a PascalCase mirror here would
// silently fall back to 'dashboard' on every non-Dashboard page (regression
// shipped 2026-06-05; users saw Dashboard help on every page).
export const ROUTE_TAG_MAP: Record<string, string> = {
  dashboard:        'dashboard',
  sessions:         'sessions',
  'session-detail': 'session-detail',
  upload:           'upload',
  editor:           'editor',
  sop:              'sop',
  'editor-audit':   'audit',
  viewer:           'viewer',
  processing:       'processing',
  improvements:     'improvements',
  settings:         'settings',
  audit:            'audit',
  'admin-help':     'help',
};

export function resolvePageKey(routeName: unknown): string {
  const name = typeof routeName === 'string' ? routeName : '';
  return ROUTE_TAG_MAP[name] || 'dashboard';
}
