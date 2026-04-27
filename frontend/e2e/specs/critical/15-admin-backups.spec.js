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

function getPythonAndRepoRoot() {
  const repoRoot = path.resolve(__dirname, '..', '..', '..', '..');
  const venvPython = path.join(repoRoot, '.venv', 'bin', 'python');
  const pythonBin = existsSync(venvPython) ? venvPython : 'python3';
  return { repoRoot, pythonBin };
}

function ensureAdminUser() {
  const { repoRoot, pythonBin } = getPythonAndRepoRoot();
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
    'u.save()',
    "print('admin-ready')",
  ].join('\n');

  execFileSync(pythonBin, ['manage.py', 'shell', '-c', shellCode], {
    cwd: repoRoot,
    stdio: 'inherit',
  });
}

function createSuccessfulBackupRecord() {
  const { repoRoot, pythonBin } = getPythonAndRepoRoot();
  const shellCode = [
    'from apps.backups.models import BackupRecord',
    "r = BackupRecord.objects.create(",
    "  backup_type=BackupRecord.BackupType.DATABASE,",
    "  status=BackupRecord.Status.SUCCESS,",
    "  file_name='e2e-admin-backup.psql.bin',",
    "  file_size_bytes=1024,",
    "  is_automatic=False,",
    ")",
    'print(r.pk)',
  ].join('\n');

  const out = execFileSync(pythonBin, ['manage.py', 'shell', '-c', shellCode], {
    cwd: repoRoot,
    encoding: 'utf-8',
  }).trim();

  const lines = out.split('\n').map((line) => line.trim()).filter(Boolean);
  return lines[lines.length - 1];
}

async function loginAdmin(page) {
  const backendBase = getBackendBaseURL();

  await page.goto(`${backendBase}/admin/login/`);
  await page.locator('input[name="username"]').fill(ADMIN_EMAIL);
  await page.locator('input[name="password"]').fill(ADMIN_PASSWORD);
  await page.locator('input[type="submit"][value="Log in"]').click();

  await page.waitForLoadState('networkidle');
  if (page.url().includes('/admin/login/')) {
    await page.locator('input[name="username"]').fill(ADMIN_USERNAME);
    await page.locator('input[name="password"]').fill(ADMIN_PASSWORD);
    await page.locator('input[type="submit"][value="Log in"]').click();
    await page.waitForLoadState('networkidle');
  }

  if (page.url().includes('/admin/login/')) {
    const err = await page.locator('.errornote, .errorlist').first().textContent();
    throw new Error(`Admin login failed: ${err || 'unknown error'}`);
  }
}

test.describe('Django Admin Backups', () => {
  let backupRecordId;

  test.beforeAll(async () => {
    ensureAdminUser();
    backupRecordId = createSuccessfulBackupRecord();
  });

  test('backup changelist shows trigger button and can queue backup', async ({ page }) => {
    const backendBase = getBackendBaseURL();
    await loginAdmin(page);

    await page.goto(`${backendBase}/admin/backups/backuprecord/`);
    const triggerButton = page.getByRole('button', { name: /trigger backup now/i });
    await expect(triggerButton).toBeVisible();

    page.once('dialog', async (dialog) => {
      await dialog.accept();
    });
    await triggerButton.click();

    await expect(page).toHaveURL(new RegExp(`${backendBase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}/admin/backups/backuprecord/?`));
    await expect(page.getByText(/backup queued/i)).toBeVisible();
  });

  test('restore confirmation page renders for a successful backup record', async ({ page }) => {
    const backendBase = getBackendBaseURL();
    await loginAdmin(page);

    await page.goto(`${backendBase}/admin/backups/backuprecord/${backupRecordId}/restore/`);

    await expect(page.getByRole('heading', { name: /confirm database restore/i }).first()).toBeVisible();
    await expect(page.getByText(/destructive and irreversible/i)).toBeVisible();
    await expect(page.locator('input[name="confirmation"]')).toBeVisible();
    await expect(page.getByRole('button', { name: /restore database/i })).toBeVisible();
  });
});
