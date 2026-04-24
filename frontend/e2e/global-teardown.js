/**
 * global-teardown.js
 *
 * Runs once after all tests finish.  Currently a no-op placeholder;
 * add cleanup logic here if post-suite database resets are needed.
 */
import { test as teardown } from '@playwright/test';

teardown('cleanup after suite', async () => {
  // Nothing to do — seed_e2e can be re-run before the next suite.
});
