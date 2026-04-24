/**
 * helpers/wait.js
 *
 * Resilient wait helpers that account for React Query refetches,
 * toast notifications, and optimistic UI updates.
 */

/**
 * Wait for a toast notification containing the given text to appear.
 * Toasts auto-dismiss, so we only wait for visibility (not disappearance).
 */
export async function waitForToast(page, text) {
  await page.getByText(text).first().waitFor({ state: 'visible', timeout: 8_000 });
}

/**
 * Wait for the page loading spinner to disappear (React Query pending state).
 */
export async function waitForPageLoad(page) {
  // The LoadingSpinner component renders a role="status" element.
  const spinner = page.getByRole('status');
  const count = await spinner.count();
  if (count > 0) {
    await spinner.first().waitFor({ state: 'hidden', timeout: 15_000 });
  }
}

/**
 * Dismiss the browser confirm() dialog automatically with the given response.
 * Must be called BEFORE the action that triggers the dialog.
 */
export function autoConfirmDialog(page, accept = true) {
  page.once('dialog', (dialog) => {
    if (accept) {
      dialog.accept();
    } else {
      dialog.dismiss();
    }
  });
}

/**
 * Wait for a URL pattern to appear in the browser's location.
 */
export async function waitForNavigation(page, urlPattern, timeout = 15_000) {
  await page.waitForURL(urlPattern, { timeout });
}

/**
 * Retry a callback up to `attempts` times, waiting `delay` ms between tries.
 * Useful when asserting on eventually-consistent UI state.
 */
export async function retryExpect(fn, { attempts = 3, delay = 500 } = {}) {
  let lastError;
  for (let i = 0; i < attempts; i++) {
    try {
      await fn();
      return;
    } catch (err) {
      lastError = err;
      if (i < attempts - 1) {
        await new Promise((r) => setTimeout(r, delay));
      }
    }
  }
  throw lastError;
}
