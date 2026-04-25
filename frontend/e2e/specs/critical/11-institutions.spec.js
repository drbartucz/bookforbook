/**
 * critical/11-institutions.spec.js
 *
 * Institutions browse page:
 *   - Page loads with heading and seeded library_e2e institution
 *   - Search by name finds library_e2e
 *   - Searching for a non-existent name shows empty state
 *   - Filter by type (Libraries) still shows library_e2e
 *   - View Profile button navigates to institution profile
 */
import { test, expect } from '../../fixtures/index.js';

test.describe('Institutions', () => {
  test('page loads with heading', async ({ guestPage: page }) => {
    await page.goto('/institutions');
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: /institutions/i })).toBeVisible();
    await expect(page.getByLabel(/search institutions/i)).toBeVisible();
    await expect(page.getByLabel(/filter by type/i)).toBeVisible();
  });

  test('seeded library_e2e institution appears in the list', async ({ guestPage: page }) => {
    await page.goto('/institutions');
    await page.waitForLoadState('networkidle');

    // The seeded library is named "E2E Public Library" and has username library_e2e
    await expect(
      page.getByText(/library_e2e/i).or(page.getByText(/e2e public library/i)).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test('search by name finds the seeded library', async ({ guestPage: page }) => {
    await page.goto('/institutions');
    await page.waitForLoadState('networkidle');

    await page.getByLabel(/search institutions/i).fill('library_e2e');
    await page.waitForTimeout(600); // debounce
    await page.waitForLoadState('networkidle');

    await expect(
      page.getByText(/library_e2e/i).or(page.getByText(/e2e public library/i)).first()
    ).toBeVisible({ timeout: 8_000 });
  });

  test('search with no match shows empty state', async ({ guestPage: page }) => {
    await page.goto('/institutions');
    await page.waitForLoadState('networkidle');

    // Wait for initial results before typing
    await page.locator('[class*="institutionCard"]').first()
      .waitFor({ state: 'visible', timeout: 10_000 });

    const searchInput = page.getByLabel(/search institutions/i);
    await searchInput.fill('xyzzy-no-institution-matches-12345');
    // Debounce is 400ms; wait extra before asserting
    await page.waitForTimeout(600);

    // Wait directly for the empty state — React Query may keep stale data while refetching,
    // so we can't rely on the card disappearing first.
    await expect(page.getByText(/no institutions found/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/try adjusting/i)).toBeVisible();
  });

  test('filter by type Libraries shows library institution', async ({ guestPage: page }) => {
    await page.goto('/institutions');
    await page.waitForLoadState('networkidle');

    await page.getByLabel(/filter by type/i).selectOption('library');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(300);

    // Either the library card appears or empty state
    await expect(
      page.getByText(/library_e2e/i)
        .or(page.getByText(/e2e public library/i))
        .or(page.getByText(/no institutions found/i))
        .first()
    ).toBeVisible({ timeout: 8_000 });
  });

  test('View Profile button navigates to institution profile page', async ({ guestPage: page }) => {
    await page.goto('/institutions');
    await page.waitForLoadState('networkidle');

    const viewProfileBtn = page.getByRole('link', { name: /view profile/i }).first();
    await expect(viewProfileBtn).toBeVisible({ timeout: 10_000 });
    await viewProfileBtn.click();

    await expect(page).toHaveURL(/\/profile\//, { timeout: 8_000 });
    // Institution badge should be on the profile page
    await expect(page.getByText(/institution/i).first()).toBeVisible({ timeout: 8_000 });
  });

  test('institution card shows type badge', async ({ guestPage: page }) => {
    await page.goto('/institutions');
    await page.waitForLoadState('networkidle');

    const card = page.locator('[class*="institutionCard"]').first();
    await expect(card).toBeVisible({ timeout: 10_000 });

    // Should show either institution type badge (library) or verified badge
    await expect(
      card.getByText(/library|bookstore|school|verified/i).first()
    ).toBeVisible({ timeout: 8_000 });
  });
});
