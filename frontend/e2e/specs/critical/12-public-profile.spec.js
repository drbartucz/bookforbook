/**
 * critical/12-public-profile.spec.js
 *
 * Public profile page:
 *   - Individual user profile (navigated to directly via known ID)
 *   - Institution profile (navigated via institutions page)
 *   - Profile header sections: username, stats, member since
 *   - Offered Books and Wanted Books sections present
 *   - Own profile: shows shipping address section
 *   - Own profile: shows wishlist match preferences form and can save
 *   - Custom edition preference reveals additional controls
 */
import { test, expect } from '../../fixtures/index.js';

/**
 * Get the authenticated user's own profile URL by reading the user ID
 * from the React app's localStorage (JWT auth is stored there, not in cookies).
 */
async function getOwnProfileUrl(page) {
  // Navigate to the app first so localStorage is accessible for this origin
  await page.goto('/');
  const userId = await page.evaluate(() => {
    const stored = localStorage.getItem('bookforbook-auth');
    return JSON.parse(stored)?.state?.user?.id;
  });
  return `/profile/${userId}`;
}

test.describe('Public Profile', () => {
  test('individual user profile loads', async ({ alicePage: page }) => {
    const profileUrl = await getOwnProfileUrl(page);
    await page.goto(profileUrl);
    await page.waitForLoadState('networkidle');

    // Username displayed as @username in the profile h1
    await expect(page.getByRole('heading', { name: /^@alice_e2e$/i })).toBeVisible({ timeout: 8_000 });
  });

  test('profile header shows Trades and Member since stats', async ({ alicePage: page }) => {
    const profileUrl = await getOwnProfileUrl(page);
    await page.goto(profileUrl);
    await page.waitForLoadState('networkidle');

    await expect(page.getByText(/trades/i).first()).toBeVisible({ timeout: 8_000 });
    await expect(page.getByText(/member since/i)).toBeVisible({ timeout: 8_000 });
  });

  test('profile has Offered Books section', async ({ alicePage: page }) => {
    const profileUrl = await getOwnProfileUrl(page);
    await page.goto(profileUrl);
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: /offered books/i })).toBeVisible({ timeout: 8_000 });
    // Alice has 3 seeded books — at least one should appear
    await expect(
      page.locator('[class*="wantedItem"]').first()
        .or(page.getByText(/no books offered yet/i))
    ).toBeVisible({ timeout: 8_000 });
  });

  test('profile has Wanted Books section for individual user', async ({ alicePage: page }) => {
    const profileUrl = await getOwnProfileUrl(page);
    await page.goto(profileUrl);
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: /wanted books/i })).toBeVisible({ timeout: 8_000 });
  });

  test('profile has Recent Ratings section', async ({ alicePage: page }) => {
    const profileUrl = await getOwnProfileUrl(page);
    await page.goto(profileUrl);
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: /recent ratings/i })).toBeVisible({ timeout: 8_000 });
    await expect(
      page.locator('[class*="ratingItem"]').first()
        .or(page.getByText(/no ratings yet/i))
    ).toBeVisible({ timeout: 8_000 });
  });

  test('institution profile loads via institutions page', async ({ guestPage: page }) => {
    await page.goto('/institutions');
    await page.waitForLoadState('networkidle');

    const viewBtn = page.getByRole('link', { name: /view profile/i }).first();
    await expect(viewBtn).toBeVisible({ timeout: 10_000 });
    await viewBtn.click();

    await expect(page).toHaveURL(/\/profile\//, { timeout: 8_000 });
    await expect(page.getByText(/institution/i).first()).toBeVisible({ timeout: 8_000 });
  });

  test('institution profile shows Wanted Books section', async ({ guestPage: page }) => {
    await page.goto('/institutions');
    await page.waitForLoadState('networkidle');

    await page.getByRole('link', { name: /view profile/i }).first().click();
    await expect(page).toHaveURL(/\/profile\//);

    await expect(page.getByRole('heading', { name: /wanted books/i })).toBeVisible({ timeout: 8_000 });
    await expect(
      page.locator('[class*="wantedItem"]').first()
        .or(page.getByText(/no wanted books listed/i))
    ).toBeVisible({ timeout: 8_000 });
  });

  test('institution profile does not show Wishlist preferences (own-profile only)', async ({ guestPage: page }) => {
    await page.goto('/institutions');
    await page.waitForLoadState('networkidle');

    await page.getByRole('link', { name: /view profile/i }).first().click();
    await expect(page).toHaveURL(/\/profile\//);

    // Wishlist match preferences form is only shown on own profile
    await expect(page.getByRole('heading', { name: /wishlist match preferences/i })).not.toBeVisible();
  });

  test('own profile shows shipping address section', async ({ alicePage: page }) => {
    const profileUrl = await getOwnProfileUrl(page);
    await page.goto(profileUrl);
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: /shipping address/i })).toBeVisible({ timeout: 8_000 });
    // Alice has a verified address — "Edit address" link should appear
    await expect(page.getByRole('link', { name: /edit address/i })).toBeVisible({ timeout: 8_000 });
  });

  test('own profile shows wishlist match preferences form', async ({ alicePage: page }) => {
    const profileUrl = await getOwnProfileUrl(page);
    await page.goto(profileUrl);
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: /wishlist match preferences/i })).toBeVisible({ timeout: 8_000 });
    await expect(page.getByLabel(/minimum acceptable condition/i)).toBeVisible();
    await expect(page.getByLabel(/edition matching/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /save wishlist preferences/i })).toBeVisible();
  });

  test('own profile wishlist preferences can be saved', async ({ alicePage: page }) => {
    const profileUrl = await getOwnProfileUrl(page);
    await page.goto(profileUrl);
    await page.waitForLoadState('networkidle');

    await page.getByLabel(/edition matching/i).selectOption('same_language');
    await page.getByRole('button', { name: /save wishlist preferences/i }).click();

    await expect(page.locator('.alert-success')).toBeVisible({ timeout: 8_000 });
  });

  test('custom edition preference shows additional controls', async ({ alicePage: page }) => {
    const profileUrl = await getOwnProfileUrl(page);
    await page.goto(profileUrl);
    await page.waitForLoadState('networkidle');

    await page.getByLabel(/edition matching/i).selectOption('custom');

    await expect(page.getByText(/include translations/i)).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText(/exclude abridged/i)).toBeVisible();
    await expect(page.getByText(/allowed formats/i)).toBeVisible();
    // Format buttons
    await expect(page.getByRole('button', { name: /hardcover/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /paperback/i })).toBeVisible();
  });

  test('bob profile is viewable by alice (someone else\'s profile)', async ({ alicePage: page }) => {
    // Navigate to bob's profile via the proposals page (bob sent alice a proposal)
    await page.goto('/proposals');
    await page.waitForLoadState('networkidle');

    // The proposal card has a link to bob's profile: "From: @bob_e2e"
    const bobLink = page.getByRole('link', { name: /@bob_e2e/i }).first();
    await expect(bobLink).toBeVisible({ timeout: 10_000 });
    await bobLink.click();

    await expect(page).toHaveURL(/\/profile\//, { timeout: 8_000 });
    await expect(page.getByRole('heading', { name: /^@bob_e2e$/i })).toBeVisible({ timeout: 8_000 });
    // Own-profile sections should NOT appear
    await expect(page.getByRole('heading', { name: /shipping address/i })).not.toBeVisible();
    await expect(page.getByRole('heading', { name: /wishlist match preferences/i })).not.toBeVisible();
  });
});
