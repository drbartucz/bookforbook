import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';
import { execFileSync } from 'child_process';
import { existsSync } from 'fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ADMIN_EMAIL = 'admin-e2e@example.com';
const ADMIN_USERNAME = 'admin_e2e';
const ADMIN_PASSWORD = 'AdminE2ePass1!';

function getBackendBaseURL() {
  return process.env.DJANGO_BASE_URL || 'http://localhost:8000';
}

function ensureAdminUser() {
  const repoRoot = path.resolve(__dirname, '..', '..', '..', '..');
  const venvPython = path.join(repoRoot, '.venv', 'bin', 'python');
  const pythonBin = existsSync(venvPython) ? venvPython : 'python3';

  const shellCode = [
    'from django.contrib.auth import get_user_model',
    'User = get_user_model()',
    `u, _ = User.objects.get_or_create(email=${JSON.stringify(ADMIN_EMAIL)}, defaults={`,
    `    'username': ${JSON.stringify(ADMIN_USERNAME)},`,
    "    'is_staff': True,",
    "    'is_superuser': True,",
    "    'is_active': True,",
    "    'email_verified': True,",
    '})',
    `u.username = ${JSON.stringify(ADMIN_USERNAME)}`,
    'u.is_staff = True',
    'u.is_superuser = True',
    'u.is_active = True',
    'u.email_verified = True',
    `u.set_password(${JSON.stringify(ADMIN_PASSWORD)})`,
    "u.save()",
    "print('admin-ready')",
  ].join('\n');

  execFileSync(pythonBin, ['manage.py', 'shell', '-c', shellCode], {
    cwd: repoRoot,
    stdio: 'inherit',
  });
}

test.describe('Django Admin Console', () => {
  test.beforeAll(async () => {
    ensureAdminUser();
  });

  test('admin login works and accounts user edit page has verification controls', async ({ page }) => {
    const backendBase = getBackendBaseURL();

    await page.goto(`${backendBase}/admin/login/`);
    await page.locator('input[name="username"]').fill(ADMIN_EMAIL);
    await page.locator('input[name="password"]').fill(ADMIN_PASSWORD);
    await page.locator('input[type="submit"][value="Log in"]').click();

    await page.waitForLoadState('networkidle');
    if (page.url().includes('/admin/login/')) {
      // Retry once with username in case admin auth is configured for username entry.
      await page.locator('input[name="username"]').fill(ADMIN_USERNAME);
      await page.locator('input[name="password"]').fill(ADMIN_PASSWORD);
      await page.locator('input[type="submit"][value="Log in"]').click();
      await page.waitForLoadState('networkidle');
    }

    if (page.url().includes('/admin/login/')) {
      const err = await page.locator('.errornote, .errorlist').first().textContent();
      throw new Error(`Admin login failed: ${err || 'unknown error'}`);
    }

    await expect(page.url()).toContain('/admin');

    await page.goto(`${backendBase}/admin/accounts/user/?q=${encodeURIComponent(ADMIN_EMAIL)}`);
    await page.getByRole('link', { name: ADMIN_EMAIL }).first().click();

    const splitDate = page.locator('#id_email_verified_at_0');
    const splitTime = page.locator('#id_email_verified_at_1');
    const singleField = page.locator('#id_email_verified_at');

    if (await splitDate.count()) {
      await expect(splitDate).toBeVisible();
      await expect(splitTime).toBeVisible();
    } else {
      await expect(singleField).toBeVisible();
    }

    const nowButton = page.locator('#email-verified-at-now-btn');
    if (await nowButton.count()) {
      await nowButton.click();
    }

    if (await splitDate.count()) {
      await splitDate.fill('2026-04-26');
      await splitTime.fill('12:34:56');
      await expect(splitDate).toHaveValue('2026-04-26');
      await expect(splitTime).toHaveValue('12:34:56');
    } else {
      await singleField.fill('2026-04-26 12:34:56');
      await expect(singleField).toHaveValue('2026-04-26 12:34:56');
    }
  });
});
