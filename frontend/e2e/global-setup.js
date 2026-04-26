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
import { ALICE, BOB, CAROL, DAVE, LIBRARY } from './constants.js';
import { STORAGE_STATE, loginAndSave, ensureAuthDir } from './auth-state.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

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

  ensureAuthDir();

  const users = [
    { user: ALICE, file: STORAGE_STATE.alice },
    { user: BOB, file: STORAGE_STATE.bob },
    { user: CAROL, file: STORAGE_STATE.carol },
    { user: DAVE, file: STORAGE_STATE.dave },
    { user: LIBRARY, file: STORAGE_STATE.library },
  ];

  for (const { user, file } of users) {
    await loginAndSave(page, baseURL, user, file);
  }
});
