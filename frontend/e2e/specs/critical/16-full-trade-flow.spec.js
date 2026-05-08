/**
 * critical/16-full-trade-flow.spec.js
 *
 * End-to-end test for the complete book-swap lifecycle:
 *
 *   1.  beforeAll seeds two dedicated books and runs direct matching synchronously.
 *   2.  Alice sees the proposed match and accepts it via the UI.
 *   3.  Bob sees the proposed match and accepts it via the UI.
 *   4.  Both users see the completed match in the "Accepted" tab.
 *   5.  A confirmed trade appears in each user's Trades list.
 *   6.  Alice opens the trade detail, enters a tracking number, and marks shipped.
 *   7.  Bob opens the trade detail, enters a tracking number, and marks shipped.
 *   8.  Alice marks her received book (Bob's package arrived).
 *   9.  Bob marks his received book (Alice's package arrived) → trade completes.
 *
 * Books used (ISBNs dedicated to this spec, not in the main seed_e2e catalog):
 *   Alice sends: "The Stranger" by Albert Camus       (9780679720201)
 *   Bob   sends: "Crime and Punishment" by Dostoevsky (9780140449136)
 *
 * Dashboard card assertions are interleaved at each stage to verify that
 * Proposed Matches, Active Trades, and Total Trades counts change correctly
 * throughout the lifecycle.
 */

import { test, expect } from '../../fixtures/index.js';
import { autoConfirmDialog } from '../../helpers/wait.js';
import { execFileSync } from 'child_process';
import { existsSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '..', '..', '..', '..');
const venvPython = path.join(repoRoot, '.venv', 'bin', 'python');
const pythonBin = existsSync(venvPython) ? venvPython : 'python3';

const ALICE_SENDS = 'The Stranger';      // Alice's outgoing book
const BOB_SENDS   = 'Crime and Punishment'; // Bob's outgoing book

// ── Dashboard helper ──────────────────────────────────────────────────────────

/** Wait for the loading gate to clear and return all dashboard card counts. */
async function getDashboardCounts(page) {
  await page.goto('/dashboard');
  await page.waitForLoadState('networkidle');
  const spinner = page.getByRole('status');
  if (await spinner.count() > 0) {
    await spinner.first().waitFor({ state: 'hidden', timeout: 15_000 });
  }
  await expect(page.locator('[class*="summaryCard"]').first()).toBeVisible({ timeout: 10_000 });

  const cardCount = async (labelText) => {
    const card = page.locator('[class*="summaryCard"]').filter({ hasText: labelText });
    const text = await card.locator('[class*="summaryValue"]').textContent();
    return parseInt(text.trim(), 10);
  };

  return {
    proposedMatches:   await cardCount('Proposed Matches'),
    pendingProposals:  await cardCount('Pending Proposals'),
    activeTrades:      await cardCount('Active Trades'),
    totalTrades:       await cardCount('Total Trades'),
    booksOffered:      await cardCount('Books Offered'),
    booksWanted:       await cardCount('Books Wanted'),
  };
}

// ── Shared state (populated by dashboard checkpoint tests) ────────────────────

// Baseline counts captured at the start of the flow, before any accept actions.
let aliceBaseline = null;
let bobBaseline   = null;

