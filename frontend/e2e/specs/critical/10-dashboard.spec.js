/**
 * critical/10-dashboard.spec.js
 *
 * Dashboard page:
 *   - Welcome heading renders with username
 *   - All six summary cards present
 *   - Quick action links visible and functional
 *   - Summary cards link to correct pages
 *   - Activity feed or empty state renders
 */
import { test, expect } from '../../fixtures/index.js';

test.describe('Dashboard', () => {
  test('dashboard loads with welcome heading', async ({ alicePage: page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    await expect(page.getByText(/welcome back/i).first()).toBeVisible({ timeout: 8_000 });
    await expect(page.getByRole('heading', { name: /welcome back.*alice_e2e/i })).toBeVisible({ timeout: 8_000 });
  });

  test('all six summary cards are visible', async ({ alicePage: page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    // Wait for spinner to clear
    const spinner = page.getByRole('status');
    if (await spinner.count() > 0) {
      await spinner.first().waitFor({ state: 'hidden', timeout: 15_000 });
    }

    await expect(page.getByText(/pending matches/i)).toBeVisible();
    await expect(page.getByText(/pending proposals/i)).toBeVisible();
    await expect(page.getByText(/active trades/i)).toBeVisible();
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

  test('Pending Matches card links to /matches', async ({ alicePage: page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    const spinner = page.getByRole('status');
    if (await spinner.count() > 0) {
      await spinner.first().waitFor({ state: 'hidden', timeout: 15_000 });
    }

    // Click the card containing "Pending Matches" label
    await page.getByText(/pending matches/i).first().click();
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
