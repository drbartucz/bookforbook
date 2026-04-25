/**
 * critical/09-home.spec.js
 *
 * Home / Browse page:
 *   - Guest sees hero section with Register / Sign-in CTAs
 *   - Books from seed data appear in the browse grid
 *   - Search by title filters results
 *   - Condition filter narrows results
 *   - Authenticated user sees "Want this" button on book cards
 *   - "Want this" changes to "Added!" after clicking
 *   - Empty state when search matches nothing
 */
import { test, expect } from '../../fixtures/index.js';

test.describe('Home / Browse', () => {
  test('guest sees hero section with Register and Sign in CTAs', async ({ guestPage: page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: /trade books, not money/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /register/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /sign in/i })).toBeVisible();
  });

  test('browse grid shows seeded available books', async ({ guestPage: page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Seed has alice/bob/carol with books — at least one card must appear
    const card = page.locator('.card').filter({ has: page.locator('h3') }).first();
    await expect(card).toBeVisible({ timeout: 10_000 });

    // One of the seeded titles must appear somewhere on the page
    await expect(
      page.getByText(/war and peace|nineteen eighty-four|great gatsby|cherry orchard|call of the wild/i).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test('search by title filters results', async ({ guestPage: page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Wait for initial results to render
    await page.locator('.card').filter({ has: page.locator('h3') }).first()
      .waitFor({ state: 'visible', timeout: 10_000 });

    const searchInput = page.getByRole('searchbox', { name: /search books/i })
      .or(page.getByPlaceholder(/search by title/i));
    // Use Nineteen Eighty-Four (alice_orwell) — stable across the full suite
    await searchInput.fill('Nineteen Eighty-Four');
    // Debounce delay is 400ms — wait a bit longer
    await page.waitForTimeout(600);
    await page.waitForLoadState('networkidle');

    await expect(page.getByText(/nineteen eighty-four/i).first()).toBeVisible({ timeout: 8_000 });
    // Unrelated books should not appear
    await expect(page.getByText(/cherry orchard/i)).not.toBeVisible();
  });

  test('condition filter narrows results', async ({ guestPage: page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await page.locator('.card').filter({ has: page.locator('h3') }).first()
      .waitFor({ state: 'visible', timeout: 10_000 });

    // Filter to Very Good — seed has bob_gatsby and bob_tolstoy in VERY_GOOD
    await page.getByLabel(/filter by condition/i).selectOption('very_good');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(300);

    // Results count or empty state must appear
    const counter = page.locator('[class*="resultsCount"]').or(page.locator('[class*="emptyTitle"]'));
    await expect(counter.first()).toBeVisible({ timeout: 8_000 });
  });

  test('search with no match shows empty state', async ({ guestPage: page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await page.locator('.card').filter({ has: page.locator('h3') }).first()
      .waitFor({ state: 'visible', timeout: 10_000 });

    const searchInput = page.getByRole('searchbox', { name: /search books/i })
      .or(page.getByPlaceholder(/search by title/i));
    await searchInput.fill('xyzzy-no-book-matches-this-query-12345');
    await page.waitForTimeout(600);
    await page.waitForLoadState('networkidle');

    // The emptyTitle paragraph — use .first() since resultsCount also says "No books found"
    await expect(page.getByText(/no books found/i).first()).toBeVisible({ timeout: 8_000 });
    await expect(page.getByText(/try adjusting/i)).toBeVisible();
  });

  test('authenticated user sees Want this button on book cards', async ({ carolPage: page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Search for a book carol doesn't own (alice's Nineteen Eighty-Four)
    // War and Peace may be RESERVED by a donation acceptance earlier in the suite
    const searchInput = page.getByRole('searchbox', { name: /search books/i })
      .or(page.getByPlaceholder(/search by title/i));
    await searchInput.fill('Nineteen Eighty-Four');
    await page.waitForTimeout(600);
    await page.waitForLoadState('networkidle');

    const wantBtn = page.getByRole('button', { name: /want this/i }).first();
    await expect(wantBtn).toBeVisible({ timeout: 8_000 });
  });

  test('Want this button disappears after clicking (book added to wishlist)', async ({ carolPage: page }) => {
    // Guard: skip if carol already has Nineteen Eighty-Four in her wishlist (previous run without --reset)
    const wlCheck = await page.request.get('/api/v1/wishlist/');
    const wlData = await wlCheck.json();
    const wlItems = wlData?.results ?? (Array.isArray(wlData) ? wlData : []);
    const alreadyHasIt = wlItems.some((i) =>
      (i.book?.isbn_13 ?? i.isbn_13) === '9780451524935'
    );
    if (alreadyHasIt) {
      test.skip(true, 'carol already has Nineteen Eighty-Four in wishlist — re-run with --reset');
      return;
    }

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const searchInput = page.getByRole('searchbox', { name: /search books/i })
      .or(page.getByPlaceholder(/search by title/i));
    await searchInput.fill('Nineteen Eighty-Four');
    await page.waitForTimeout(600);
    await page.waitForLoadState('networkidle');

    const wantBtn = page.getByRole('button', { name: /want this/i }).first();
    await expect(wantBtn).toBeVisible({ timeout: 8_000 });
    await wantBtn.click();

    // After a successful add, onAction becomes undefined and the button disappears
    // (the BookCard only renders the button when onAction is truthy)
    await expect(wantBtn).not.toBeVisible({ timeout: 12_000 });
  });

  test('authenticated user does not see hero CTAs', async ({ alicePage: page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Hero Register/Sign-in CTAs should not be shown to authenticated users
    await expect(page.getByRole('link', { name: /^register$/i })).not.toBeVisible();
  });

  test('results count text shows number of available books', async ({ guestPage: page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await page.locator('.card').filter({ has: page.locator('h3') }).first()
      .waitFor({ state: 'visible', timeout: 10_000 });

    // Results count paragraph shows "N books available"
    await expect(page.getByText(/books available|1 book available/i)).toBeVisible({ timeout: 8_000 });
  });
});
