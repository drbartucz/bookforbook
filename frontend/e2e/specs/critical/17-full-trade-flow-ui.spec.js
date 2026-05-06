/**
 * critical/17-full-trade-flow-ui.spec.js
 *
 * End-to-end test for the complete book-swap lifecycle driven entirely
 * through the browser UI — no API helpers are used to create UserBooks or
 * WishlistItems.
 *
 * Flow
 * ────
 *  beforeAll  Seed only the Book catalog entries so the backend does not
 *             contact Open Library when the UI submits ISBNs.
 *  1.  Alice  Adds "The Stranger" to her have-list via My Books UI.
 *  2.  Alice  Adds "Crime and Punishment" to her wishlist via Wishlist UI.
 *  3.  Bob    Adds "Crime and Punishment" to his have-list via My Books UI.
 *  4.  Bob    Adds "The Stranger" to his wishlist via Wishlist UI.
 *  5.  Setup  Trigger direct matching synchronously (management command).
 *  6.  Alice  Sees the proposed match, accepts it; match moves to Accepted tab.
 *  7.  Bob    Sees the proposed match, accepts it; match becomes COMPLETED.
 *  8.  Both   Match visible in Accepted tab.
 *  9.  Alice  Opens trade from Accepted match card and marks shipped.
 * 10.  Bob    Opens trade from Accepted match card and marks shipped.
 * 11.  Alice  Marks her received book.
 * 12.  Bob    Marks his received book → trade status becomes Completed.
 * 13.  Alice  Completed trade visible in Completed tab.
 *
 * Books
 * ─────
 *   Alice sends: "The Stranger" by Albert Camus       (ISBN 9780679720201)
 *   Bob   sends: "Crime and Punishment" by Dostoevsky (ISBN 9780140449136)
 */

import { test, expect, mockBookLookup } from '../../fixtures/index.js';
import { autoConfirmDialog } from '../../helpers/wait.js';
import { execFileSync } from 'child_process';
import { existsSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '..', '..', '..', '..');
const venvPython = path.join(repoRoot, '.venv', 'bin', 'python');
const pythonBin = existsSync(venvPython) ? venvPython : 'python3';

const ALICE_SENDS = 'The Stranger';
const BOB_SENDS   = 'Crime and Punishment';

const STRANGER_BOOK = {
  isbn_13: '9780679720201',
  isbn_10: null,
  title: 'The Stranger',
  authors: ['Albert Camus'],
  publish_year: 1942,
  physical_format: 'Paperback',
  cover_url: null,
};

const CRIME_BOOK = {
  isbn_13: '9780140449136',
  isbn_10: null,
  title: 'Crime and Punishment',
  authors: ['Fyodor Dostoevsky'],
  publish_year: 1866,
  physical_format: 'Paperback',
  cover_url: null,
};

// ── Helper: add a book to My Books via the UI ─────────────────────────────────

async function uiAddMyBook(page, bookData, condition = 'Good') {
  await mockBookLookup(page, bookData);
  await page.goto('/my-books');
  await page.waitForLoadState('networkidle');

  await page.getByRole('button', { name: /add book/i }).click();

  const isbnInput = page.getByRole('textbox', { name: /^isbn$/i });
  await expect(isbnInput).toBeVisible();
  await isbnInput.fill(bookData.isbn_13);
  await page.getByRole('button', { name: /look\s*up/i }).click();

  await expect(page.getByText(bookData.title)).toBeVisible({ timeout: 8_000 });

  // Select condition
  const conditionSelect = page.locator('select').filter({ hasText: /good|acceptable|very good/i }).first();
  await expect(conditionSelect).toBeVisible();
  await conditionSelect.selectOption({ label: condition });

  // Register a synchronous event listener to accept the "already own a copy?"
  // confirm dialog if alice has added this book previously (e.g. on a spec retry).
  autoConfirmDialog(page);
  await page.getByRole('button', { name: /add to my books/i }).click();

  // Wait for the add form to close — this confirms the API call completed
  // successfully, guaranteeing the UserBook row is committed before we proceed.
  await expect(page.locator('[class*="addForm"]')).toBeHidden({ timeout: 15_000 });

  // Book should appear in the list
  await expect(page.getByText(bookData.title)).toBeVisible({ timeout: 5_000 });
}

// ── Helper: add a book to the Wishlist via the UI ────────────────────────────

