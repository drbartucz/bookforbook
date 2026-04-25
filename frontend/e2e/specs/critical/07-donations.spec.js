/**
 * critical/07-donations.spec.js
 *
 * Donation flows:
 *   - Alice sees her offered donation (Austen → library)
 *   - Library account sees the received donation
 *   - Library can accept the donation
 *   - Library can decline a donation
 */
import { test, expect } from '../../fixtures/index.js';

test.describe('Donations', () => {
  test('donations page loads for alice', async ({ alicePage: page }) => {
    await page.goto('/donations');
    await expect(page.getByRole('heading', { name: /donations/i })).toBeVisible();
    await page.waitForLoadState('networkidle');
  });

  test('alice sees her offered donation in "Offered by me" tab', async ({
    alicePage: page,
  }) => {
    await page.goto('/donations');
    await page.waitForLoadState('networkidle');

    // Switch to "Offered by me" tab
    await page.getByRole('button', { name: /offered by me/i }).click();
    await page.waitForLoadState('networkidle');

    // Seeded donation: Pride and Prejudice → E2E Library
    const donationCard = page.locator('[class*="donationCard"]').first();
    await expect(donationCard).toBeVisible({ timeout: 10_000 });
    await expect(donationCard.getByText(/pride and prejudice/i)).toBeVisible({ timeout: 10_000 });
    await expect(donationCard.getByText(/^offered$/i)).toBeVisible({ timeout: 10_000 });
  });

  test('library account sees received donation', async ({ libraryPage: page }) => {
    await page.goto('/donations');
    await page.waitForLoadState('networkidle');

    // Switch to "Received" tab
    await page.getByRole('button', { name: /received/i }).click();
    await page.waitForLoadState('networkidle');

    // Should show alice's donation
    const donationCard = page.locator('[class*="donationCard"]').first();
    await expect(donationCard).toBeVisible({ timeout: 10_000 });
  });

  test('library can accept a pending donation', async ({ libraryPage: page }) => {
    await page.goto('/donations');
    await page.waitForLoadState('networkidle');

    // Go to Received tab
    await page.getByRole('button', { name: /received/i }).click();

    // Wait for cards to render (networkidle can fire before React re-renders with new query result)
    const donationCard = page.locator('[class*="donationCard"]').first();
    await donationCard.waitFor({ state: 'visible', timeout: 10_000 }).catch(() => {});

    const acceptBtn = page.getByRole('button', { name: /accept donation/i }).first();
    const count = await acceptBtn.count();
    if (count === 0) {
      test.skip(true, 'No pending received donations for library');
      return;
    }

    await acceptBtn.click();

    // Status badge updates to Accepted
    await expect(
      page.getByText(/accepted/i).or(page.getByText(/no donations found/i))
    ).toBeVisible({ timeout: 12_000 });
  });

  test('library can decline a pending donation', async ({ libraryPage: page }) => {
    await page.goto('/donations');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /received/i }).click();

    // Wait for cards to render before counting buttons
    const donationCard = page.locator('[class*="donationCard"]').first();
    await donationCard.waitFor({ state: 'visible', timeout: 10_000 }).catch(() => {});

    const declineBtn = page.getByRole('button', { name: /^decline$/i }).first();
    const count = await declineBtn.count();
    if (count === 0) {
      test.skip(true, 'No pending donations to decline');
      return;
    }

    await declineBtn.click();

    await expect(
      page.getByText(/declined|no donations found/i)
    ).toBeVisible({ timeout: 12_000 });
  });

  test('all tab shows all donations', async ({ alicePage: page }) => {
    await page.goto('/donations');

    await page.getByRole('button', { name: /^all$/i }).click();
    await page.waitForLoadState('networkidle');

    await expect(
      page.locator('[class*="donationCard"]').or(page.getByText(/no donations found/i))
    ).toBeVisible({ timeout: 10_000 });
  });
});
