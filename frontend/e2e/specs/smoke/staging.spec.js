/**
 * smoke/staging.spec.js
 *
 * Non-destructive smoke tests that run against the live staging environment.
 * These are read-only: no mutations, no seed data required.
 *
 * Triggered via: npm run e2e:smoke
 * Requires env vars: STAGING_URL, STAGING_USER_EMAIL, STAGING_USER_PASSWORD
 */
import { test, expect } from '@playwright/test';

const STAGING_URL = process.env.STAGING_URL ?? 'https://bookforbook-staging.up.railway.app';

test.describe('Staging smoke tests', () => {
  test.use({ baseURL: STAGING_URL });

  // ── Public pages ──────────────────────────────────────────────────────────

  test('homepage loads', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/bookforbook/i);
    // Main nav / hero content visible
    await expect(page.locator('nav')).toBeVisible();
  });

  test('/institutions page loads', async ({ page }) => {
    await page.goto('/institutions');
    await expect(page.getByRole('heading', { name: /institution/i })).toBeVisible({
      timeout: 15_000,
    });
  });

  test('/login page renders form', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByLabel(/email address/i)).toBeVisible({ timeout: 10_000 });
    await expect(page.getByLabel(/password/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible();
  });

  test('/register page renders form', async ({ page }) => {
    await page.goto('/register');
    await expect(page.getByLabel(/email address/i)).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole('button', { name: /create account/i })).toBeVisible();
  });

  // ── Auth-gated redirect ───────────────────────────────────────────────────

  test('/dashboard redirects unauthenticated users to /login', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForURL(/\/(login)/, { timeout: 10_000 });
    await expect(page).toHaveURL(/\/login/);
  });

  // ── Authenticated smoke (optional) ────────────────────────────────────────

  test('staging user can log in to dashboard', async ({ page }) => {
    const email = process.env.STAGING_USER_EMAIL;
    const password = process.env.STAGING_USER_PASSWORD;

    if (!email || !password) {
      test.skip(true, 'STAGING_USER_EMAIL / STAGING_USER_PASSWORD not set');
      return;
    }

    await page.goto('/login');
    await page.getByLabel(/email address/i).fill(email);
    await page.getByLabel(/password/i).fill(password);
    await page.getByRole('button', { name: /sign in/i }).click();

    await page.waitForURL(/\/dashboard/, { timeout: 20_000 });
    await expect(page).toHaveURL(/\/dashboard/);
  });
});
