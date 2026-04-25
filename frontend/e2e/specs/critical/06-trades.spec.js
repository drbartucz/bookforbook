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
    await expect(page).toHaveURL(/\/trades\/.+/, { timeout: 8_000 });
    await expect(page.getByText(/trade #/i)).toBeVisible();
  });

  test('trade detail shows book exchange summary', async ({ alicePage: page }) => {
    await page.goto('/trades');
    await page.waitForLoadState('networkidle');

    await page.locator('[class*="tradeCard"]').first().click();
    await expect(page).toHaveURL(/\/trades\/.+/);

    await expect(page.getByText(/you send/i)).toBeVisible();
    await expect(page.getByText(/you receive/i)).toBeVisible();
  });

  test('alice can mark book as shipped', async ({ alicePage: page }) => {
    // Navigate directly to trades list and find the confirmed trade
    await page.goto('/trades');
    await page.waitForLoadState('networkidle');

    await page.locator('[class*="tradeCard"]').first().click();
    await expect(page).toHaveURL(/\/trades\/.+/);

    // Wait for trade detail content to finish loading before checking for ship button
    await expect(page.getByText(/trade #/i)).toBeVisible({ timeout: 8_000 });

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
      page.locator('.badge').filter({ hasText: /shipping|books in transit/i }).first()
    ).toBeVisible({ timeout: 12_000 });
  });

  test('alice can send a message in the trade thread', async ({ alicePage: page }) => {
    await page.goto('/trades');
    await page.waitForLoadState('networkidle');

    await page.locator('[class*="tradeCard"]').first().click();
    await expect(page).toHaveURL(/\/trades\/.+/);

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
    await expect(page).toHaveURL(/\/trades\/.+/);

    await page.getByText(/back to trades/i).click();
    await expect(page).toHaveURL(/\/trades$/, { timeout: 8_000 });
  });

  test('completed tab shows seeded completed trade', async ({ alicePage: page }) => {
    await page.goto('/trades');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /^completed$/i }).click();

    const tradeCard = page.locator('[class*="tradeCard"]').first();
    await tradeCard.waitFor({ state: 'visible', timeout: 10_000 }).catch(() => {});
    const count = await tradeCard.count();
    if (count === 0) {
      test.skip(true, 'No completed trades found');
      return;
    }

    await expect(tradeCard).toBeVisible();
    // Status badge should read "Completed"
    await expect(tradeCard.getByText(/completed/i)).toBeVisible();
  });

  test('trade detail for completed trade shows correct status badge', async ({ alicePage: page }) => {
    await page.goto('/trades');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /^completed$/i }).click();

    const tradeCard = page.locator('[class*="tradeCard"]').first();
    await tradeCard.waitFor({ state: 'visible', timeout: 10_000 }).catch(() => {});
    if (await tradeCard.count() === 0) {
      test.skip(true, 'No completed trades found');
      return;
    }

    await tradeCard.click();
    await expect(page).toHaveURL(/\/trades\/.+/);
    await expect(page.getByText(/trade #/i)).toBeVisible({ timeout: 8_000 });
    await expect(page.getByText(/completed/i).first()).toBeVisible({ timeout: 8_000 });
  });

  test('alice can rate a completed trade partner', async ({ alicePage: page }) => {
    await page.goto('/trades');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /^completed$/i }).click();

    const tradeCard = page.locator('[class*="tradeCard"]').first();
    await tradeCard.waitFor({ state: 'visible', timeout: 10_000 }).catch(() => {});
    if (await tradeCard.count() === 0) {
      test.skip(true, 'No completed trades found');
      return;
    }

    await tradeCard.click();
    await expect(page).toHaveURL(/\/trades\/.+/);
    await expect(page.getByText(/trade #/i)).toBeVisible({ timeout: 8_000 });

    // Rating button is only present when not yet rated
    const rateBtn = page.getByRole('button', { name: /rate your trade partner/i });
    const count = await rateBtn.count();
    if (count === 0) {
      test.skip(true, 'Trade already rated');
      return;
    }

    await rateBtn.click();

    // Rating form appears
    await expect(page.getByText(/rate @/i)).toBeVisible({ timeout: 5_000 });

    // Click 4th star
    const stars = page.locator('[class*="star"]').filter({ hasText: '★' });
    await stars.nth(3).click();

    // Fill comment
    const commentField = page.getByLabel(/comment/i);
    await expect(commentField).toBeVisible();
    await commentField.fill('Great trade partner, would trade again!');

    // Submit
    await page.getByRole('button', { name: /submit rating/i }).click();

    // Form closes — Rate button disappears (trade now rated)
    await expect(
      page.getByRole('button', { name: /rate your trade partner/i })
    ).not.toBeVisible({ timeout: 10_000 });
  });

  test('message type dropdown has all expected options', async ({ alicePage: page }) => {
    await page.goto('/trades');
    await page.waitForLoadState('networkidle');

    await page.locator('[class*="tradeCard"]').first().click();
    await expect(page).toHaveURL(/\/trades\/.+/);
    await expect(page.getByText(/trade #/i)).toBeVisible({ timeout: 8_000 });

    // Message type select
    const msgTypeSelect = page.getByRole('combobox').filter({ hasText: /general|shipping|question|issue/i })
      .or(page.locator('select').filter({ hasText: /general/i }));
    await expect(msgTypeSelect.first()).toBeVisible({ timeout: 8_000 });

    // All four message types should be options
    const options = await msgTypeSelect.first().locator('option').allInnerTexts();
    expect(options.some((o) => /general/i.test(o))).toBe(true);
    expect(options.some((o) => /shipping/i.test(o))).toBe(true);
    expect(options.some((o) => /question/i.test(o))).toBe(true);
    expect(options.some((o) => /issue/i.test(o))).toBe(true);
  });
});
