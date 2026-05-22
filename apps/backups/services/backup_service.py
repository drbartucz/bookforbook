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
import os

from django.conf import settings as django_settings
from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.utils import timezone
from dbbackup.storage import get_storage

from apps.notifications.email import send_email

logger = logging.getLogger(__name__)


def _ensure_filesystem_storage_path_exists(storage_backend) -> None:
    """Create local filesystem backup directory if it doesn't exist yet.

    Only acts on FileSystemStorage — S3-compatible backends use a location
    prefix, not a local path, so os.makedirs would create a spurious directory.
    """
    # Use storage_backend itself as the fallback so a bare (unwrapped)
    # FileSystemStorage is handled correctly alongside dbbackup's wrapper.
    underlying = getattr(storage_backend, "storage", storage_backend)
    if not isinstance(underlying, FileSystemStorage):
        return
    location = getattr(underlying, "location", None)
    if isinstance(location, str) and location:
        os.makedirs(location, exist_ok=True)


def _send_backup_notification(record) -> None:
    """Email the admin alert address based on BackupSettings switches."""
    from apps.backups.models import BackupRecord, BackupSettings

    try:
        backup_settings = BackupSettings.get()
        recipient = getattr(django_settings, "ADMIN_ACCOUNT_ALERT_EMAIL", "")
        if not recipient:
            return

        if (
            record.status == BackupRecord.Status.SUCCESS
            and backup_settings.email_on_success
        ):
            subject = "[BookForBook] Database backup succeeded"
            body = (
                f"Database backup completed successfully.\n\n"
                f"File: {record.file_name or '(unknown)'}\n"
                f"Size: {f'{record.file_size_mb} MB' if record.file_size_mb else '(unknown)'}\n"
                f"Storage: {record.storage_backend or '(unknown)'}\n"
                f"Duration: {f'{record.duration_seconds}s' if record.duration_seconds else '(unknown)'}\n"
                f"Completed: {record.completed_at.isoformat() if record.completed_at else '(unknown)'}"
            )
            send_email(recipient, subject, body)

        elif (
            record.status == BackupRecord.Status.FAILED
            and backup_settings.email_on_failure
        ):
            subject = "[BookForBook] Database backup FAILED"
            body = (
                f"Database backup FAILED.\n\n"
                f"Error: {record.error_message or '(no error message)'}\n"
                f"Storage: {record.storage_backend or '(unknown)'}\n"
                f"Failed at: {record.completed_at.isoformat() if record.completed_at else '(unknown)'}"
            )
            send_email(recipient, subject, body)

    except Exception:
        logger.exception("Failed to send backup notification for record %s", record.pk)


def run_database_backup(record_id: str) -> None:
    """Execute pg_dump via django-dbbackup and update *record_id*."""
    from apps.backups.models import BackupRecord

    record = BackupRecord.objects.get(pk=record_id)
    record.status = BackupRecord.Status.RUNNING
    record.save(update_fields=["status"])

    storage_backend_name = ""

    try:
        storage = get_storage()
        underlying = getattr(storage, "storage", storage)
        storage_backend_name = type(underlying).__name__
        logger.info("Using backup storage: %s", storage_backend_name)

        if isinstance(underlying, FileSystemStorage):
            logger.warning(
                "Backup is writing to local FILESYSTEM storage, not Backblaze B2. "
                "Set B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY, and B2_BUCKET_NAME "
                "environment variables to enable B2 cloud backup."
            )

        _ensure_filesystem_storage_path_exists(storage)
        before: set[str] = set(storage.list_backups())

        # --clean removes old backups beyond DBBACKUP_CLEANUP_KEEP.
        call_command("dbbackup", "--clean", verbosity=0)

        after: set[str] = set(storage.list_backups())
        new_files = after - before
        if not new_files:
            # The set difference is empty: dbbackup did not create a new file.
            # Do NOT fall back to an existing backup — that would silently
            # report a stale file as a fresh backup (false positive).
            raise RuntimeError(
                "Backup command completed but no new file was detected in storage. "
                "dbbackup may have failed silently or the before/after file lists "
                "are identical. Check dbbackup and storage configuration."
            )
        filename = new_files.pop()

        # Verify the file is actually reachable in storage.
        if filename:
            if not underlying.exists(filename):
                raise RuntimeError(
                    f"Backup file '{filename}' was listed but cannot be accessed "
                    "in storage. Check B2 credentials and bucket configuration."
                )
            logger.info("Backup file verified in storage: %s", filename)
        else:
            raise RuntimeError(
                "Backup command completed but no backup files found in storage. "
                "Verify B2 credentials and that the bucket exists."
            )

        # Best-effort size — only works for filesystem; S3 skips silently.
        file_size: int | None = None
        try:
            file_size = storage.size(filename)
        except Exception:
            pass

        record.status = BackupRecord.Status.SUCCESS
        record.file_name = filename
        record.file_size_bytes = file_size
        record.storage_backend = storage_backend_name
        record.completed_at = timezone.now()
        record.save(
            update_fields=[
                "status",
                "file_name",
                "file_size_bytes",
                "storage_backend",
                "completed_at",
            ]
        )
        logger.info("Database backup completed: %s", filename)
        _send_backup_notification(record)

    except Exception as exc:
        record.status = BackupRecord.Status.FAILED
        record.error_message = str(exc)[:2000]
        record.storage_backend = storage_backend_name
        record.completed_at = timezone.now()
        record.save(
            update_fields=["status", "error_message", "storage_backend", "completed_at"]
        )
        logger.exception("Database backup failed for record %s: %s", record_id, exc)
        _send_backup_notification(record)
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
