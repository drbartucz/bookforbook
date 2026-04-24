/**
 * critical/04-matches.spec.js
 *
 * Matches page flows:
 *   - Pending tab shows seeded match
 *   - Alice (address verified) can accept a match
 *   - Carol (no address) gets an address-verification error
 *   - Decline a match
 */
import { test, expect } from '../../fixtures/index.js';

test.describe('Matches', () => {
  test('page loads with pending matches', async ({ alicePage: page }) => {
    await page.goto('/matches');
    await expect(page.getByRole('heading', { name: /matches/i })).toBeVisible();

    // Pending tab is active by default
    const pendingTab = page.getByRole('button', { name: /pending/i });
    await expect(pendingTab).toBeVisible();
  });

  test('alice sees seeded pending match (Orwell ↔ Gatsby)', async ({ alicePage: page }) => {
    await page.goto('/matches');

    // Wait for match cards to load
    await page.waitForLoadState('networkidle');

    // Should see the books from the seeded match
    const bookTitle = page.getByText(/nineteen eighty-four|great gatsby/i).first();
    await expect(bookTitle).toBeVisible({ timeout: 10_000 });

    // Accept and Decline buttons present
    await expect(page.getByRole('button', { name: /accept match/i }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: /decline/i }).first()).toBeVisible();
  });

  test('alice can accept a pending match', async ({ alicePage: page }) => {
    await page.goto('/matches');
    await page.waitForLoadState('networkidle');

    // Count pending matches
    const matchCards = page.locator('[class*="matchCard"]');
    await expect(matchCards.first()).toBeVisible({ timeout: 10_000 });

    // Accept the first pending match
    await page.getByRole('button', { name: /accept match/i }).first().click();

    // Card should move away from pending tab OR a success state appears
    // Give the mutation time to resolve and query to invalidate
    await expect(
      page.getByText(/accepted|no pending matches/i)
    ).toBeVisible({ timeout: 12_000 });
  });

  test('bob can decline a pending match', async ({ bobPage: page }) => {
    await page.goto('/matches');
    await page.waitForLoadState('networkidle');

    const declineBtn = page.getByRole('button', { name: /^decline$/i }).first();
    // Only proceed if bob still has a pending match; otherwise skip gracefully
    const count = await declineBtn.count();
    if (count === 0) {
      test.skip(true, 'No pending matches for bob — may have been accepted in prior test');
      return;
    }

    await declineBtn.click();

    await expect(
      page.getByText(/declined|no pending matches/i)
    ).toBeVisible({ timeout: 12_000 });
  });

  test('carol gets address-verification error when accepting a match', async ({
    carolPage: page,
  }) => {
    // Carol has no address — accepting should surface an error with a link to /account
    await page.goto('/matches');
    await page.waitForLoadState('networkidle');

    const acceptBtn = page.getByRole('button', { name: /accept match/i }).first();
    const count = await acceptBtn.count();
    if (count === 0) {
      // Carol may have no pending matches — this test is conditional
      test.skip(true, 'No pending matches for carol');
      return;
    }

    await acceptBtn.click();

    // Expect an error message referencing address verification
    await expect(
      page.locator('.alert-error').or(page.getByText(/verify.*address|address.*verify/i))
    ).toBeVisible({ timeout: 10_000 });
  });

  test('accepted tab shows accepted matches', async ({ alicePage: page }) => {
    await page.goto('/matches');
    await page.getByRole('button', { name: /^accepted$/i }).click();

    // Either shows match cards or "no matches found"
    await expect(
      page.locator('[class*="matchCard"]').or(page.getByText(/no matches found/i))
    ).toBeVisible({ timeout: 10_000 });
  });

  test('declined tab shows declined matches', async ({ alicePage: page }) => {
    await page.goto('/matches');
    await page.getByRole('button', { name: /^declined$/i }).click();

    await expect(
      page.locator('[class*="matchCard"]').or(page.getByText(/no matches found/i))
    ).toBeVisible({ timeout: 10_000 });
  });
});
