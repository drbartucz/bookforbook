/**
 * global-setup.js
 *
 * Runs once before the test suite begins:
 *   1. Re-seeds the database (python manage.py seed_e2e)
 *   2. Logs in each E2E user via the API and persists JWT+localStorage state
 *      so that individual specs can skip the login UI.
 *
 * Requires the backend to be running at DJANGO_BASE_URL (default localhost:8000).
 */
import { test as setup } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';
import { execFileSync } from 'child_process';
import { existsSync } from 'fs';
import { ALICE, BOB, CAROL, LIBRARY } from './constants.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const AUTH_DIR = path.join(__dirname, '.auth');

export const STORAGE_STATE = {
  alice: path.join(AUTH_DIR, 'alice.json'),
  bob: path.join(AUTH_DIR, 'bob.json'),
  carol: path.join(AUTH_DIR, 'carol.json'),
  library: path.join(AUTH_DIR, 'library.json'),
};

/**
 * Perform an API login and persist the browser storage state.
 * We navigate to the app first so that localStorage writes are scoped to the
 * correct origin.
 */
async function loginAndSave(page, baseURL, user, stateFile) {
  const apiBase = `${baseURL}/api/v1`;

  // 1. Obtain tokens from the backend
  const loginResponse = await page.request.post(`${apiBase}/auth/token/`, {
    data: { email: user.email, password: user.password },
  });

  if (!loginResponse.ok()) {
    const body = await loginResponse.text();
    throw new Error(
      `Failed to log in as ${user.email} (${loginResponse.status()}): ${body}`
    );
  }

  const { access, refresh } = await loginResponse.json();

  // 2. Fetch user profile
  const meResponse = await page.request.get(`${apiBase}/users/me/`, {
    headers: { Authorization: `Bearer ${access}` },
  });
  const meData = meResponse.ok() ? await meResponse.json() : null;

  // 3. Navigate to the app and write auth state to localStorage
  await page.goto(baseURL);
  await page.evaluate(
    ([accessToken, refreshToken, userData]) => {
      const authState = {
        state: { user: userData, accessToken, refreshToken },
        version: 0,
      };
      localStorage.setItem('bookforbook-auth', JSON.stringify(authState));
    },
    [access, refresh, meData]
  );

  // 4. Reload so React picks up the stored state
  await page.reload();

  // 5. Save the full storage state (cookies + localStorage)
  await page.context().storageState({ path: stateFile });
}

setup('authenticate all e2e users', async ({ page, baseURL }) => {
  // Re-seed the database so every run starts from a clean, known state.
  // The command is resolved relative to the repo root (two levels up from e2e/).
  const repoRoot = path.resolve(__dirname, '..', '..');

  // Prefer the project virtualenv python; fall back to python3 on PATH.
  const venvPython = path.join(repoRoot, '.venv', 'bin', 'python');
  const pythonBin = existsSync(venvPython) ? venvPython : 'python3';

  console.log(`[setup] seeding database (${pythonBin})…`);
  execFileSync(pythonBin, ['manage.py', 'seed_e2e', '--reset'], {
    cwd: repoRoot,
    stdio: 'inherit',
  });
  console.log('[setup] seed complete');

  const { mkdirSync } = await import('fs');
  mkdirSync(AUTH_DIR, { recursive: true });

  const users = [
    { user: ALICE, file: STORAGE_STATE.alice },
    { user: BOB, file: STORAGE_STATE.bob },
    { user: CAROL, file: STORAGE_STATE.carol },
    { user: LIBRARY, file: STORAGE_STATE.library },
  ];

  for (const { user, file } of users) {
    await loginAndSave(page, baseURL, user, file);
  }
});
