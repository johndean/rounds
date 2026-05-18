/**
 * Playwright config — single chromium project, fixed viewport, deterministic
 * env (no animations, frozen Date.now in some specs via patch). Vite dev
 * server is auto-started by webServer.
 */
import { defineConfig, devices } from '@playwright/test';

const PORT = 5173;

export default defineConfig({
  testDir: '.',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: `http://localhost:${PORT}`,
    viewport: { width: 1440, height: 900 },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    ignoreHTTPSErrors: true,
    actionTimeout: 10_000,
    navigationTimeout: 30_000,
  },
  expect: {
    timeout: 10_000,
    toHaveScreenshot: {
      // Per-pixel diff tolerance: 0.2 = 20% color delta per pixel before counted as different.
      // maxDiffPixelRatio: 0.5% of total pixels can differ before the test fails.
      // Combined this absorbs font subpixel + Vue scoped-style cascade noise without
      // missing real layout breaks.
      maxDiffPixelRatio: 0.005,
      threshold: 0.2,
      animations: 'disabled',
      caret: 'hide',
      scale: 'device',
    },
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'npm run dev -- --port 5173',
    url: `http://localhost:${PORT}`,
    timeout: 60_000,
    reuseExistingServer: !process.env.CI,
    cwd: '..',
    stdout: 'ignore',
    stderr: 'pipe',
  },
});
