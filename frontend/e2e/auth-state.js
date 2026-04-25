import path from 'path';
import { fileURLToPath } from 'url';
import { mkdirSync } from 'fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const AUTH_DIR = path.join(__dirname, '.auth');

export const STORAGE_STATE = {
  alice: path.join(AUTH_DIR, 'alice.json'),
  bob: path.join(AUTH_DIR, 'bob.json'),
  carol: path.join(AUTH_DIR, 'carol.json'),
  dave: path.join(AUTH_DIR, 'dave.json'),
  library: path.join(AUTH_DIR, 'library.json'),
};

function getBackendBaseURL() {
  return process.env.DJANGO_BASE_URL || 'http://localhost:8000';
}

export function ensureAuthDir() {
  mkdirSync(AUTH_DIR, { recursive: true });
}

/**
 * Perform an API login and persist browser storage state.
 * We navigate to the app first so localStorage writes are scoped to the app origin.
 */
export async function loginAndSave(page, appBaseURL, user, stateFile) {
  const apiBase = `${getBackendBaseURL()}/api/v1`;

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

  const meResponse = await page.request.get(`${apiBase}/users/me/`, {
    headers: { Authorization: `Bearer ${access}` },
  });
  const meData = meResponse.ok() ? await meResponse.json() : null;

  await page.goto(appBaseURL);
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

  await page.reload();
  await page.context().storageState({ path: stateFile });
}
