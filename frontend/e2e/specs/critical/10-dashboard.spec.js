/**
 * critical/10-dashboard.spec.js
 *
 * Dashboard page:
 *   - Welcome heading renders with username
 *   - All seven summary cards present
 *   - Quick action links visible and functional
 *   - Summary cards link to correct pages
 *   - Activity feed or empty state renders
 *   - All card counts are valid non-negative integers (exercises the
 *     parsePaginatedResponse fix for plain-array API responses)
 */
import { test, expect } from '../../fixtures/index.js';

/** Read the numeric value displayed inside a named summary card. */
async function getCardCount(page, labelText) {
  const card = page.locator('[class*="summaryCard"]').filter({ hasText: labelText });
  const text = await card.locator('[class*="summaryValue"]').textContent();
  return parseInt(text.trim(), 10);
}

/** Wait for the loading spinner to clear and all summary cards to be visible. */
async function waitForDashboard(page) {
  await page.goto('/dashboard');
  await page.waitForLoadState('networkidle');
  const spinner = page.getByRole('status');
  if (await spinner.count() > 0) {
    await spinner.first().waitFor({ state: 'hidden', timeout: 15_000 });
  }
  // Confirm at least one card is visible before proceeding
  await expect(page.locator('[class*="summaryCard"]').first()).toBeVisible({ timeout: 10_000 });
}