test.describe.serial('Full trade flow (match → accept → ship → receive)', () => {
  test.beforeAll(async () => {
    execFileSync(pythonBin, ['manage.py', 'e2e_seed_trade_flow'], {
      cwd: repoRoot,
      stdio: 'inherit',
    });
  });

  test.afterAll(async () => {
    execFileSync(pythonBin, ['manage.py', 'e2e_seed_trade_flow', '--teardown-only'], {
      cwd: repoRoot,
      stdio: 'inherit',
    });
  });

  // ── Dashboard checkpoint 1: baseline after seed ───────────────────────────
  // The seed creates one new proposed match (The Stranger ↔ Crime and Punishment).

  test('dashboard baseline: alice has ≥1 proposed match and ≥1 active trade after seed', async ({ alicePage: page }) => {
    aliceBaseline = await getDashboardCounts(page);

    // The seeded CONFIRMED trade must always be reflected in Active Trades
    expect(aliceBaseline.activeTrades, 'Active Trades should be ≥ 1 (seeded confirmed trade)').toBeGreaterThanOrEqual(1);

    // The seed just created a new proposed match for The Stranger
    expect(aliceBaseline.proposedMatches, 'Proposed Matches should be ≥ 1 after seed').toBeGreaterThanOrEqual(1);

    // All counts must be valid non-negative integers (regression: was undefined before fix)
    for (const [key, val] of Object.entries(aliceBaseline)) {
      expect(Number.isInteger(val), `alice "${key}" should be a valid integer`).toBe(true);
      expect(val, `alice "${key}" should be >= 0`).toBeGreaterThanOrEqual(0);
    }
  });

  test('dashboard baseline: bob has ≥1 proposed match and ≥1 active trade after seed', async ({ bobPage: page }) => {
    bobBaseline = await getDashboardCounts(page);

    expect(bobBaseline.activeTrades, 'Bob Active Trades should be ≥ 1').toBeGreaterThanOrEqual(1);
    expect(bobBaseline.proposedMatches, 'Bob Proposed Matches should be ≥ 1 after seed').toBeGreaterThanOrEqual(1);

    for (const [key, val] of Object.entries(bobBaseline)) {
      expect(Number.isInteger(val), `bob "${key}" should be a valid integer`).toBe(true);
      expect(val, `bob "${key}" should be >= 0`).toBeGreaterThanOrEqual(0);
    }
  });

  // ── Step 1: Alice accepts ──────────────────────────────────────────────────

  test('alice sees the proposed match and accepts it', async ({ alicePage: page }) => {
    await page.goto('/matches');
    await page.waitForLoadState('networkidle');

    // Default tab is "Proposed" — find the card containing Alice's book
    const matchCard = page.locator('[class*="matchCard"]').filter({ hasText: ALICE_SENDS });
    await expect(matchCard).toBeVisible({ timeout: 10_000 });

    // Accept button is present (alice hasn't accepted yet)
    await expect(matchCard.getByRole('button', { name: /accept match/i })).toBeVisible();
    await matchCard.getByRole('button', { name: /accept match/i }).click();

    // After accepting, the match stays in the Proposed tab (it's still PROPOSED,
    // waiting for Bob). The card switches from showing action buttons to showing
    // "Waiting for partner…".
    const updatedCard = page.locator('[class*="matchCard"]').filter({ hasText: ALICE_SENDS });
    await expect(updatedCard.getByText(/waiting for partner/i)).toBeVisible({ timeout: 8_000 });
  });

  // Dashboard check: after alice accepts (but not bob yet) the match is still
  // PROPOSED → Proposed Matches count is unchanged.
  test('dashboard: proposed matches unchanged while waiting for bob to accept', async ({ alicePage: page }) => {
    const counts = await getDashboardCounts(page);

    // Match is still PROPOSED (backend only moves to COMPLETED when both accept)
    // so alice's Proposed Matches count must still equal her baseline
    expect(counts.proposedMatches, 'Proposed Matches should be unchanged while waiting for partner')
      .toBe(aliceBaseline.proposedMatches);

    // Active trades unchanged — the trade hasn't been created yet
    expect(counts.activeTrades, 'Active Trades should be unchanged before trade is created')
      .toBe(aliceBaseline.activeTrades);
  });

  // ── Step 2: Bob accepts ───────────────────────────────────────────────────

  test('bob sees the proposed match and accepts it', async ({ bobPage: page }) => {
    await page.goto('/matches');
    await page.waitForLoadState('networkidle');

    // Bob's card shows his outgoing book (Crime and Punishment) in the Proposed tab
    const matchCard = page.locator('[class*="matchCard"]').filter({ hasText: BOB_SENDS });
    await expect(matchCard).toBeVisible({ timeout: 10_000 });

    await expect(matchCard.getByRole('button', { name: /accept match/i })).toBeVisible();
    await matchCard.getByRole('button', { name: /accept match/i }).click();

    // After both accept the match moves to COMPLETED → appears in the Accepted tab.
    // Switch to Accepted tab to confirm (Bob may still have other seeded proposed
    // matches so we can't assume the Proposed tab becomes empty).
    await page.getByRole('button', { name: /^accepted$/i }).click();
    await page.waitForLoadState('networkidle');

    const acceptedCard = page.locator('[class*="matchCard"]').filter({ hasText: BOB_SENDS });
    await expect(acceptedCard).toBeVisible({ timeout: 10_000 });
  });

  // ── Step 3: Completed match visible in "Accepted" tab ─────────────────────

  test('alice sees the completed match in the accepted tab', async ({ alicePage: page }) => {
    await page.goto('/matches');
    await page.getByRole('button', { name: /^accepted$/i }).click();
    await page.waitForLoadState('networkidle');

    const matchCard = page.locator('[class*="matchCard"]').filter({ hasText: ALICE_SENDS });
    await expect(matchCard).toBeVisible({ timeout: 10_000 });
  });

  test('bob sees the completed match in the accepted tab', async ({ bobPage: page }) => {
    await page.goto('/matches');
    await page.getByRole('button', { name: /^accepted$/i }).click();
    await page.waitForLoadState('networkidle');

    const matchCard = page.locator('[class*="matchCard"]').filter({ hasText: BOB_SENDS });
    await expect(matchCard).toBeVisible({ timeout: 10_000 });
  });

  // ── Step 4: Trade appears in both trades lists ────────────────────────────

  test('confirmed trade appears in alice trades list', async ({ alicePage: page }) => {
    await page.goto('/trades');
    await page.waitForLoadState('networkidle');

    const tradeCard = page.locator('[class*="tradeCard"]').filter({ hasText: ALICE_SENDS });
    await expect(tradeCard).toBeVisible({ timeout: 10_000 });
    await expect(tradeCard.getByText(/confirmed/i)).toBeVisible();
  });

  test('confirmed trade appears in bob trades list', async ({ bobPage: page }) => {
    await page.goto('/trades');
    await page.waitForLoadState('networkidle');

    const tradeCard = page.locator('[class*="tradeCard"]').filter({ hasText: BOB_SENDS });
    await expect(tradeCard).toBeVisible({ timeout: 10_000 });
    await expect(tradeCard.getByText(/confirmed/i)).toBeVisible();
  });

  // ── Dashboard checkpoint 2: after both accept, Active Trades +1 ──────────

  test('dashboard: alice active trades +1 and proposed matches -1 after both accept', async ({ alicePage: page }) => {
    const counts = await getDashboardCounts(page);

    // Both alice and bob accepted → new CONFIRMED trade created
    expect(counts.activeTrades, 'Active Trades should increase by 1 after trade is created')
      .toBe(aliceBaseline.activeTrades + 1);

    // The match moved from PROPOSED to COMPLETED → Proposed Matches decreased by 1
    expect(counts.proposedMatches, 'Proposed Matches should decrease by 1 after match is accepted by both')
      .toBe(aliceBaseline.proposedMatches - 1);
  });

  test('dashboard: bob active trades +1 and proposed matches -1 after both accept', async ({ bobPage: page }) => {
    const counts = await getDashboardCounts(page);

    expect(counts.activeTrades, 'Bob Active Trades should increase by 1 after trade is created')
      .toBe(bobBaseline.activeTrades + 1);

    expect(counts.proposedMatches, 'Bob Proposed Matches should decrease by 1 after match is accepted by both')
      .toBe(bobBaseline.proposedMatches - 1);
  });

  // ── Step 5: Alice marks her book shipped ──────────────────────────────────

  test('alice enters shipping details and marks her book shipped', async ({ alicePage: page }) => {
    await page.goto('/trades');
    await page.waitForLoadState('networkidle');

    await page.locator('[class*="tradeCard"]').filter({ hasText: ALICE_SENDS }).click();
    await expect(page).toHaveURL(/\/trades\/.+/);
    await expect(page.getByText(/trade #/i)).toBeVisible({ timeout: 8_000 });

    const shipBtn = page.getByRole('button', { name: /mark my book as shipped/i });
    await expect(shipBtn).toBeVisible({ timeout: 8_000 });
    await shipBtn.click();

    // Tracking form expands
    const trackingInput = page.getByLabel(/tracking number/i);
    await expect(trackingInput).toBeVisible({ timeout: 5_000 });
    await trackingInput.fill('1Z999AA10123456001');

    await page.getByRole('button', { name: /confirm shipped/i }).click();

    // Status badge updates to show "shipped" for the current user
    await expect(
      page.getByTestId('my-status-badge')
    ).toHaveText(/shipped/i, { timeout: 12_000 });
  });

  // Dashboard check: shipping doesn't change Active Trades count (trade is still active)
  test('dashboard: active trades unchanged while trade is in shipping state', async ({ alicePage: page }) => {
    const counts = await getDashboardCounts(page);

    // Trade status is now SHIPPING — still active
    expect(counts.activeTrades, 'Active Trades should stay the same while trade is shipping')
      .toBe(aliceBaseline.activeTrades + 1);
  });

  // ── Step 6: Bob marks his book shipped ───────────────────────────────────
  // The canMarkShipped fix ensures this button is present even when the trade
  // status is already "shipping" (because Alice shipped first).

  test('bob enters shipping details and marks his book shipped', async ({ bobPage: page }) => {
    await page.goto('/trades');
    await page.waitForLoadState('networkidle');

    await page.locator('[class*="tradeCard"]').filter({ hasText: BOB_SENDS }).click();
    await expect(page).toHaveURL(/\/trades\/.+/);
    await expect(page.getByText(/trade #/i)).toBeVisible({ timeout: 8_000 });

    const shipBtn = page.getByRole('button', { name: /mark my book as shipped/i });
    await expect(shipBtn).toBeVisible({ timeout: 8_000 });
    await shipBtn.click();

    const trackingInput = page.getByLabel(/tracking number/i);
    await expect(trackingInput).toBeVisible({ timeout: 5_000 });
    await trackingInput.fill('1Z999AA10123456002');

    await page.getByRole('button', { name: /confirm shipped/i }).click();

    await expect(
      page.getByTestId('partner-status-badge')
    ).toHaveText(/shipped/i, { timeout: 12_000 });
  });

  // ── Step 7: Alice marks book received ────────────────────────────────────

  test('alice marks the book she received', async ({ alicePage: page }) => {
    await page.goto('/trades');
    await page.waitForLoadState('networkidle');

    await page.locator('[class*="tradeCard"]').filter({ hasText: ALICE_SENDS }).click();
    await expect(page).toHaveURL(/\/trades\/.+/);
    await expect(page.getByText(/trade #/i)).toBeVisible({ timeout: 8_000 });

    // Dismiss the confirm() dialog automatically before clicking
    autoConfirmDialog(page);
    const receiveBtn = page.getByRole('button', { name: /mark book received/i });
    await expect(receiveBtn).toBeVisible({ timeout: 10_000 });
    await receiveBtn.click();

    // One side received → status badge updates
    await expect(
      page.getByTestId('my-status-badge')
    ).toHaveText(/received/i, { timeout: 12_000 });
  });

  // ── Step 8: Bob marks book received → trade completes ────────────────────

  test('bob marks the book he received and the trade completes', async ({ bobPage: page }) => {
    await page.goto('/trades');
    await page.waitForLoadState('networkidle');

    await page.locator('[class*="tradeCard"]').filter({ hasText: BOB_SENDS }).click();
    await expect(page).toHaveURL(/\/trades\/.+/);
    await expect(page.getByText(/trade #/i)).toBeVisible({ timeout: 8_000 });

    autoConfirmDialog(page);
    const receiveBtn = page.getByRole('button', { name: /mark book received/i });
    await expect(receiveBtn).toBeVisible({ timeout: 10_000 });
    await receiveBtn.click();

    // Both sides received → partner badge shows "received"
    await expect(
      page.getByTestId('partner-status-badge')
    ).toHaveText(/received/i, { timeout: 12_000 });
  });

  // ── Step 9: Trade appears in "Completed" tab ─────────────────────────────

  test('completed trade appears in alice completed tab', async ({ alicePage: page }) => {
    await page.goto('/trades');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /^completed$/i }).click();

    const tradeCard = page.locator('[class*="tradeCard"]').filter({ hasText: ALICE_SENDS });
    await expect(tradeCard).toBeVisible({ timeout: 10_000 });
    await expect(tradeCard.getByText(/completed/i)).toBeVisible();
  });

  // ── Dashboard checkpoint 3: after trade completes, Active Trades -1 ──────

  test('dashboard: alice active trades returns to baseline and total trades increases after completion', async ({ alicePage: page }) => {
    const counts = await getDashboardCounts(page);

    // The flow trade completed → Active Trades should be back to the original baseline
    expect(counts.activeTrades, 'Active Trades should return to baseline after trade completes')
      .toBe(aliceBaseline.activeTrades);

    // Total trades should have increased by at least 1 compared to baseline
    expect(counts.totalTrades, 'Total Trades should increase after trade completes')
      .toBeGreaterThan(aliceBaseline.totalTrades);
  });

  test('dashboard: bob active trades returns to baseline and total trades increases after completion', async ({ bobPage: page }) => {
    const counts = await getDashboardCounts(page);

    expect(counts.activeTrades, 'Bob Active Trades should return to baseline after trade completes')
      .toBe(bobBaseline.activeTrades);

    expect(counts.totalTrades, 'Bob Total Trades should increase after trade completes')
      .toBeGreaterThan(bobBaseline.totalTrades);
  });
});
