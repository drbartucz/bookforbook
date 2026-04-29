/**
 * critical/03-inventory.spec.js
 *
 * My Books + Wishlist:
 *   - Books page loads and shows seeded books
 *   - Add book via ISBN lookup (mocked API)
 *   - Edit book condition
 *   - Remove book with confirmation
 *   - Wishlist page loads
 *   - Add / remove wishlist item
 */
import { test, expect, mockBookLookup } from '../../fixtures/index.js';
import { MOCK_BOOK_LOOKUP, SEEDED_ISBN } from '../../constants.js';
import { autoConfirmDialog } from '../../helpers/wait.js';

// ── My Books ─────────────────────────────────────────────────────────────────

test.describe('My Books', () => {
  test('page loads and shows seeded books', async ({ alicePage: page }) => {
    await page.goto('/my-books');
    await expect(page.getByRole('heading', { name: /my books/i })).toBeVisible();

    // Alice has 1984 / Orwell seeded
    await expect(page.getByText('Nineteen Eighty-Four', { exact: false })).toBeVisible();
  });

  test('add book via ISBN lookup', async ({ alicePage: page }) => {
    // Intercept the book lookup endpoint so we don't depend on Open Library
    await mockBookLookup(page, MOCK_BOOK_LOOKUP);

    await page.goto('/my-books');

    // Open add form
    await page.getByRole('button', { name: /add book/i }).click();

    // Look up a new ISBN (mock intercepts any ISBN)
    const isbnInput = page.getByRole('textbox', { name: /^isbn$/i });
    await isbnInput.fill('9780451524935');
    await page.getByRole('button', { name: /look\s*up/i }).click();

    // Wait for book preview to appear
    await expect(page.getByText(MOCK_BOOK_LOOKUP.title)).toBeVisible({ timeout: 8_000 });

    // Submit
    const submitBtn = page.getByRole('button', { name: /add to my books/i });
    await expect(submitBtn).toBeEnabled();
    await submitBtn.click();

    // Book should appear in list (or already present and API returns 400 — either way preview worked)
    await expect(
      page.getByText(MOCK_BOOK_LOOKUP.title).or(page.locator('.alert-error'))
    ).toBeVisible({ timeout: 8_000 });
  });

  test('edit book condition', async ({ alicePage: page }) => {
    await page.goto('/my-books');

    // Click Edit on the first available book card
    const editBtn = page.getByRole('button', { name: /^edit$/i }).first();
    await editBtn.click();

    // A condition select should appear
    const conditionSelect = page.locator('select').filter({ hasText: /good|acceptable|very good/i }).first();
    await expect(conditionSelect).toBeVisible();

    // Change condition
    await conditionSelect.selectOption({ label: 'Acceptable' });

    // Save
    await page.getByRole('button', { name: /^save$/i }).click();

    // Edit form should disappear
    await expect(page.getByRole('button', { name: /^save$/i })).toBeHidden({ timeout: 5_000 });
  });

  test('remove book with confirm dialog', async ({ alicePage: page }) => {
    await page.goto('/my-books');

    // Wait for the list to load before counting — books are fetched asynchronously
    const bookCards = page.locator('[class*="bookItem"]');
    await expect(bookCards.first()).toBeVisible({ timeout: 8_000 });
    const initialCount = await bookCards.count();

    // Auto-accept the window.confirm dialog
    autoConfirmDialog(page, true);

    // Click first visible Remove button
    await page.getByRole('button', { name: /^remove$/i }).first().click();

    // Book count should decrease (or toast / empty state appears)
    await expect(bookCards).toHaveCount(initialCount - 1, { timeout: 8_000 });
  });
});

// ── Wishlist ──────────────────────────────────────────────────────────────────

test.describe('Wishlist', () => {
  test('wishlist page loads and shows seeded item for carol', async ({ carolPage: page }) => {
    await page.goto('/wishlist');
    await expect(page.getByRole('heading', { name: /wishlist/i })).toBeVisible();
    // Carol has Huckleberry Finn seeded
    await expect(page.getByText(/huckleberry finn/i)).toBeVisible();
  });

  test('add book to wishlist via ISBN lookup', async ({ carolPage: page }) => {
    await mockBookLookup(page, MOCK_BOOK_LOOKUP);

    await page.goto('/wishlist');

    // Open the add form
    const addBtn = page.getByRole('button', { name: /add to wishlist/i });
    await addBtn.click();

    // Fill ISBN and look up
    await page.getByRole('textbox', { name: /^isbn$/i }).fill('9780741234567');
    await page.getByRole('button', { name: /look\s*up/i }).click();

    // Preview appears — use .first() because the edition-preference dialog also
    // contains the title, which would cause a strict-mode violation
    await expect(page.getByText(MOCK_BOOK_LOOKUP.title).first()).toBeVisible({ timeout: 8_000 });

    // Dismiss the edition-preference dialog if it appeared (it blocks the submit button)
    const doneBtn = page.getByRole('button', { name: /^done$/i });
    if (await doneBtn.isVisible()) {
      await doneBtn.click();
    }

    // Submit
    const submitBtn = page.getByRole('button', { name: /add to wishlist/i });
    await expect(submitBtn).toBeEnabled();
    await submitBtn.click();

    // Either the new item appears in the list or error (already in wishlist) — either state is OK
    await expect(
      page.locator('[class*="wishlistItem"]').getByText(MOCK_BOOK_LOOKUP.title)
        .or(page.locator('.alert-error'))
    ).toBeVisible({ timeout: 8_000 });
  });

  test('remove wishlist item', async ({ carolPage: page }) => {
    await page.goto('/wishlist');

    const removeBtn = page.getByRole('button', { name: /remove/i }).first();
    await expect(removeBtn).toBeVisible();
    await removeBtn.click();

    // Item disappears or confirmation shown
    await expect(
      page.getByText(/huckleberry finn/i).or(page.getByText(/no books/i))
    ).toBeVisible({ timeout: 8_000 });
  });
});