test.describe('Dashboard', () => {
  test('dashboard loads with welcome heading', async ({ alicePage: page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    await expect(page.getByText(/welcome back/i).first()).toBeVisible({ timeout: 8_000 });
    await expect(page.getByRole('heading', { name: /welcome back.*alice_e2e/i })).toBeVisible({ timeout: 8_000 });
  });

  test('all seven summary cards are visible', async ({ alicePage: page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    // Wait for spinner to clear
    const spinner = page.getByRole('status');
    if (await spinner.count() > 0) {
      await spinner.first().waitFor({ state: 'hidden', timeout: 15_000 });
    }

    await expect(page.getByText(/proposed matches/i)).toBeVisible();
    await expect(page.getByText(/potential partners/i)).toBeVisible();
    await expect(page.getByText(/pending proposals/i)).toBeVisible();
    await expect(
      page.locator('[class*="summaryCard"]').filter({ hasText: 'Active Trades' })
    ).toBeVisible();
    await expect(page.getByText(/total trades/i)).toBeVisible();
    await expect(page.getByText(/books offered/i)).toBeVisible();
    await expect(page.getByText(/books wanted/i)).toBeVisible();
  });

  test('quick action buttons are visible', async ({ alicePage: page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('link', { name: /\+ add book/i })).toBeVisible({ timeout: 8_000 });
    await expect(page.getByRole('link', { name: /browse books/i })).toBeVisible({ timeout: 8_000 });
  });

  test('summary cards show numeric values', async ({ alicePage: page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    const spinner = page.getByRole('status');
    if (await spinner.count() > 0) {
      await spinner.first().waitFor({ state: 'hidden', timeout: 15_000 });
    }

    // Each summary card renders a number (0 or more)
    const summaryValues = page.locator('[class*="summaryValue"]');
    await expect(summaryValues.first()).toBeVisible({ timeout: 8_000 });
    const count = await summaryValues.count();
    expect(count).toBeGreaterThanOrEqual(4);
  });

  test('all card counts are valid non-negative integers (verifies parsePaginatedResponse fix)', async ({ alicePage: page }) => {
    await waitForDashboard(page);

    const CARD_LABELS = [
      'Proposed Matches',
      'Pending Proposals',
      'Active Trades',
      'Total Trades',
      'Books Offered',
      'Books Wanted',
    ];

    for (const label of CARD_LABELS) {
      const count = await getCardCount(page, label);
      expect(Number.isInteger(count), `"${label}" count should be an integer, got: ${count}`).toBe(true);
      expect(count, `"${label}" count should be >= 0`).toBeGreaterThanOrEqual(0);
    }

    // Potential Partners uses a different layout — just verify it renders a number
    const ppCard = page.locator('[class*="summaryCard"]').filter({ hasText: 'Potential Partners' });
    const ppText = (await ppCard.locator('[class*="summaryValue"]').textContent()).trim();
    expect(Number.isInteger(parseInt(ppText, 10))).toBe(true);
  });

  test('alice has at least one active trade from the seeded confirmed trade', async ({ alicePage: page }) => {
    await waitForDashboard(page);

    // seed_e2e always creates a CONFIRMED trade for alice — it should show ≥ 1
    // This test specifically verifies the "Active Trades" bug is fixed (it was always 0 before)
    const activeTrades = await getCardCount(page, 'Active Trades');
    expect(activeTrades, 'Active Trades should be >= 1 given the seeded confirmed trade').toBeGreaterThanOrEqual(1);
  });

  test('alice has books offered from seeded inventory', async ({ alicePage: page }) => {
    await waitForDashboard(page);

    // seed_e2e creates 3 books for alice (Orwell, Hemingway, Austen)
    // Some earlier tests may modify inventory, so assert >= 1
    const booksOffered = await getCardCount(page, 'Books Offered');
    expect(booksOffered, 'Books Offered should be >= 1').toBeGreaterThanOrEqual(1);
  });

  test('Proposed Matches card links to /matches', async ({ alicePage: page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    const spinner = page.getByRole('status');
    if (await spinner.count() > 0) {
      await spinner.first().waitFor({ state: 'hidden', timeout: 15_000 });
    }

    // Click the card containing "Proposed Matches" label
    await page.getByText(/proposed matches/i).first().click();
    await expect(page).toHaveURL(/\/matches/, { timeout: 8_000 });
  });

  test('Active Trades card links to /trades', async ({ alicePage: page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    const spinner = page.getByRole('status');
    if (await spinner.count() > 0) {
      await spinner.first().waitFor({ state: 'hidden', timeout: 15_000 });
    }

    await page.getByText(/active trades/i).first().click();
    await expect(page).toHaveURL(/\/trades/, { timeout: 8_000 });
  });

  test('Pending Proposals card links to /proposals', async ({ alicePage: page }) => {
    await waitForDashboard(page);

    await page.locator('[class*="summaryCard"]').filter({ hasText: 'Pending Proposals' }).click();
    await expect(page).toHaveURL(/\/proposals/, { timeout: 8_000 });
  });

  test('Books Offered card links to /my-books', async ({ alicePage: page }) => {
    await waitForDashboard(page);

    await page.locator('[class*="summaryCard"]').filter({ hasText: 'Books Offered' }).click();
    await expect(page).toHaveURL(/\/my-books/, { timeout: 8_000 });
  });

  test('Books Wanted card links to /wishlist', async ({ alicePage: page }) => {
    await waitForDashboard(page);

    await page.locator('[class*="summaryCard"]').filter({ hasText: 'Books Wanted' }).click();
    await expect(page).toHaveURL(/\/wishlist/, { timeout: 8_000 });
  });

  test('Potential Partners card links to /discovery', async ({ alicePage: page }) => {
    await waitForDashboard(page);

    await page.locator('[class*="summaryCard"]').filter({ hasText: 'Potential Partners' }).click();
    await expect(page).toHaveURL(/\/discovery/, { timeout: 8_000 });
  });

  test('activity feed or empty-activity state is shown', async ({ alicePage: page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    const spinner = page.getByRole('status');
    if (await spinner.count() > 0) {
      await spinner.first().waitFor({ state: 'hidden', timeout: 15_000 });
    }

    const hasActivity = await page.locator('[class*="activityItem"]').count();
    if (hasActivity === 0) {
      await expect(page.getByText(/no activity yet/i)).toBeVisible({ timeout: 8_000 });
    } else {
      await expect(page.locator('[class*="activityItem"]').first()).toBeVisible();
    }
  });

  test('Add Book quick action navigates to /my-books', async ({ alicePage: page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    await page.getByRole('link', { name: /\+ add book/i }).click();
    await expect(page).toHaveURL(/\/my-books/, { timeout: 8_000 });
  });

  test('Browse Books quick action navigates to home page', async ({ alicePage: page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    await page.getByRole('link', { name: /browse books/i }).click();
    // Home page URL is just /
    await expect(page).toHaveURL(/localhost:\d+\/?$/, { timeout: 8_000 });
    await expect(page.getByRole('heading', { name: /trade books/i })).toBeVisible({ timeout: 8_000 });
  });
});
