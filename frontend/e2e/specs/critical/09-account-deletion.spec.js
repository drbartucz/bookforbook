/**
 * critical/09-account-deletion.spec.js
 *
 * Account deletion journeys:
 *
 *   Danger Zone UI
 *   ─────────────
 *   - Danger Zone section is visible on /account
 *   - Empty password: client-side error shown, no navigation
 *   - Wrong password: backend 400 error shown, no navigation
 *
 *   Happy path (dave — address-verified, deleted during this suite)
 *   ──────────────────────────────────────────────────────────────
 *   - Correct password → account deactivated → redirect to /login
 *   - Pending match with carol is cancelled on deletion
 *   - Carol receives an account_deleted_impact notification
 *
 *   Post-deletion guard
 *   ───────────────────
 *   - Deactivated user cannot log back in via the login form
 *
 * NOTE: The "happy path" describe block uses test.describe.serial so tests
 * run in order.  Dave is deactivated during test 1; tests 2–3 verify the
 * downstream effects and the post-deletion login guard.
 *
 * Test isolation:
 *   - "Danger Zone UI" tests use carolPage — carol is NEVER deleted here.
 *   - "Happy path" tests use davePage then guestPage.
 *   - Dave exists solely for deletion testing and is re-created by
 *     `seed_e2e --reset` at the start of every E2E run.
 */
import { test, expect } from '../../fixtures/index.js';
import { CAROL, DAVE } from '../../constants.js';
import { apiLogin, apiListMatches, apiGetNotifications } from '../../helpers/api.js';

// ── Danger Zone UI ─────────────────────────────────────────────────────────

test.describe('Account deletion — Danger Zone UI', () => {
  /**
   * All three tests use carolPage.  Carol never gets deleted; these tests
   * exercise the form without triggering an actual account deletion.
   */

  test('Danger Zone section is visible on /account', async ({ carolPage: page }) => {
    await page.goto('/account');

    // Section heading
    await expect(page.getByText('Danger Zone', { exact: true })).toBeVisible();

    // Warning copy
    await expect(
      page.getByText(/delete your account and deactivate access/i)
    ).toBeVisible();

    // Confirm password field
    await expect(page.getByLabel(/confirm password/i)).toBeVisible();

    // Delete button
    await expect(page.getByRole('button', { name: /delete account/i })).toBeVisible();
  });

  test('empty password shows client-side error without navigating away', async ({
    carolPage: page,
  }) => {
    await page.goto('/account');

    // Leave password field blank and click Delete account
    await page.getByRole('button', { name: /delete account/i }).click();

    // Client-side validation fires immediately — no API round-trip
    await expect(page.locator('.alert-error')).toBeVisible();
    await expect(page.locator('.alert-error')).toContainText(
      /password is required to delete your account/i
    );

    // Must remain on the account settings page
    await expect(page).toHaveURL(/\/account/);
  });

  test('wrong password shows backend validation error without navigating away', async ({
    carolPage: page,
  }) => {
    await page.goto('/account');

    await page.getByLabel(/confirm password/i).fill('absolutely-wrong-password-123');
    await page.getByRole('button', { name: /delete account/i }).click();

    // Wait for the backend response error to surface in the DOM
    await expect(page.locator('.alert-error')).toBeVisible();

    // The error must mention password or be a generic "incorrect" message;
    // the exact wording comes from AccountDeletionSerializer on the backend.
    await expect(page.locator('.alert-error')).toContainText(/incorrect|password|wrong/i);

    // Still on /account, no redirect
    await expect(page).toHaveURL(/\/account/);
  });

  test('delete button is disabled while a request is in-flight', async ({
    carolPage: page,
  }) => {
    await page.goto('/account');

    // Intercept the DELETE request and stall it so we can assert the loading state
    await page.route('**/api/v1/users/me/', async (route) => {
      if (route.request().method() === 'DELETE') {
        // Never fulfill — causes the mutation to stay pending
        // The test assertion must run before Playwright's default timeout
        await new Promise((r) => setTimeout(r, 3_000));
        await route.abort();
        return;
      }
      await route.continue();
    });

    await page.getByLabel(/confirm password/i).fill(CAROL.password);

    const deleteBtn = page.getByRole('button', { name: /delete account|deleting account/i });
    await deleteBtn.click();

    // Button should be disabled while the mutation is pending
    await expect(deleteBtn).toBeDisabled();
    await expect(deleteBtn).toHaveText(/deleting account/i);

    // Clean up: unroute so subsequent tests are not affected
    await page.unroute('**/api/v1/users/me/');
  });
});

