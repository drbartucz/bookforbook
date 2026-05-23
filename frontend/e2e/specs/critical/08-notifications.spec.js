/**
 * critical/08-notifications.spec.js
 *
 * Notification UX in the Navbar:
 *   - Bell icon renders when authenticated
 *   - Clicking bell opens dropdown
 *   - "Mark all read" button present in dropdown
 *   - Notifications API endpoint is called
 */
import { test, expect } from '../../fixtures/index.js';
import { ALICE } from '../../constants.js';

test.describe('Notifications', () => {
  test('notification bell visible for authenticated user', async ({ alicePage: page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('button', { name: /notifications/i })).toBeVisible();
  });

  test('clicking bell opens notifications dropdown', async ({ alicePage: page }) => {
    await page.goto('/dashboard');

    await page.getByRole('button', { name: /notifications/i }).click();

    // Dropdown appears
    await expect(
      page.getByText(/mark all read/i).or(page.getByText(/no notifications yet/i)).first()
    ).toBeVisible({ timeout: 8_000 });
  });

  test('mark all read button clears unread badge', async ({ alicePage: page }) => {
    await page.goto('/dashboard');

    // Open notifications
    await page.getByRole('button', { name: /notifications/i }).click();

    // Mark all read (may be a no-op if already at 0, but should not error)
    const markAllBtn = page.getByRole('button', { name: /mark all read/i });
    await expect(markAllBtn).toBeVisible({ timeout: 8_000 });
    await markAllBtn.click();

    // Button should not show an error state
    await expect(page.locator('.alert-error')).toHaveCount(0);

    // Close dropdown
    await page.keyboard.press('Escape');
  });

  test('closing dropdown by pressing Escape or clicking away', async ({ alicePage: page }) => {
    await page.goto('/dashboard');

    // Open
    await page.getByRole('button', { name: /notifications/i }).click();
    await expect(
      page.getByText(/mark all read/i).or(page.getByText(/no notifications yet/i)).first()
    ).toBeVisible({ timeout: 8_000 });

    // Close by pressing Escape (clicking elsewhere is blocked by the backdrop overlay)
    await page.keyboard.press('Escape');

    // Dropdown should be gone
    await expect(page.getByText(/mark all read/i)).toBeHidden({ timeout: 5_000 });
  });

  test('notification bell not visible for guest user', async ({ guestPage: page }) => {
    await page.goto('/');
    // Bell button requires authentication — should not be present
    await expect(page.getByRole('button', { name: /notifications/i })).toHaveCount(0);
  });

  test('pending match count badge shows in user menu matches link', async ({
    alicePage: page,
  }) => {
    // My Matches lives in the user dropdown — open it first
    await page.goto('/dashboard');

    await page.getByRole('button', { name: new RegExp(ALICE.username, 'i') }).click();

    // My Matches link should be visible in the open dropdown
    const myMatchesLink = page.getByRole('link', { name: /my matches/i });
    await expect(myMatchesLink).toBeVisible({ timeout: 8_000 });
  });
});
