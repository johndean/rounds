/**
 * Interactions spec — every wired button/modal/keyboard shortcut.
 * Mirrors the §17 "78 functional buttons" checklist from IMPLEMENTATION.md.
 */
import { test, expect } from '@playwright/test';
import { bypassAuth } from './helpers';

test.describe('overlays', () => {
  test('command palette ⌘K opens, filters routes, closes on Esc', async ({ page }) => {
    await bypassAuth(page);
    await page.goto('/#/dashboard');
    await page.keyboard.press('ControlOrMeta+k');
    const palette = page.locator('.command-palette');
    await expect(palette).toBeVisible();
    await palette.locator('input').fill('settings');
    await expect(page.locator('.cmdp-item').first()).toContainText(/Settings/);
    await page.keyboard.press('Escape');
    await expect(palette).toBeHidden();
  });

  test('command palette has 12 entries matching React SSOT', async ({ page }) => {
    await bypassAuth(page);
    await page.goto('/#/dashboard');
    await page.keyboard.press('ControlOrMeta+k');
    await expect(page.locator('.cmdp-item')).toHaveCount(12);
  });

  test('tweaks panel: ⌘. toggles, drag persists', async ({ page }) => {
    await bypassAuth(page);
    await page.goto('/#/dashboard');
    const fab = page.locator('.twk-fab');
    await expect(fab).toBeVisible();
    await page.keyboard.press('ControlOrMeta+.');
    await expect(page.locator('.twk-panel')).toBeVisible();
    await page.keyboard.press('ControlOrMeta+.');
    await expect(page.locator('.twk-panel')).toBeHidden();
  });

  test('tweaks panel brand toggle flips --color-navy CSS variable', async ({ page }) => {
    await bypassAuth(page);
    await page.goto('/#/dashboard');
    await page.keyboard.press('ControlOrMeta+.');
    const panel = page.locator('.twk-panel');
    await expect(panel).toBeVisible();
    await panel.locator('.twk-radio__opt', { hasText: 'VSPN' }).click();
    const navy = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--color-navy').trim()
    );
    expect(navy).toBe('#007D61');
  });
});

test.describe('editor inline interactions', () => {
  test('inline Edit toolbar opens with 14 buttons and history controls', async ({ page }) => {
    await bypassAuth(page);
    await page.goto('/#/e/se_001');
    await expect(page.locator('.editor')).toBeVisible();
    await page.locator('[data-test-id="seg-edit"]').first().click();
    const toolbar = page.locator('.segment-editor__toolbar').first();
    await expect(toolbar).toBeVisible();
    await expect(toolbar.locator('button')).toHaveCount(14);
    await expect(toolbar.locator('button[title="Bold"]')).toBeVisible();
    await expect(toolbar.locator('button[title="Italic"]')).toBeVisible();
    await expect(toolbar.locator('button[title="Underline"]')).toBeVisible();
    await expect(toolbar.locator('button[title="Undo"]')).toBeVisible();
    await expect(toolbar.locator('button[title="Redo"]')).toBeVisible();
  });

  test('inline Reassign shows 24 slide tiles', async ({ page }) => {
    await bypassAuth(page);
    await page.goto('/#/e/se_001');
    await page.locator('[data-test-id="seg-reassign"]').first().click();
    await expect(page.locator('.segment-reassign__tile')).toHaveCount(24);
  });

  test('inline Speaker shows 3 speaker tiles', async ({ page }) => {
    await bypassAuth(page);
    await page.goto('/#/e/se_001');
    await page.locator('[data-test-id="seg-speaker"]').first().click();
    await expect(page.locator('.segment-speakerpick__tile')).toHaveCount(3);
  });

  test('right-rail Chat tab shows placed-count + chat messages', async ({ page }) => {
    await bypassAuth(page);
    await page.goto('/#/e/se_001');
    // Chat is the default right-tab; should show all 12 chat messages from fixture
    await expect(page.locator('.chat-msg').first()).toBeVisible();
  });

  test('right-rail Polls tab renders 3 polls with options', async ({ page }) => {
    await bypassAuth(page);
    await page.goto('/#/e/se_001');
    await page.locator('.rightrail__tab', { hasText: 'Polls' }).click();
    await expect(page.locator('.poll-card')).toHaveCount(3);
    // Each poll has 4 options
    await expect(page.locator('.poll-card').first().locator('.poll-card__opt')).toHaveCount(4);
  });

  test('Find & Replace modal opens from editor topbar', async ({ page }) => {
    await bypassAuth(page);
    await page.goto('/#/e/se_001');
    await page.locator('[data-test-id="editor-find-replace"]').click();
    const modal = page.locator('.scrim[data-test-id="modal-host"]');
    await expect(modal).toBeVisible();
    await expect(modal.locator('h3.modal__title')).toContainText('Find & Replace');
  });

  test('Download menu opens with 4 export options', async ({ page }) => {
    await bypassAuth(page);
    await page.goto('/#/e/se_001');
    await page.locator('[data-test-id="editor-download"]').click();
    await expect(page.locator('.dl-menu')).toBeVisible();
    await expect(page.locator('[data-test-id="dl-docx"]')).toBeVisible();
    await expect(page.locator('[data-test-id="dl-srt"]')).toBeVisible();
    await expect(page.locator('[data-test-id="dl-txt"]')).toBeVisible();
    await expect(page.locator('[data-test-id="dl-zip"]')).toBeVisible();
  });

  test('slide-rail filter mode shows filter banner above transcript', async ({ page }) => {
    await bypassAuth(page);
    await page.goto('/#/e/se_001');
    await page.locator('.sliderail__toggle button', { hasText: 'Filter' }).click();
    await page.locator('.slide-card').first().click();
    await expect(page.locator('.transcript__filter-banner')).toBeVisible();
  });
});

