# Database Backups & Disaster Recovery

BookForBook uses automated nightly database backups to Backblaze B2, with admin-controlled triggers, restore capabilities, and a tiered retention policy.

## Overview

- **Automatic**: Nightly backups at 2 AM UTC via Django-Q2 scheduler
- **Manual**: Trigger on-demand from Django admin with one click
- **Restore**: One-click restore from admin (with safety confirmation)
- **Audit**: Every backup run is logged to `BackupRecord` with status, size, duration, and user (if manual)
- **Retention**: Custom tiered policy keeps backups for up to 1 year
- **Storage**: Backblaze B2 in production (~75% cheaper than AWS S3), local filesystem in development

## Architecture

### Models

**`BackupRecord`** (UUID PK, immutable audit log)
- `backup_type`: `database` (always)
- `status`: `pending` → `running` → `success` | `failed`
- `file_name`: Backup filename in storage
- `file_size_bytes`: Size of the backup file
- `error_message`: If status is `failed`
- `is_automatic`: True for scheduled, False for manual
- `triggered_by`: User who triggered (NULL for automatic)
- `created_at`, `completed_at`: Timestamps

### Storage

#### Development
- **Location**: `<project_root>/backups/` (local filesystem)
- **Setup**: Automatic; no configuration needed

#### Production
- **Provider**: Backblaze B2 (S3-compatible)
- **Endpoint**: `https://f000.backblazeb2.com`
- **Location**: `db-backups/` prefix in configured bucket
- **Configuration** (Railway env vars):
  ```
  B2_APPLICATION_KEY_ID=<your-key-id>
  B2_APPLICATION_KEY=<your-key>
  B2_BUCKET_NAME=<your-bucket>
  ```

### Tasks (Django-Q2)

| Task | Schedule | Purpose |
|------|----------|---------|
| `nightly_database_backup()` | Daily @ 2 AM UTC | Create backup, record result |
| `apply_backup_retention_policy()` | Weekly (Sundays @ 2 AM) | Enforce retention rules, delete old backups |

## Retention Policy

| Age | Frequency | Kept |
|-----|-----------|------|
| 0–14 days | Daily | ✓ All (14 backups max) |
| 14–60 days | Weekly | ✓ One per week (6–7 backups) |
| 60–365 days | Monthly | ✓ One per month (12 backups) |
| 1 year+ | — | ✗ Deleted |

**Total kept**: ~32–35 backups at any time, consuming ~32–350 GB (depends on DB size).

Example timeline:
- Today (April 22): backup kept (daily)
- 10 days ago: kept (daily)
- 30 days ago: kept (oldest of that week)
- 90 days ago: kept (oldest of that month)
- 400 days ago: deleted

## Admin Interface

### Backup List (`/admin/backups/backuprecord/`)

- **"Trigger Backup Now"** button (top of page): Queues a manual backup
  - Status updates to `pending` → `running` → `success` or `failed`
  - Refresh to see the result (usually completes within seconds)
- **Status badge**: Color-coded indicator (green=success, red=failed, blue=running)
- **Size**: File size in MB (if available)
- **Duration**: Backup completion time in seconds
- **Restore button**: Available only for successful backups
  - Leads to a confirmation page with warnings
  - Requires typing "CONFIRM" to proceed

### Restore Flow

1. Click **Restore** on any successful backup
2. Read the warnings carefully:
   - All current data will be overwritten
   - Only data from the backup time will remain
   - Users' sessions will be invalidated
3. Type exactly **CONFIRM** in the text box
4. Click **Restore Database**
5. **After restore completes**: Manually restart the web process on Railway
   - Go to Railway dashboard → Backups.app → Deployments
   - Redeploy or restart the service
   - Django will sync its in-memory state with the restored database

## Management Commands

### Manual backup (CLI)

```bash
# Queue a backup via Django shell
python manage.py shell
>>> from apps.backups.services.backup_service import trigger_manual_backup
>>> record = trigger_manual_backup(user_id=None)  # or user_id="<uuid>"
>>> print(record.pk)
```

### List backups (CLI)

```bash
python manage.py shell
>>> from apps.backups.models import BackupRecord
>>> BackupRecord.objects.order_by('-created_at')[:10]
```

## Cost Estimate

**Backblaze B2 pricing** (as of 2026):
- Storage: $0.006/GB/month
- Egress: $0.006/GB (or free if ≤1 GB/day)

**Example**: If your database is 10 GB:
- 35 backups × 10 GB = 350 GB stored
- Cost: ~$2.10/month storage + egress
- **Annual**: ~$30–50

Compare to AWS S3: Same scenario = $140–180/year. **Backblaze saves ~75%.**

## Troubleshooting

### Backup fails with "permission denied"

- **Dev**: Check that `<project_root>/backups/` exists and is writable
- **Prod**: Verify B2 credentials are correct (`B2_APPLICATION_KEY_ID`, `B2_APPLICATION_KEY`)

### Backup is slow

- Large databases (>500 MB) can take 1–5 minutes
- Normal for PostgreSQL's `pg_dump` to be I/O bound
- Monitor via the `BackupRecord` status and `duration_seconds`

### Restore is taking a long time

- `dbrestore` can take as long as `dbbackup`
- Do NOT interrupt; let it complete
- Monitor logs: `docker logs <container>` or Railway's log viewer

### Can't see recent backups

- Retention policy runs weekly; old backups aren't deleted until then
- Check `BackupRecord` list in admin; query logs for policy execution

## Security Notes

- **Backups contain sensitive data**: User addresses, email hashes, etc.
  - B2 bucket should NOT be public
  - Consider enabling B2's "Server-Side Encryption"
- **Address fields are encrypted at rest**: But backups are plaintext database dumps
- **Access control**: Only superusers can trigger/restore backups from admin
  - Consider further restricting to a backup operator role in the future

## What's NOT backed up

- Media files (book covers from Open Library, etc.) — these are immutable and can be re-fetched
- Static files — regenerated on deploy
- Cache — non-critical transient data

## Disaster Recovery Scenarios

### Scenario 1: Accidental Data Deletion
1. Find the most recent backup before the deletion in `/admin/backups/backuprecord/`
2. Click **Restore**
3. Confirm by typing "CONFIRM"
4. Restart the web process
5. The deleted data is restored to the state at backup time

### Scenario 2: Database Corruption
1. Same steps as Scenario 1
2. If the corruption happened recently, restore to an older backup
3. Accept loss of data between the backup time and now

### Scenario 3: Ransomware / Malicious Data Modification
1. Restore from the oldest clean backup you can identify
2. Investigate the compromise window
3. Audit access logs and consider rotating credentials

### Scenario 4: Backblaze B2 Outage
- Backups already in B2 are safe; Railway's own backups provide a secondary safety net
- If B2 is unavailable and you need to restore immediately, consider manually downloading a backup from the previous day's B2 snapshot (if available) or switching to local filesystem backups temporarily

## Future Enhancements

- [ ] Backup encryption (B2 server-side or client-side with django-cryptography)
- [ ] Media file backups to B2 (optional, for full disaster recovery)
- [ ] Email alerts on backup failure
- [ ] Backup integrity checks (verify restore before production use)
- [ ] Geographically replicated B2 buckets for multi-region safety
