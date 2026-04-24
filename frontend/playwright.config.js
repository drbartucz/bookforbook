// @ts-check
import { defineConfig, devices } from '@playwright/test';

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173';

export default defineConfig({
  testDir: './e2e/specs',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  timeout: 30_000,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ...(process.env.CI ? [/** @type {['github']} */ (['github'])] : []),
  ],
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
    actionTimeout: 10_000,
    navigationTimeout: 20_000,
  },

  projects: [
    // ── Auth setup (runs first, saves storageState files) ──────────────────
    {
      name: 'setup',
      testMatch: /global-setup\.js/,
      teardown: 'teardown',
    },
    {
      name: 'teardown',
      testMatch: /global-teardown\.js/,
    },

    // ── CI-blocking critical suite ─────────────────────────────────────────
    {
      name: 'critical',
      testMatch: /critical\/.*\.spec\.js/,
      dependencies: ['setup'],
      use: {
        ...devices['Desktop Chrome'],
        baseURL: BASE_URL,
      },
    },

    // ── Staging smoke (non-blocking, separate base URL) ────────────────────
    {
      name: 'smoke',
      testMatch: /smoke\/.*\.spec\.js/,
      use: {
        ...devices['Desktop Chrome'],
        baseURL: process.env.STAGING_URL || BASE_URL,
        storageState: { cookies: [], origins: [] },
      },
    },
  ],
});