async function uiAddWishlist(page, bookData) {
  await mockBookLookup(page, bookData);
  await page.goto('/wishlist');
  await page.waitForLoadState('networkidle');

  await page.getByRole('button', { name: /add to wishlist/i }).click();

  const isbnInput = page.getByRole('textbox', { name: /^isbn$/i })
    .or(page.locator('input[placeholder*="isbn" i]').first());
  await expect(isbnInput).toBeVisible();
  await isbnInput.fill(bookData.isbn_13);
  await page.getByRole('button', { name: /look\s*up/i }).click();

  await expect(page.getByText(bookData.title).first()).toBeVisible({ timeout: 8_000 });

  // Edition preference can appear slightly after lookup; close it right before
  // submitting so the overlay cannot intercept the final click.
  const overlay = page.locator('[data-testid="edition-preference-overlay"]');
  const doneBtn = page.getByRole('button', { name: /^done$/i });
  if (await overlay.isVisible({ timeout: 5_000 }).catch(() => false)) {
    await doneBtn.click();
    await expect(overlay).toBeHidden({ timeout: 5_000 });
  }

  await page.getByRole('button', { name: /add to wishlist/i }).last().click();

  // Wait for the add form to close — confirms the API call completed
  // successfully and the WishlistItem row is committed before we proceed.
  await expect(page.locator('[class*="addForm"]')).toBeHidden({ timeout: 15_000 });

  await expect(page.getByText(bookData.title)).toBeVisible({ timeout: 5_000 });
}

// ── Helper: open a trade from Matches > Accepted via card action ─────────────