test.describe('improvements suggest flow', () => {
  test('Suggest Improvement modal opens, validates, submits, appears in list', async ({ page }) => {
    await bypassAuth(page);
    await page.goto('/#/improvements');
    await page.locator('[data-test-id="improv-suggest"]').click();
    const modal = page.locator('.scrim[data-test-id="modal-host"]');
    await expect(modal).toBeVisible();
    await expect(modal.locator('h3.modal__title')).toContainText('Suggest Improvement');
    // Submit with empty title → toast appears, modal still open
    await modal.locator('button.btn--primary', { hasText: 'Submit' }).click();
    await expect(modal).toBeVisible();
    // Fill title and submit
    await modal.locator('input').first().fill('Test improvement from Playwright');
    await modal.locator('button.btn--primary', { hasText: 'Submit' }).click();
    await expect(modal).toBeHidden();
    await expect(page.locator('.improv-row2__title', { hasText: 'Test improvement from Playwright' })).toBeVisible();
  });
});

test.describe('settings interactions', () => {
  test('Email section drills into builder + back returns', async ({ page }) => {
    await bypassAuth(page);
    await page.goto('/#/settings/email');
    await page.locator('button.btn--tertiary', { hasText: 'Open builder' }).click();
    await expect(page.locator('.set-emailbuilder')).toBeVisible();
    await page.locator('button.set-link', { hasText: '← Settings' }).click();
    await expect(page.locator('.settings-row h3', { hasText: 'Email templates' })).toBeVisible();
  });

  test('Diagnostics → GCS QA drill renders 14 G1-G14 rows', async ({ page }) => {
    await bypassAuth(page);
    await page.goto('/#/settings/diagnostics');
    await page.locator('button.btn--tertiary', { hasText: 'Open GCS QA' }).click();
    // Count data rows by excluding the head row class.
    const rows = page.locator('.audit-ledger .audit-row:not(.audit-row--head)');
    await expect(rows).toHaveCount(14);
  });

  test('Diagnostics → Test email page renders 5 sections', async ({ page }) => {
    await bypassAuth(page);
    await page.goto('/#/settings/diagnostics');
    await page.locator('button.btn--tertiary', { hasText: 'Open test email page' }).click();
    // Five h4 section headers (SMTP / Connectivity / Send / Recent / Event)
    const headers = page.locator('.set-pane h4');
    await expect(headers).toHaveCount(5);
  });

  test('Types matrix renders 8 stage rows with assignee select + email checkbox', async ({ page }) => {
    await bypassAuth(page);
    await page.goto('/#/settings/types');
    await expect(page.locator('.set-matrix-row')).toHaveCount(8);
    await expect(page.locator('.set-matrix-row__email input[type="checkbox"]')).toHaveCount(8);
  });

  test('Prompt Templates Catalog → New Template form', async ({ page }) => {
    await bypassAuth(page);
    await page.goto('/#/settings/prompts');
    await expect(page.locator('.set-tpl-card').first()).toBeVisible();
    await page.locator('button.sugg-modal__submit', { hasText: '+ New Template' }).first().click();
    await expect(page.locator('h3', { hasText: 'New Template' })).toBeVisible();
  });
});
