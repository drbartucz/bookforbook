"""
Backup and restore service layer.

run_database_backup() is called by the Django-Q2 task (and by the manual
admin trigger).  It wraps django-dbbackup's ``dbbackup`` management command,
captures the resulting filename, and updates the BackupRecord accordingly.

run_database_restore() wraps the ``dbrestore`` management command.  Because
restoring overwrites the entire database the function runs synchronously and
the caller (admin view) is responsible for showing the user an appropriate
warning.
"""

import logging

from django.core.management import call_command
from django.utils import timezone

logger = logging.getLogger(__name__)


def run_database_backup(record_id: str) -> None:
    """Execute pg_dump via django-dbbackup and update *record_id*."""
    from apps.backups.models import BackupRecord

    record = BackupRecord.objects.get(pk=record_id)
    record.status = BackupRecord.Status.RUNNING
    record.save(update_fields=["status"])

    try:
        from dbbackup.storage import get_storage

        storage = get_storage()
        before: set[str] = set(storage.list_backups())

        # --clean removes old backups beyond DBBACKUP_CLEANUP_KEEP.
        call_command("dbbackup", "--clean", verbosity=0)

        after: set[str] = set(storage.list_backups())
        new_files = after - before
        filename = new_files.pop() if new_files else ""

        # Best-effort size — only works for filesystem; S3 skips silently.
        file_size: int | None = None
        if filename:
            try:
                file_size = storage.size(filename)
            except Exception:
                pass

        record.status = BackupRecord.Status.SUCCESS
        record.file_name = filename
        record.file_size_bytes = file_size
        record.completed_at = timezone.now()
        record.save(
            update_fields=["status", "file_name", "file_size_bytes", "completed_at"]
        )
        logger.info("Database backup completed: %s", filename or "(unknown filename)")

    except Exception as exc:
        record.status = BackupRecord.Status.FAILED
        record.error_message = str(exc)[:2000]
        record.completed_at = timezone.now()
        record.save(update_fields=["status", "error_message", "completed_at"])
        logger.exception("Database backup failed for record %s: %s", record_id, exc)
        raise


def trigger_manual_backup(user_id: str | None = None) -> "BackupRecord":  # type: ignore[name-defined]  # noqa: F821
    """Create a BackupRecord and dispatch it to the Django-Q2 worker."""
    from django_q.tasks import async_task

    from apps.backups.models import BackupRecord

    record = BackupRecord.objects.create(
        backup_type=BackupRecord.BackupType.DATABASE,
        is_automatic=False,
        triggered_by_id=user_id,
    )
    async_task(
        "apps.backups.services.backup_service.run_database_backup",
        str(record.pk),
    )
    return record


def run_database_restore(filename: str) -> None:
    """
    Restore the database from *filename* using django-dbbackup.

    WARNING: This overwrites the entire database.  Any changes made after the
    backup was taken will be lost.  The web process should be restarted after
    this completes so Django's in-memory state is consistent with the restored
    data.
    """
    logger.warning("Starting database restore from file: %s", filename)
    call_command("dbrestore", "--input-filename", filename, "--noinput")
    logger.warning("Database restore completed from file: %s", filename)
