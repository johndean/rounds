/**
 * Shared test helpers — auth bypass + console-error collector + readable
 * page-ready wait. Imported by every spec so we have one source of truth.
 */
import type { Page } from '@playwright/test';

export async function bypassAuth(page: Page): Promise<void> {
  await page.addInitScript(() => {
    localStorage.setItem('rounds_jwt_v1', 'test-bypass-token');
    localStorage.setItem('rounds_user_email_v1', 'johndean@vin.com');
  });
  await page.route('**/v1/auth/me', (route) => {
    void route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ email: 'johndean@vin.com' }),
    });
  });
  await page.route('**/v1/**', (route) => {
    const url = route.request().url();
    if (url.includes('/v1/auth/me')) return;
    const looksLikeList = /\/(sessions|segments|slides|discrepancies|corrections|improvements|sources|audit-events)(\?|$)/.test(url);
    void route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: looksLikeList ? '[]' : '{}',
    });
  });
}

/**
 * Collect console errors that genuinely indicate a bug. Suppresses backend-
 * network errors (we stub 200s but some 4xx may slip from non-/v1 paths) and
 * Vite HMR chatter.
 */
export function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() !== 'error') return;
    const text = msg.text();
    if (/Failed to load resource/i.test(text)) return;
    if (/the server responded with a status of 4\d\d/i.test(text)) return;
    if (/net::ERR_/i.test(text)) return;
    if (/HMR/i.test(text)) return;
    // The session WebSocket (wsConnectionPool) can't connect in the no-backend
    // preview env; that failure is environmental, not a render bug.
    if (/WebSocket connection to .* failed/i.test(text)) return;
    errors.push(text);
  });
  page.on('pageerror', (err) => {
    errors.push(`pageerror: ${err.message}`);
  });
  return errors;
}

/**
 * Disable transitions + caret blink so screenshot diffs are stable.
 */
export async function freezeAnimations(page: Page): Promise<void> {
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        transition-duration: 0s !important;
        transition-delay: 0s !important;
        caret-color: transparent !important;
      }
    `,
  });
}
