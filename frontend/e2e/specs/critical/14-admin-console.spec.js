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

  const output = execFileSync(pythonBin, ['manage.py', 'shell', '-c', `${shellCode}\nprint(u.pk)`], {
    cwd: repoRoot,
    encoding: 'utf-8',
  }).trim();

  const lines = output.split('\n').map((line) => line.trim()).filter(Boolean);
  const userId = lines[lines.length - 1];
  if (!userId) {
    throw new Error('Failed to resolve admin user id for e2e test');
  }
  return userId;
}

async function firstExistingLocator(page, selectors) {
  for (const selector of selectors) {
    const locator = page.locator(selector).first();
    if (await locator.count()) {
      return locator;
    }
  }
  return null;
}

test.describe('Django Admin Console', () => {
  let adminUserId;

  test.beforeAll(async () => {
    adminUserId = ensureAdminUser();
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

    await page.goto(`${backendBase}/admin/accounts/user/${adminUserId}/change/`);

    const splitDate = await firstExistingLocator(page, [
      '#id_email_verified_at_0',
      '#id_email_verified_at_date',
      'input[name="email_verified_at_0"]',
      'input[name="email_verified_at_date"]',
    ]);
    const splitTime = await firstExistingLocator(page, [
      '#id_email_verified_at_1',
      '#id_email_verified_at_time',
      'input[name="email_verified_at_1"]',
      'input[name="email_verified_at_time"]',
    ]);
    const singleField = await firstExistingLocator(page, [
      '#id_email_verified_at',
      'input[name="email_verified_at"]',
    ]);

    if (splitDate && splitTime) {
      await expect(splitDate).toBeVisible();
      await expect(splitTime).toBeVisible();
    } else if (singleField) {
      await expect(singleField).toBeVisible();
    } else {
      throw new Error('Could not find email_verified_at admin input fields');
    }

    const nowButton = page.locator('#email-verified-at-now-btn');
    if (await nowButton.count()) {
      await nowButton.click();
    }

    if (splitDate && splitTime) {
      await splitDate.fill('2026-04-26');
      await splitTime.fill('12:34:56');
      await expect(splitDate).toHaveValue('2026-04-26');
      await expect(splitTime).toHaveValue('12:34:56');
    } else if (singleField) {
      await singleField.fill('2026-04-26 12:34:56');
      await expect(singleField).toHaveValue('2026-04-26 12:34:56');
    } else {
      throw new Error('No writable email_verified_at field found');
    }
  });
});
