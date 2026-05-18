/**
 * Visual snapshot suite — golden regression baselines for every route + state.
 *
 * First run produces the baseline PNGs under __screenshots__/. Subsequent runs
 * diff against the baseline at the tolerances configured in playwright.config.ts
 * (0.005 maxDiffPixelRatio = 0.5% of pixels can differ before the test fails).
 *
 * Run `npm run test:visual:update` to refresh the baseline after intentional
 * UI changes. Run `npm run test:visual` to verify against the baseline in CI.
 */
import { test, expect, type Page } from '@playwright/test';
import { bypassAuth, freezeAnimations } from './helpers';

async function ready(page: Page, hash: string, wait: string): Promise<void> {
  await page.goto(`/${hash}`);
  await page.locator(wait).first().waitFor({ state: 'visible', timeout: 10_000 });
  await freezeAnimations(page);
  // Settle one extra frame so layout + fonts paint
  await page.waitForTimeout(150);
}

test.describe('visual: routes', () => {
  test('dashboard', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/dashboard', '.page');
    await expect(page).toHaveScreenshot('dashboard.png', { fullPage: true });
  });

  test('sessions list', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/sessions', '.page');
    await expect(page).toHaveScreenshot('sessions.png', { fullPage: true });
  });

  test('session detail', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/s/se_001', '.page');
    await expect(page).toHaveScreenshot('session-detail.png', { fullPage: true });
  });

  test('upload', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/upload', '.upload-page');
    await expect(page).toHaveScreenshot('upload.png', { fullPage: true });
  });

  test('sop workflow', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/e/se_001/sop', '.page');
    await expect(page).toHaveScreenshot('sop.png', { fullPage: true });
  });

  test('editor audit (per-session)', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/e/se_001/audit', '.page');
    await expect(page).toHaveScreenshot('editor-audit.png', { fullPage: true });
  });

  test('viewer', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/v/se_004', '.preview-page');
    await expect(page).toHaveScreenshot('viewer.png', { fullPage: true });
  });

  test('processing', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/p/se_007', '.page');
    await expect(page).toHaveScreenshot('processing.png', { fullPage: true });
  });

  test('improvements', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/improvements', '.page');
    await expect(page).toHaveScreenshot('improvements.png', { fullPage: true });
  });

  test('standalone audit', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/audit', '.page');
    await expect(page).toHaveScreenshot('audit.png', { fullPage: true });
  });

  test('gcs qa', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/gcs', '.page');
    await expect(page).toHaveScreenshot('gcs.png', { fullPage: true });
  });
});

test.describe('visual: editor tabs', () => {
  test('editor — AI Transcript tab (default)', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/e/se_001', '.editor');
    await page.locator('.transcript').first().waitFor();
    await expect(page).toHaveScreenshot('editor-ai.png', { fullPage: true });
  });

  test('editor — STT Reference tab', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/e/se_001', '.editor');
    await page.locator('.editor__tab', { hasText: 'STT Reference' }).click();
    await page.locator('.stt-pane').first().waitFor();
    await expect(page).toHaveScreenshot('editor-stt.png', { fullPage: true });
  });

  test('editor — Discrepancies tab', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/e/se_001', '.editor');
    await page.locator('.editor__tab', { hasText: 'Discrepancies' }).click();
    await page.locator('.compare').first().waitFor();
    await expect(page).toHaveScreenshot('editor-disc.png', { fullPage: true });
  });

  test('editor — Audit tab', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/e/se_001', '.editor');
    await page.locator('.editor__tab', { hasText: 'Audit' }).click();
    await page.locator('.audit-tab').first().waitFor();
    await expect(page).toHaveScreenshot('editor-audit-tab.png', { fullPage: true });
  });
});

