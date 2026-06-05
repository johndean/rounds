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

export const ROUTE_TAG_MAP: Record<string, string> = {
  Dashboard:      'dashboard',
  Sessions:       'sessions',
  SessionDetail:  'session-detail',
  Editor:         'editor',
  EditorSop:      'sop',
  EditorAudit:    'audit',
  Sop:            'sop',
  Upload:         'upload',
  Improvements:   'improvements',
  Settings:       'settings',
  Audit:          'audit',
  Viewer:         'viewer',
  Processing:     'processing',
  Help:           'help',
};

export function resolvePageKey(routeName: unknown): string {
  const name = typeof routeName === 'string' ? routeName : '';
  return ROUTE_TAG_MAP[name] || 'dashboard';
}