// ── Happy path + downstream effects ────────────────────────────────────────

test.describe.serial('Account deletion — happy path and downstream effects', () => {
  /**
   * Serial block: tests run in strict order.
   *
   *   Test 1 — UI happy path:
   *     Dave fills in the correct password → account deactivated → /login redirect.
   *     Within the same test we also check via the API that:
   *       • carol's pending match with dave is now CANCELLED.
   *       • carol has received an account_deleted_impact notification.
   *
   *   Test 2 — post-deletion login guard:
   *     A guest tries to log in as dave; the backend rejects the attempt because
   *     the account is deactivated (is_active=False).
   */

  test(
    'correct password deactivates account, redirects to /login, cancels pending match, and notifies counterparty',
    async ({ davePage: page }) => {
      // ── 1. Navigate to account settings ──────────────────────────────────
      await page.goto('/account');

      await expect(page.getByText('Danger Zone', { exact: true })).toBeVisible();

      // ── 2. Enter the correct password and submit ──────────────────────────
      await page.getByLabel(/confirm password/i).fill(DAVE.password);
      await page.getByRole('button', { name: /delete account/i }).click();

      // ── 3. Expect redirect to /login ──────────────────────────────────────
      await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });

      // The auth store should be cleared — navigating to a protected route
      // must redirect back to /login, not forward to the app.
      await page.goto('/dashboard');
      await expect(page).toHaveURL(/\/login/);

      // ── 4. Verify counterparty effects via the API ────────────────────────
      // Log in as carol using page.request (bypasses UI, no storageState needed)
      const { access: carolToken } = await apiLogin(
        page.request,
        CAROL.email,
        CAROL.password
      );

      // 4a. Dave's pending match with carol should now be CANCELLED.
      // The matches endpoint only returns PENDING/PROPOSED matches, so if the
      // dave↔carol match was correctly cancelled it will be absent from this list.
      const pendingMatches = await apiListMatches(page.request, carolToken);
      const pendingMatchWithDave = (Array.isArray(pendingMatches) ? pendingMatches : []).find(
        (m) =>
          m.legs?.some(
            (leg) =>
              leg.sender?.username === DAVE.username ||
              leg.receiver?.username === DAVE.username
          )
      );
      expect(
        pendingMatchWithDave,
        'Expected the dave↔carol pending match to be gone (cancelled) after dave\'s deletion'
      ).toBeUndefined();

      // 4b. Carol should have received an account_deleted_impact notification
      const notificationsData = await apiGetNotifications(page.request, carolToken);
      const deletionNotification = notificationsData.results?.find(
        (n) => n.notification_type === 'account_deleted_impact'
      );
      expect(
        deletionNotification,
        'Expected carol to have an account_deleted_impact notification'
      ).toBeTruthy();
    }
  );

  test('deactivated user cannot log back in via the login form', async ({
    guestPage: page,
  }) => {
    await page.goto('/login');

    await page.getByLabel(/email address/i).fill(DAVE.email);
    await page.getByLabel(/^password$/i).fill(DAVE.password);
    await page.getByRole('button', { name: /sign in/i }).click();

    // The backend returns 401 for inactive accounts; the frontend shows an error.
    await expect(page.locator('.alert-error')).toBeVisible({ timeout: 8_000 });

    // Must remain on /login — no redirect to dashboard.
    await expect(page).toHaveURL(/\/login/);
  });
});
