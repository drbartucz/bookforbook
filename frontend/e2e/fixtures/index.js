/**
 * fixtures/index.js
 *
 * Custom Playwright test fixtures that layer authenticated browser contexts
 * on top of the base @playwright/test primitives.
 *
 * Usage:
 *   import { test, expect } from '../fixtures/index.js';
 *
 *   test('my test', async ({ alicePage }) => { ... });
 */
import { test as base } from '@playwright/test';
import { STORAGE_STATE } from '../global-setup.js';

/**
 * Intercept the Open Library book-lookup call and return deterministic data.
 * Keeps E2E tests independent of the external Open Library API.
 */
export async function mockBookLookup(page, bookData) {
  await page.route('**/api/v1/books/lookup/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(bookData),
    });
  });
}

export const test = base.extend({
  // ── Alice: address-verified individual ──────────────────────────────────
  alicePage: async ({ browser }, use) => {
    const ctx = await browser.newContext({ storageState: STORAGE_STATE.alice });
    const page = await ctx.newPage();
    await use(page);
    await ctx.close();
  },

  // ── Bob: address-verified individual (trading partner) ──────────────────
  bobPage: async ({ browser }, use) => {
    const ctx = await browser.newContext({ storageState: STORAGE_STATE.bob });
    const page = await ctx.newPage();
    await use(page);
    await ctx.close();
  },

  // ── Carol: individual WITHOUT address verification ───────────────────────
  carolPage: async ({ browser }, use) => {
    const ctx = await browser.newContext({ storageState: STORAGE_STATE.carol });
    const page = await ctx.newPage();
    await use(page);
    await ctx.close();
  },

  // ── Library: institution account ─────────────────────────────────────────
  libraryPage: async ({ browser }, use) => {
    const ctx = await browser.newContext({ storageState: STORAGE_STATE.library });
    const page = await ctx.newPage();
    await use(page);
    await ctx.close();
  },

  // ── Guest: unauthenticated context ───────────────────────────────────────
  guestPage: async ({ browser }, use) => {
    const ctx = await browser.newContext({ storageState: { cookies: [], origins: [] } });
    const page = await ctx.newPage();
    await use(page);
    await ctx.close();
  },
});

export { expect } from '@playwright/test';
