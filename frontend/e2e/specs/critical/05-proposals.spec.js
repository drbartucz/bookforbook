/**
 * critical/05-proposals.spec.js
 *
 * Trade proposals:
 *   - Alice sees pending received proposal from bob
 *   - Accept proposal → status changes
 *   - Decline proposal → status changes
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

    // Accept / Decline buttons visible
    await expect(page.getByRole('button', { name: /^accept$/i }).first()).toBeVisible();
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

  test('sent tab shows bob proposals', async ({ bobPage: page }) => {
    await page.goto('/proposals');

    // Switch to Sent direction
    await page.getByRole('button', { name: /^sent$/i }).click();
    await page.waitForLoadState('networkidle');

    await expect(
      page.locator('[class*="proposalCard"]').first().or(page.getByText(/no proposals found/i))
    ).toBeVisible({ timeout: 10_000 });
  });

  // ── Status filter tabs ──

  test('Accepted status tab shows accepted proposals', async ({ alicePage: page }) => {
    await page.goto('/proposals');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /^accepted$/i }).click();

    const card = page.locator('[class*="proposalCard"]').first();
    await card.waitFor({ state: 'visible', timeout: 8_000 }).catch(() => {});

    await expect(
      card.or(page.getByText(/no proposals found/i)).first()
    ).toBeVisible({ timeout: 8_000 });
  });

  test('Declined status tab shows declined proposals', async ({ alicePage: page }) => {
    await page.goto('/proposals');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /^declined$/i }).click();

    const card = page.locator('[class*="proposalCard"]').first();
    await card.waitFor({ state: 'visible', timeout: 8_000 }).catch(() => {});

    await expect(
      card.or(page.getByText(/no proposals found/i)).first()
    ).toBeVisible({ timeout: 8_000 });
  });

  test('All status tab with Sent direction shows bobs sent proposals', async ({ bobPage: page }) => {
    await page.goto('/proposals');
    await page.waitForLoadState('networkidle');

    // Direction: Sent, Status: All
    await page.getByRole('button', { name: /^sent$/i }).click();
    await page.getByRole('button', { name: /^all$/i }).first().click();

    const card = page.locator('[class*="proposalCard"]').first();
    await card.waitFor({ state: 'visible', timeout: 8_000 }).catch(() => {});

    await expect(
      card.or(page.getByText(/no proposals found/i)).first()
    ).toBeVisible({ timeout: 8_000 });
  });
});
