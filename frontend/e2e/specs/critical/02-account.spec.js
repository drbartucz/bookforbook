/**
 * critical/02-account.spec.js
 *
 * Account settings page:
 *   - Profile fields pre-populated from backend
 *   - Address update and verify flow
 *   - Shipping address status badge
 *   - Delete account confirmation
 */
import { test, expect } from '../../fixtures/index.js';
import { ALICE } from '../../constants.js';

test.describe('Account Settings', () => {
  test('page loads with alice profile pre-populated', async ({ alicePage: page }) => {
    await page.goto('/account');
    await expect(page.getByRole('heading', { name: /account settings/i })).toBeVisible();

    // Profile info section
    await expect(page.getByText(ALICE.username, { exact: false })).toBeVisible();
    await expect(page.getByText(ALICE.email, { exact: false })).toBeVisible();

    // Address form pre-populated
    await expect(page.getByLabel(/full name/i)).not.toHaveValue('');
    await expect(page.getByLabel(/address line 1/i)).not.toHaveValue('');
  });

  test('alice shows verified address status badge', async ({ alicePage: page }) => {
    await page.goto('/account');
    await expect(page.getByText(/verified/i).first()).toBeVisible();
  });

  test('carol shows unverified address status', async ({ carolPage: page }) => {
    await page.goto('/account');
    await expect(page.getByText(/not verified/i)).toBeVisible();
  });

  test('address form accepts new values', async ({ alicePage: page }) => {
    await page.goto('/account');

    // Update the full name field to something different
    const fullNameInput = page.getByLabel(/full name/i);
    await fullNameInput.clear();
    await fullNameInput.fill('Alice Updated');

    // Submit — this calls USPS verify; in E2E we just check UI responds
    const submitBtn = page.getByRole('button', { name: /verify and save address/i });
    await expect(submitBtn).toBeVisible();
    await expect(submitBtn).toBeEnabled();
  });

  test('danger zone section visible', async ({ alicePage: page }) => {
    await page.goto('/account');
    await expect(page.getByRole('heading', { name: /danger zone/i })).toBeVisible();
    await expect(page.getByLabel(/confirm password/i)).toBeVisible();
  });

  test('delete account requires password', async ({ alicePage: page }) => {
    await page.goto('/account');

    // Click delete without entering password should show error
    const deleteForm = page.locator('form').filter({ has: page.getByLabel(/confirm password/i) });
    const deleteBtn = deleteForm.getByRole('button', { name: /delete account/i });
    await deleteBtn.click();

    await expect(page.getByText(/password is required/i)).toBeVisible();
  });

  test('library account shows institution fields', async ({ libraryPage: page }) => {
    await page.goto('/account');
    await expect(page.getByText(/institution/i, { exact: false })).toBeVisible();
  });
});
