import { test, expect } from './e2e/fixtures/index.js';

test('debug library donations', async ({ libraryPage: page }) => {
  await page.goto('/donations');
  await page.waitForLoadState('networkidle');

  await page.getByRole('button', { name: /received/i }).click();
  await page.waitForLoadState('networkidle');

  // Wait a bit
  await page.waitForTimeout(2000);

  // Get page content
  const cards = await page.locator('[class*="donationCard"]').count();
  console.log('Donation cards:', cards);
  
  const acceptBtns = await page.getByRole('button', { name: /accept donation/i }).count();
  console.log('Accept buttons:', acceptBtns);
  
  const declineBtns = await page.getByRole('button', { name: /decline/i }).count();
  console.log('Decline buttons:', declineBtns);
  
  const html = await page.locator('[class*="donationList"]').innerHTML();
  console.log('Donation list HTML (first 2000 chars):', html.substring(0, 2000));
  
  await expect(page.getByRole('button', { name: /accept donation/i }).first()).toBeVisible();
});
