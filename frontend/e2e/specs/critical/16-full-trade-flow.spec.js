/**
 * critical/16-full-trade-flow.spec.js
 *
 * End-to-end test for the complete book-swap lifecycle:
 *
 *   1.  beforeAll seeds two dedicated books and runs direct matching synchronously.
 *   2.  Alice sees the pending match and accepts it via the UI.
 *   3.  Bob sees the pending match and accepts it via the UI.
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

test.describe.serial('Full trade flow (match → accept → ship → receive)', () => {
  test.beforeAll(async () => {
    execFileSync(pythonBin, ['manage.py', 'e2e_seed_trade_flow'], {
      cwd: repoRoot,
      stdio: 'inherit',
    });
  });

  // ── Step 1: Alice accepts ──────────────────────────────────────────────────

  test('alice sees the pending match and accepts it', async ({ alicePage: page }) => {
    await page.goto('/matches');
    await page.waitForLoadState('networkidle');

    // Default tab is "Pending" — find the card containing Alice's book
    const matchCard = page.locator('[class*="matchCard"]').filter({ hasText: ALICE_SENDS });
    await expect(matchCard).toBeVisible({ timeout: 10_000 });

    // Accept button is present (alice hasn't accepted yet)
    await expect(matchCard.getByRole('button', { name: /accept match/i })).toBeVisible();
    await matchCard.getByRole('button', { name: /accept match/i }).click();

    // Card transitions to "Waiting for partner…" — match is still pending for bob
    await expect(matchCard.getByText(/waiting for partner/i)).toBeVisible({ timeout: 10_000 });
  });

  // ── Step 2: Bob accepts ───────────────────────────────────────────────────

  test('bob sees the pending match and accepts it', async ({ bobPage: page }) => {
    await page.goto('/matches');
    await page.waitForLoadState('networkidle');

    // Bob's card shows his outgoing book (Crime and Punishment)
    const matchCard = page.locator('[class*="matchCard"]').filter({ hasText: BOB_SENDS });
    await expect(matchCard).toBeVisible({ timeout: 10_000 });

    await expect(matchCard.getByRole('button', { name: /accept match/i })).toBeVisible();
    await matchCard.getByRole('button', { name: /accept match/i }).click();

    // After both accept the match moves to COMPLETED → pending tab empties
    // (the card either disappears or the page shows "No pending matches")
    await expect(
      page.getByText(/no pending matches/i)
        .or(page.locator('[class*="matchCard"]').filter({ hasText: BOB_SENDS }).getByText(/accepted/i))
    ).toBeVisible({ timeout: 12_000 });
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

    // Status badge updates to "Books in Transit"
    await expect(
      page.locator('.badge').filter({ hasText: /in transit|shipping/i }).first()
    ).toBeVisible({ timeout: 12_000 });
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
      page.locator('.badge').filter({ hasText: /in transit|shipping/i }).first()
    ).toBeVisible({ timeout: 12_000 });
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
      page.locator('.badge').filter({ hasText: /one.*received|received/i }).first()
    ).toBeVisible({ timeout: 12_000 });
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

    // Both sides received → trade is now Completed
    await expect(
      page.locator('.badge').filter({ hasText: /completed/i }).first()
    ).toBeVisible({ timeout: 12_000 });
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
});
