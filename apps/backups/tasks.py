"""
Django-Q2 tasks for the backups app.
"""

import logging

logger = logging.getLogger(__name__)


def nightly_database_backup() -> None:
    """Scheduled nightly task — creates a BackupRecord and runs the backup."""
    from apps.backups.models import BackupRecord
    from apps.backups.services.backup_service import run_database_backup

    record = BackupRecord.objects.create(
        backup_type=BackupRecord.BackupType.DATABASE,
        is_automatic=True,
    )
    logger.info("Nightly database backup started, record=%s", record.pk)
    run_database_backup(str(record.pk))
    # Reload to get the latest status after the service updates it.
    record.refresh_from_db()
    logger.info("Nightly database backup finished, status=%s", record.status)


def apply_backup_retention_policy() -> None:
    """
    Scheduled task — enforce retention policy on old backups.

    Runs weekly or monthly to clean up backups older than 1 year,
    keeping only one per month for backups 60–365 days old, and
    one per week for 14–60 day old backups.
    """
    from apps.backups.services.retention_policy import apply_retention_policy

    logger.info("Applying backup retention policy...")
    apply_retention_policy()
    logger.info("Retention policy applied.")