async function openTradeFromAcceptedMatch(page, bookTitle) {
  await page.goto('/matches');
  await page.getByRole('button', { name: /^accepted$/i }).click();
  await page.waitForLoadState('networkidle');

  const card = page.locator('[class*="matchCard"]').filter({ hasText: bookTitle });
  await expect(card).toBeVisible({ timeout: 10_000 });
  await card.getByRole('link', { name: /open trade/i }).click();

  await expect(page).toHaveURL(/\/trades\/.+/);
  await expect(page.getByText(/trade #/i)).toBeVisible({ timeout: 8_000 });
}

// ─────────────────────────────────────────────────────────────────────────────

test.describe.serial('Full trade flow — UI driven (match → accept → ship → receive)', () => {
  test.beforeAll(async () => {
    // Seed only the Book catalog entries. The UI steps below create the UserBooks
    // and WishlistItems through the browser, so we just need the Book rows to exist
    // so the backend can skip the Open Library network call.
    execFileSync(
      pythonBin,
      ['manage.py', 'e2e_seed_trade_flow', '--books-only'],
      { cwd: repoRoot, stdio: 'inherit' },
    );
  });

  test.afterAll(async () => {
    execFileSync(
      pythonBin,
      ['manage.py', 'e2e_seed_trade_flow', '--teardown-only'],
      { cwd: repoRoot, stdio: 'inherit' },
    );
  });

  // ── Steps 1–2: Alice adds her book and wishlist item ─────────────────────

  test('alice adds The Stranger to her have-list', async ({ alicePage: page }) => {
    await uiAddMyBook(page, STRANGER_BOOK, 'Good');
  });

  test('alice adds Crime and Punishment to her wishlist', async ({ alicePage: page }) => {
    await uiAddWishlist(page, CRIME_BOOK);
  });

  // ── Steps 3–4: Bob adds his book and wishlist item ────────────────────────

  test('bob adds Crime and Punishment to his have-list', async ({ bobPage: page }) => {
    await uiAddMyBook(page, CRIME_BOOK, 'Good');
  });

  test('bob adds The Stranger to his wishlist', async ({ bobPage: page }) => {
    await uiAddWishlist(page, STRANGER_BOOK);
  });

  // ── Step 5: Trigger matching synchronously ────────────────────────────────

  test('matching detects a proposed match between alice and bob', async () => {
    execFileSync(
      pythonBin,
      ['manage.py', 'e2e_seed_trade_flow', '--match-only'],
      { cwd: repoRoot, stdio: 'inherit' },
    );
  });

  // ── Step 6: Alice accepts ─────────────────────────────────────────────────

  test('alice sees the proposed match and accepts it', async ({ alicePage: page }) => {
    await page.goto('/matches');
    await page.waitForLoadState('networkidle');

    const matchCard = page.locator('[class*="matchCard"]').filter({ hasText: ALICE_SENDS });
    await expect(matchCard).toBeVisible({ timeout: 10_000 });

    await expect(matchCard.getByRole('button', { name: /accept match/i })).toBeVisible();
    await matchCard.getByRole('button', { name: /accept match/i }).click();

    // Alice's leg → ACCEPTED → match stays in Proposed tab (still waiting for Bob).
    // The card switches from action buttons to "Waiting for partner…".
    const updatedCard = page.locator('[class*="matchCard"]').filter({ hasText: ALICE_SENDS });
    await expect(updatedCard.getByText(/waiting for partner/i)).toBeVisible({ timeout: 8_000 });
  });

  // ── Step 7: Bob accepts ───────────────────────────────────────────────────

  test('bob sees the proposed match and accepts it', async ({ bobPage: page }) => {
    await page.goto('/matches');
    await page.waitForLoadState('networkidle');

    const matchCard = page.locator('[class*="matchCard"]').filter({ hasText: BOB_SENDS });
    await expect(matchCard).toBeVisible({ timeout: 10_000 });

    await expect(matchCard.getByRole('button', { name: /accept match/i })).toBeVisible();
    await matchCard.getByRole('button', { name: /accept match/i }).click();

    // Match → COMPLETED; switch to Accepted tab to verify
    await page.getByRole('button', { name: /^accepted$/i }).click();
    await page.waitForLoadState('networkidle');

    const acceptedCard = page.locator('[class*="matchCard"]').filter({ hasText: BOB_SENDS });
    await expect(acceptedCard).toBeVisible({ timeout: 10_000 });
  });

  // ── Step 8: Accepted tab verification ────────────────────────────────────

  test('alice sees the completed match in her accepted tab', async ({ alicePage: page }) => {
    await page.goto('/matches');
    await page.getByRole('button', { name: /^accepted$/i }).click();
    await page.waitForLoadState('networkidle');

    await expect(
      page.locator('[class*="matchCard"]').filter({ hasText: ALICE_SENDS })
    ).toBeVisible({ timeout: 10_000 });
  });

  test('bob sees the completed match in his accepted tab', async ({ bobPage: page }) => {
    await page.goto('/matches');
    await page.getByRole('button', { name: /^accepted$/i }).click();
    await page.waitForLoadState('networkidle');

    await expect(
      page.locator('[class*="matchCard"]').filter({ hasText: BOB_SENDS })
    ).toBeVisible({ timeout: 10_000 });
  });

  // ── Step 9: Alice opens trade from accepted match and marks shipped ───────

  test('alice opens trade detail and marks her book shipped', async ({ alicePage: page }) => {
    await openTradeFromAcceptedMatch(page, ALICE_SENDS);

    const shipBtn = page.getByRole('button', { name: /mark my book as shipped/i });
    await expect(shipBtn).toBeVisible({ timeout: 8_000 });
    await shipBtn.click();

    const trackingInput = page.getByLabel(/tracking number/i);
    await expect(trackingInput).toBeVisible({ timeout: 5_000 });
    await trackingInput.fill('1Z999AA20123456001');

    await page.getByRole('button', { name: /confirm shipped/i }).click();

    await expect(
      page.locator('.badge').filter({ hasText: /in transit|shipping/i }).first()
    ).toBeVisible({ timeout: 12_000 });
  });

  // ── Step 10: Bob opens trade from accepted match and marks shipped ───────

  test('bob opens trade detail and marks his book shipped', async ({ bobPage: page }) => {
    await openTradeFromAcceptedMatch(page, BOB_SENDS);

    const shipBtn = page.getByRole('button', { name: /mark my book as shipped/i });
    await expect(shipBtn).toBeVisible({ timeout: 8_000 });
    await shipBtn.click();

    const trackingInput = page.getByLabel(/tracking number/i);
    await expect(trackingInput).toBeVisible({ timeout: 5_000 });
    await trackingInput.fill('1Z999AA20123456002');

    await page.getByRole('button', { name: /confirm shipped/i }).click();

    await expect(
      page.locator('.badge').filter({ hasText: /in transit|shipping/i }).first()
    ).toBeVisible({ timeout: 12_000 });
  });

  // ── Step 11: Alice marks book received ────────────────────────────────────

  test('alice marks her received book', async ({ alicePage: page }) => {
    await openTradeFromAcceptedMatch(page, ALICE_SENDS);

    autoConfirmDialog(page);
    const receiveBtn = page.getByRole('button', { name: /mark book received/i });
    await expect(receiveBtn).toBeVisible({ timeout: 10_000 });
    await receiveBtn.click();

    await expect(
      page.locator('.badge').filter({ hasText: /one.*received|received/i }).first()
    ).toBeVisible({ timeout: 12_000 });
  });

  // ── Step 12: Bob marks book received → trade completes ────────────────────

  test('bob marks his received book and the trade completes', async ({ bobPage: page }) => {
    await openTradeFromAcceptedMatch(page, BOB_SENDS);

    autoConfirmDialog(page);
    const receiveBtn = page.getByRole('button', { name: /mark book received/i });
    await expect(receiveBtn).toBeVisible({ timeout: 10_000 });
    await receiveBtn.click();

    await expect(
      page.locator('.badge').filter({ hasText: /completed/i }).first()
    ).toBeVisible({ timeout: 12_000 });
  });

  // ── Step 13: Completed tab ─────────────────────────────────────────────────

  test('completed trade appears in alice completed tab', async ({ alicePage: page }) => {
    await page.goto('/trades');
    await page.waitForLoadState('networkidle');
    await page.getByRole('button', { name: /^completed$/i }).click();

    const tradeCard = page.locator('[class*="tradeCard"]').filter({ hasText: ALICE_SENDS });
    await expect(tradeCard).toBeVisible({ timeout: 10_000 });
    await expect(tradeCard.getByText(/completed/i)).toBeVisible();
  });
});
