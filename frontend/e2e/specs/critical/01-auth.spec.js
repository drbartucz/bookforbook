/**
 * critical/01-auth.spec.js
 *
 * Auth journeys:
 *   - Login (valid, invalid)
 *   - Protected route guard (unauthenticated redirect)
 *   - Guest route guard (authenticated redirect)
 *   - Logout
 *   - Registration form (success flow)
 */
import { test, expect } from '../../fixtures/index.js';
import { ALICE, CAROL } from '../../constants.js';
import { waitForNavigation } from '../../helpers/wait.js';

test.describe('Authentication', () => {
  // ── Login ──────────────────────────────────────────────────────────────────

  test('valid credentials redirect to dashboard', async ({ guestPage: page }) => {
    await page.goto('/login');
    await page.getByLabel('Email address').fill(ALICE.email);
    await page.getByLabel('Password').fill(ALICE.password);
    await page.getByRole('button', { name: /sign in/i }).click();

    await waitForNavigation(page, '**/dashboard');
    await expect(page.getByRole('heading', { name: /welcome back/i })).toBeVisible();
  });

  test('invalid credentials show error message', async ({ guestPage: page }) => {
    await page.goto('/login');
    await page.getByLabel('Email address').fill(ALICE.email);
    await page.getByLabel('Password').fill('wrongpassword');
    await page.getByRole('button', { name: /sign in/i }).click();

    await expect(page.locator('.alert-error')).toBeVisible();
    // Must stay on login page
    await expect(page).toHaveURL(/\/login/);
  });

  test('empty form shows validation errors without API call', async ({ guestPage: page }) => {
    await page.goto('/login');
    await page.getByRole('button', { name: /sign in/i }).click();

    // Inline validation messages appear immediately
    await expect(page.getByText(/email is required/i)).toBeVisible();
    await expect(page.getByText(/password is required/i)).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  // ── Protected route guard ──────────────────────────────────────────────────

  test('unauthenticated user redirected from /dashboard to /login', async ({
    guestPage: page,
  }) => {
    await page.goto('/dashboard');
    await waitForNavigation(page, '**/login');
    await expect(page).toHaveURL(/\/login/);
  });

  test('unauthenticated user redirected from /my-books to /login', async ({
    guestPage: page,
  }) => {
    await page.goto('/my-books');
    await waitForNavigation(page, '**/login');
    await expect(page).toHaveURL(/\/login/);
  });

  test('unauthenticated user redirected from /trades to /login', async ({
    guestPage: page,
  }) => {
    await page.goto('/trades');
    await waitForNavigation(page, '**/login');
    await expect(page).toHaveURL(/\/login/);
  });

  // ── Guest route guard ──────────────────────────────────────────────────────

  test('authenticated user redirected from /login to /dashboard', async ({
    alicePage: page,
  }) => {
    await page.goto('/login');
    await waitForNavigation(page, '**/dashboard');
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('authenticated user redirected from /register to /dashboard', async ({
    alicePage: page,
  }) => {
    await page.goto('/register');
    await waitForNavigation(page, '**/dashboard');
    await expect(page).toHaveURL(/\/dashboard/);
  });

  // ── Logout ─────────────────────────────────────────────────────────────────

  test('logout clears session and redirects to home', async ({ alicePage: page }) => {
    await page.goto('/dashboard');

    // Open user menu (desktop navbar)
    await page.getByRole('button', { name: new RegExp(ALICE.username, 'i') })
      .or(page.getByRole('button', { name: /account|profile|menu/i }))
      .first()
      .click();

    await page.getByRole('button', { name: /log out|sign out/i }).click();

    // Should land on home or login
    await page.waitForURL(/\/(login|$)/, { timeout: 10_000 });

    // Navigating to a protected route should redirect to login
    await page.goto('/dashboard');
    await waitForNavigation(page, '**/login');
    await expect(page).toHaveURL(/\/login/);
  });

  // ── Registration ───────────────────────────────────────────────────────────

  test('registration form shows success state for new individual account', async ({
    guestPage: page,
  }) => {
    const uniqueEmail = `e2e_reg_${Date.now()}@example.com`;

    await page.goto('/register');
    // Select "individual" account type (default, but explicit)
    await page.getByRole('radio', { name: /individual/i }).check();
    await page.getByLabel('Email address').fill(uniqueEmail);
    await page.getByLabel('Username').fill(`user_${Date.now()}`);
    await page.getByLabel(/^Password$/i).fill('SecureTestPass1!');
    await page.getByLabel(/confirm password/i).fill('SecureTestPass1!');
    await page.getByRole('button', { name: /create account/i }).click();

    // Success state: "Check your email" message
    await expect(page.getByText(/check your email/i)).toBeVisible({ timeout: 10_000 });
  });

  test('registration shows error for duplicate email', async ({ guestPage: page }) => {
    await page.goto('/register');
    await page.getByLabel('Email address').fill(ALICE.email);
    await page.getByLabel('Username').fill(`dup_${Date.now()}`);
    await page.getByLabel(/^Password$/i).fill('SecureTestPass1!');
    await page.getByLabel(/confirm password/i).fill('SecureTestPass1!');
    await page.getByRole('button', { name: /create account/i }).click();

    await expect(page.locator('.alert-error')).toBeVisible({ timeout: 10_000 });
  });
});
