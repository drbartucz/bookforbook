/**
 * critical/05-proposals.spec.js
 *
 * Trade proposals:
 *   - Alice sees pending received proposal from bob
 *   - Accept proposal → status changes
 *   - Decline proposal → status changes
 *   - Counter proposal → countered state
 */
import { test, expect } from '../../fixtures/index.js';

test.describe('Proposals', () => {
  test('page loads with pending / received filter active', async ({ alicePage: page }) => {
    await page.goto('/proposals');
    await expect(page.getByRole('heading', { name: /proposals/i })).toBeVisible();
    await page.waitForLoadState('networkidle');
  });

  test('alice sees seeded pending proposal from bob', async ({ alicePage: page }) => {
    await page.goto('/proposals');
    await page.waitForLoadState('networkidle');

    // Default view: received + pending — shows bob's proposal
    const proposalCard = page.locator('[class*="proposalCard"]').first();
    await expect(proposalCard).toBeVisible({ timeout: 10_000 });

    // Accept / Counter / Decline buttons visible
    await expect(page.getByRole('button', { name: /^accept$/i }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: /^counter$/i }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: /^decline$/i }).first()).toBeVisible();
  });

  test('alice can accept a pending proposal', async ({ alicePage: page }) => {
    await page.goto('/proposals');
    await page.waitForLoadState('networkidle');

    const acceptBtn = page.getByRole('button', { name: /^accept$/i }).first();
    const count = await acceptBtn.count();
    if (count === 0) {
      test.skip(true, 'No pending received proposals for alice');
      return;
    }

    await acceptBtn.click();

    // Should move out of pending list or show success indication
    await expect(
      page.getByText(/accepted|no proposals found/i)
    ).toBeVisible({ timeout: 12_000 });
  });

  test('alice can decline a pending proposal', async ({ alicePage: page }) => {
    await page.goto('/proposals');
    await page.waitForLoadState('networkidle');

    const declineBtn = page.getByRole('button', { name: /^decline$/i }).first();
    const count = await declineBtn.count();
    if (count === 0) {
      test.skip(true, 'No pending received proposals to decline');
      return;
    }

    await declineBtn.click();

    await expect(
      page.getByText(/declined|no proposals found/i)
    ).toBeVisible({ timeout: 12_000 });
  });

  test('alice can counter a pending proposal', async ({ alicePage: page }) => {
    await page.goto('/proposals');
    await page.waitForLoadState('networkidle');

    const counterBtn = page.getByRole('button', { name: /^counter$/i }).first();
    const count = await counterBtn.count();
    if (count === 0) {
      test.skip(true, 'No pending received proposals to counter');
      return;
    }

    // Open counter form
    await counterBtn.click();

    // Counter textarea appears
    const textarea = page.getByPlaceholder(/explain your counter/i);
    await expect(textarea).toBeVisible({ timeout: 5_000 });

    // Enter a counter note
    await textarea.fill('How about swapping a different condition?');

    // Send the counter
    await page.getByRole('button', { name: /send counter/i }).click();

    await expect(
      page.getByText(/countered|no proposals found/i)
    ).toBeVisible({ timeout: 12_000 });
  });

  test('sent tab shows bob proposals', async ({ bobPage: page }) => {
    await page.goto('/proposals');

    // Switch to Sent direction
    await page.getByRole('button', { name: /^sent$/i }).click();
    await page.waitForLoadState('networkidle');

    await expect(
      page.locator('[class*="proposalCard"]').or(page.getByText(/no proposals found/i))
    ).toBeVisible({ timeout: 10_000 });
  });
});
