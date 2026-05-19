/**
 * critical/04-matches.spec.js
 *
 * Matches page flows:
 *   - Proposed tab shows seeded match
 *   - Alice (address verified) can accept a match
 *   - Carol (no address) gets an address-verification error
 *   - Decline a match
 */
import { test, expect } from '../../fixtures/index.js';

test.describe('Matches', () => {
  test('page loads with proposed matches', async ({ alicePage: page }) => {
    await page.goto('/matches');
    await expect(page.getByRole('heading', { name: /matches/i })).toBeVisible();

    // Proposed tab is active by default
    const proposedTab = page.getByRole('button', { name: /proposed/i });
    await expect(proposedTab).toBeVisible();
  });

  test('alice sees seeded proposed match (Orwell ↔ Gatsby)', async ({ alicePage: page }) => {
    await page.goto('/matches');

    // Wait for match cards to load

    // Should see the books from the seeded match
    const bookTitle = page.getByText(/nineteen eighty-four|great gatsby/i).first();
    await expect(bookTitle).toBeVisible({ timeout: 10_000 });

    // Accept and Decline buttons present
    await expect(page.getByRole('button', { name: /accept match/i }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: /decline/i }).first()).toBeVisible();
  });

  test('alice can accept a proposed match', async ({ alicePage: page }) => {
    await page.goto('/matches');

    // Count proposed matches
    const matchCards = page.locator('[class*="matchCard"]');
    await expect(matchCards.first()).toBeVisible({ timeout: 10_000 });

    // Accept the first proposed match
    await page.getByRole('button', { name: /accept match/i }).first().click();

    // Card should show "Waiting for partner…" (match stays in Proposed tab until both accept)
    // or the tab becomes empty if this was the only match
    await expect(
      page.getByText(/waiting for partner|no proposed matches/i)
    ).toBeVisible({ timeout: 12_000 });
  });

  test('bob can decline a proposed match', async ({ bobPage: page }) => {
    await page.goto('/matches');

    const declineBtn = page.getByRole('button', { name: /^decline$/i }).first();
    // Only proceed if bob still has a proposed match; otherwise skip gracefully
    const count = await declineBtn.count();
    if (count === 0) {
      test.skip(true, 'No proposed matches for bob — may have been accepted in prior test');
      return;
    }

    await declineBtn.click();

    await expect(
      page.getByText(/declined|no proposed matches/i)
    ).toBeVisible({ timeout: 12_000 });
  });

  test('carol gets address-verification error when accepting a match', async ({
    carolPage: page,
  }) => {
    // Carol has no address — accepting should surface an error with a link to /account
    await page.goto('/matches');

    const acceptBtn = page.getByRole('button', { name: /accept match/i }).first();
    const count = await acceptBtn.count();
    if (count === 0) {
      // Carol may have no proposed matches — this test is conditional
      test.skip(true, 'No proposed matches for carol');
      return;
    }

    await acceptBtn.click();

    // Expect an error message referencing address verification
    await expect(page.locator('.alert-error')).toBeVisible({ timeout: 10_000 });
  });

  test('accepted tab shows accepted matches', async ({ alicePage: page }) => {
    await page.goto('/matches');
    await page.getByRole('button', { name: /^accepted$/i }).click();

    // Either shows match cards or "no matches found"
    await expect(
      page.locator('[class*="matchCard"]').first().or(page.getByText(/no matches found/i))
    ).toBeVisible({ timeout: 10_000 });
  });

  test('declined tab shows declined matches', async ({ alicePage: page }) => {
    await page.goto('/matches');
    await page.getByRole('button', { name: /^declined$/i }).click();

    await expect(
      page.locator('[class*="matchCard"]').first().or(page.getByText(/no matches found/i))
    ).toBeVisible({ timeout: 10_000 });
  });
});
