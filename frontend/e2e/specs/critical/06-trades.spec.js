/**
 * critical/06-trades.spec.js
 *
 * Trade list + detail page:
 *   - Trades list shows seeded CONFIRMED trade
 *   - Navigate to trade detail via click
 *   - Mark book as shipped (with tracking number)
 *   - Send a message in the trade thread
 */
import { test, expect } from '../../fixtures/index.js';
import { autoConfirmDialog } from '../../helpers/wait.js';

test.describe('Trades', () => {
  test('trades list page loads for alice', async ({ alicePage: page }) => {
    await page.goto('/trades');
    await expect(page.getByRole('heading', { name: /trades/i })).toBeVisible();
    await page.waitForLoadState('networkidle');

    // Alice has a seeded CONFIRMED trade
    const tradeCard = page.locator('[class*="tradeCard"]').first();
    await expect(tradeCard).toBeVisible({ timeout: 10_000 });
  });

  test('trade detail page navigates via clicking trade card', async ({ alicePage: page }) => {
    await page.goto('/trades');
    await page.waitForLoadState('networkidle');

    // Click first trade card (it is a <Link>)
    const tradeCard = page.locator('[class*="tradeCard"]').first();
    await expect(tradeCard).toBeVisible({ timeout: 10_000 });
    await tradeCard.click();

    // Should land on /trades/:id
    await expect(page).toHaveURL(/\/trades\/\d+/, { timeout: 8_000 });
    await expect(page.getByText(/trade #/i)).toBeVisible();
  });

  test('trade detail shows book exchange summary', async ({ alicePage: page }) => {
    await page.goto('/trades');
    await page.waitForLoadState('networkidle');

    await page.locator('[class*="tradeCard"]').first().click();
    await expect(page).toHaveURL(/\/trades\/\d+/);

    await expect(page.getByText(/you send/i)).toBeVisible();
    await expect(page.getByText(/you receive/i)).toBeVisible();
  });

  test('alice can mark book as shipped', async ({ alicePage: page }) => {
    // Navigate directly to trades list and find the confirmed trade
    await page.goto('/trades');
    await page.waitForLoadState('networkidle');

    await page.locator('[class*="tradeCard"]').first().click();
    await expect(page).toHaveURL(/\/trades\/\d+/);

    // "Mark My Book as Shipped" button should be present for CONFIRMED trade
    const shipBtn = page.getByRole('button', { name: /mark my book as shipped/i });
    const count = await shipBtn.count();
    if (count === 0) {
      // Trade may already be in a later state
      test.skip(true, 'Trade is past the shipping step');
      return;
    }

    await shipBtn.click();

    // Tracking form appears
    await expect(page.getByLabel(/tracking number/i)).toBeVisible({ timeout: 5_000 });
    await page.getByLabel(/tracking number/i).fill('1Z999AA10123456784');

    // Confirm shipped
    await page.getByRole('button', { name: /confirm shipped/i }).click();

    // Status badge should update
    await expect(
      page.getByText(/shipping|books in transit/i)
    ).toBeVisible({ timeout: 12_000 });
  });

  test('alice can send a message in the trade thread', async ({ alicePage: page }) => {
    await page.goto('/trades');
    await page.waitForLoadState('networkidle');

    await page.locator('[class*="tradeCard"]').first().click();
    await expect(page).toHaveURL(/\/trades\/\d+/);

    // Message textarea
    const msgArea = page.getByPlaceholder(/your message/i)
      .or(page.locator('textarea[maxlength]').first());
    await expect(msgArea).toBeVisible({ timeout: 8_000 });

    await msgArea.fill('E2E test message — please ignore.');
    await page.getByRole('button', { name: /send/i }).last().click();

    // Message appears in thread
    await expect(
      page.getByText('E2E test message — please ignore.')
    ).toBeVisible({ timeout: 10_000 });
  });

  test('back to trades link navigates to list', async ({ alicePage: page }) => {
    await page.goto('/trades');
    await page.waitForLoadState('networkidle');

    await page.locator('[class*="tradeCard"]').first().click();
    await expect(page).toHaveURL(/\/trades\/\d+/);

    await page.getByText(/back to trades/i).click();
    await expect(page).toHaveURL(/\/trades$/, { timeout: 8_000 });
  });
});
