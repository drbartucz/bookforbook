/**
 * critical/13-auth-extended.spec.js
 *
 * Extended authentication flows:
 *   - Forgot password page: form renders, submit shows success, validation
 *   - Register: switching to Library reveals institution fields
 *   - Register: institution name required validation
 *   - Register: password mismatch error
 *   - Register: short username error
 *   - 404 page renders for unknown routes
 */
import { test, expect } from '../../fixtures/index.js';

test.describe('Auth — Extended', () => {
  // ── Forgot Password ──────────────────────────────────────────────────────

  test('forgot-password page loads and form renders', async ({ guestPage: page }) => {
    await page.goto('/forgot-password');
    await expect(page.getByRole('heading', { name: /reset your password/i })).toBeVisible();
    await expect(page.getByLabel(/email address/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /send reset link/i })).toBeVisible();
  });

  test('forgot-password: missing email shows validation error', async ({ guestPage: page }) => {
    await page.goto('/forgot-password');

    await page.getByRole('button', { name: /send reset link/i }).click();

    await expect(page.getByText(/email is required/i)).toBeVisible({ timeout: 5_000 });
  });

  test('forgot-password: invalid email format shows validation error', async ({ guestPage: page }) => {
    await page.goto('/forgot-password');

    await page.getByLabel(/email address/i).fill('not-an-email');
    await page.getByRole('button', { name: /send reset link/i }).click();

    await expect(page.getByText(/valid email/i)).toBeVisible({ timeout: 5_000 });
  });

  test('forgot-password: valid email submit shows success message', async ({ guestPage: page }) => {
    await page.goto('/forgot-password');

    await page.getByLabel(/email address/i).fill('any@example.com');
    await page.getByRole('button', { name: /send reset link/i }).click();

    // API always returns success to avoid user enumeration
    await expect(
      page.getByText(/if an account exists for that email|reset link has been sent|check your inbox/i).first()
    ).toBeVisible({ timeout: 10_000 });
    // Back to sign in link appears
    await expect(page.getByRole('link', { name: /back to sign in/i })).toBeVisible();
  });

  test('login page has Forgot password link', async ({ guestPage: page }) => {
    await page.goto('/login');
    await expect(page.getByRole('link', { name: /forgot password/i })).toBeVisible();
    await page.getByRole('link', { name: /forgot password/i }).click();
    await expect(page).toHaveURL(/\/forgot-password/, { timeout: 8_000 });
  });

  // ── Register — institution fields ────────────────────────────────────────

  test('register: default is Individual type with no institution fields', async ({ guestPage: page }) => {
    await page.goto('/register');

    // Institution name and URL fields should not be visible for individual
    await expect(page.getByLabel(/institution name/i)).not.toBeVisible();
    await expect(page.getByLabel(/institution website/i)).not.toBeVisible();
  });

  test('register: selecting Library reveals institution fields', async ({ guestPage: page }) => {
    await page.goto('/register');

    await page.getByRole('radio', { name: /^library/i }).click();

    await expect(page.getByLabel(/institution name/i)).toBeVisible({ timeout: 5_000 });
    await expect(page.getByLabel(/institution website/i)).toBeVisible();
  });

  test('register: selecting Bookstore reveals institution fields', async ({ guestPage: page }) => {
    await page.goto('/register');

    await page.getByRole('radio', { name: /^bookstore/i }).click();

    await expect(page.getByLabel(/institution name/i)).toBeVisible({ timeout: 5_000 });
  });

  test('register: institution name required when Library selected', async ({ guestPage: page }) => {
    await page.goto('/register');

    await page.getByRole('radio', { name: /^library/i }).click();
    await page.getByLabel(/email address/i).fill('lib@example.com');
    await page.getByLabel(/^username/i).fill('testlibrary');
    await page.getByLabel(/^password$/i).fill('TestPass123!');
    await page.getByLabel(/confirm password/i).fill('TestPass123!');
    // Leave institution name blank
    await page.getByRole('button', { name: /create account/i }).click();

    await expect(page.getByText(/institution name is required/i)).toBeVisible({ timeout: 5_000 });
  });

  test('register: password mismatch shows error', async ({ guestPage: page }) => {
    await page.goto('/register');

    await page.getByLabel(/email address/i).fill('test@example.com');
    await page.getByLabel(/^username/i).fill('testuser99');
    await page.getByLabel(/^password$/i).fill('TestPass123!');
    await page.getByLabel(/confirm password/i).fill('DifferentPass456!');
    await page.getByRole('button', { name: /create account/i }).click();

    await expect(page.getByText(/passwords do not match/i)).toBeVisible({ timeout: 5_000 });
  });

  test('register: switching back to Individual hides institution fields', async ({ guestPage: page }) => {
    await page.goto('/register');

    await page.getByRole('radio', { name: /^library/i }).click();
    await expect(page.getByLabel(/institution name/i)).toBeVisible({ timeout: 5_000 });

    await page.getByRole('radio', { name: /^individual/i }).click();
    await expect(page.getByLabel(/institution name/i)).not.toBeVisible();
  });

  // ── 404 ──────────────────────────────────────────────────────────────────

  test('unknown route shows 404 page', async ({ guestPage: page }) => {
    await page.goto('/this-page-does-not-exist-e2e-test');
    await page.waitForLoadState('networkidle');

    // React Router renders NotFound component
    await expect(
      page.getByText(/404|not found|page.*not found|doesn.*exist/i).first()
    ).toBeVisible({ timeout: 8_000 });
  });

  test('404 page does not require authentication', async ({ guestPage: page }) => {
    await page.goto('/authenticated-only-route-that-does-not-exist');
    await page.waitForLoadState('networkidle');

    // Should NOT redirect to /login — this is genuinely a 404, not an auth guard
    // (protected routes redirect; unknown routes show 404)
    await expect(page).not.toHaveURL(/\/login/);
  });
});