test.describe('visual: editor states', () => {
  test('editor — inline Edit mode open', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/e/se_001', '.editor');
    await page.locator('[data-test-id="seg-edit"]').first().click();
    await page.locator('.segment-editor__toolbar').first().waitFor();
    await expect(page).toHaveScreenshot('editor-inline-edit.png', { fullPage: true });
  });

  test('editor — inline Reassign tile grid open', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/e/se_001', '.editor');
    await page.locator('[data-test-id="seg-reassign"]').first().click();
    await page.locator('.segment-reassign').first().waitFor();
    await expect(page).toHaveScreenshot('editor-inline-reassign.png', { fullPage: true });
  });

  test('editor — inline Speaker picker open', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/e/se_001', '.editor');
    await page.locator('[data-test-id="seg-speaker"]').first().click();
    await page.locator('.segment-speakerpick').first().waitFor();
    await expect(page).toHaveScreenshot('editor-inline-speaker.png', { fullPage: true });
  });

  test('editor — Download menu open', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/e/se_001', '.editor');
    await page.locator('[data-test-id="editor-download"]').click();
    await page.locator('.dl-menu').waitFor();
    await expect(page).toHaveScreenshot('editor-download-menu.png', { fullPage: true });
  });

  test('editor — slide rail filter banner', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/e/se_001', '.editor');
    await page.locator('.sliderail__toggle button', { hasText: 'Filter' }).click();
    await page.locator('.slide-card').nth(5).click();
    await page.locator('.transcript__filter-banner').waitFor();
    await expect(page).toHaveScreenshot('editor-filter-banner.png', { fullPage: true });
  });

  test('editor — right-rail Polls tab', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/e/se_001', '.editor');
    await page.locator('.rightrail__tab', { hasText: 'Polls' }).click();
    await page.locator('.poll-card').first().waitFor();
    await expect(page).toHaveScreenshot('editor-polls-rail.png', { fullPage: true });
  });

  test('editor — right-rail Admin tab', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/e/se_001', '.editor');
    await page.locator('.rightrail__tab', { hasText: 'Admin' }).click();
    await page.locator('.admin-segment-list').waitFor();
    await expect(page).toHaveScreenshot('editor-admin-rail.png', { fullPage: true });
  });
});

test.describe('visual: settings sections', () => {
  const sections = [
    'general', 'team', 'types', 'ai-models', 'upload', 'discrepancy',
    'export', 'prompts', 'manifest', 'email', 'diagnostics', 'deleted',
  ];
  for (const id of sections) {
    test(`settings/${id}`, async ({ page }) => {
      await bypassAuth(page);
      await ready(page, `#/settings/${id}`, '.settings__content');
      await expect(page).toHaveScreenshot(`settings-${id}.png`, { fullPage: true });
    });
  }
});

test.describe('visual: settings drill-ins', () => {
  test('settings — Email Builder', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/settings/email', '.settings__content');
    await page.locator('button.btn--tertiary', { hasText: 'Open builder' }).click();
    await page.locator('.set-emailbuilder').waitFor();
    await expect(page).toHaveScreenshot('settings-email-builder.png', { fullPage: true });
  });

  test('settings — GCS Debug', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/settings/diagnostics', '.settings__content');
    await page.locator('button.btn--tertiary', { hasText: 'Open GCS QA' }).click();
    await page.locator('.audit-ledger').waitFor();
    await expect(page).toHaveScreenshot('settings-gcs-debug.png', { fullPage: true });
  });

  test('settings — Email Debug', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/settings/diagnostics', '.settings__content');
    await page.locator('button.btn--tertiary', { hasText: 'Open test email page' }).click();
    await page.locator('.set-smtp-row').first().waitFor();
    await expect(page).toHaveScreenshot('settings-email-debug.png', { fullPage: true });
  });

  test('settings — Prompt Templates Catalog', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/settings/prompts', '.settings__content');
    await page.locator('.set-tpl-card').first().waitFor();
    await expect(page).toHaveScreenshot('settings-prompts-catalog.png', { fullPage: true });
  });

  test('settings — Prompt Templates New form', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/settings/prompts', '.settings__content');
    await page.locator('button.sugg-modal__submit', { hasText: '+ New Template' }).first().click();
    await page.locator('h3', { hasText: 'New Template' }).waitFor();
    await expect(page).toHaveScreenshot('settings-prompts-new.png', { fullPage: true });
  });
});

test.describe('visual: overlays', () => {
  test('command palette open', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/dashboard', '.page');
    await page.keyboard.press('ControlOrMeta+k');
    await page.locator('.command-palette').waitFor();
    await expect(page).toHaveScreenshot('overlay-cmdk.png', { fullPage: true });
  });

  test('tweaks panel open', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/dashboard', '.page');
    await page.keyboard.press('ControlOrMeta+.');
    await page.locator('.twk-panel').waitFor();
    await expect(page).toHaveScreenshot('overlay-tweaks.png', { fullPage: true });
  });

  test('find & replace modal', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/e/se_001', '.editor');
    await page.locator('[data-test-id="editor-find-replace"]').click();
    await page.locator('.scrim[data-test-id="modal-host"]').waitFor();
    await expect(page).toHaveScreenshot('overlay-find-replace.png', { fullPage: true });
  });

  test('suggest improvement modal', async ({ page }) => {
    await bypassAuth(page);
    await ready(page, '#/improvements', '.page');
    await page.locator('[data-test-id="improv-suggest"]').click();
    await page.locator('.scrim[data-test-id="modal-host"]').waitFor();
    await expect(page).toHaveScreenshot('overlay-suggest-improvement.png', { fullPage: true });
  });
});
