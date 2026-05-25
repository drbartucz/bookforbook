import pytest
from unittest.mock import patch, MagicMock

from apps.tests.factories import UserFactory, BackupRecordFactory
from apps.backups.models import BackupRecord, BackupSettings
from apps.backups.services.backup_service import (
    run_database_backup,
    trigger_manual_backup,
    run_database_restore,
)


def _make_mock_storage(before, after, size=1024):
    """Build a mock dbbackup storage object with a named underlying storage."""

    class FakeS3Storage:
        def exists(self, name):
            return name in after

        def delete(self, name):
            pass

        def size(self, name):
            return size

    mock_storage = MagicMock()
    mock_storage.storage = FakeS3Storage()
    mock_storage.list_backups.side_effect = [list(before), list(after)]
    mock_storage.size.return_value = size
    return mock_storage


@pytest.mark.django_db
class TestBackupService:
    @patch("apps.backups.services.backup_service.get_storage")
    @patch("apps.backups.services.backup_service.call_command")
    def test_run_database_backup_success(self, mock_call, mock_get_storage):
        record = BackupRecordFactory(status=BackupRecord.Status.PENDING)
        mock_get_storage.return_value = _make_mock_storage(
            before=["old1.psql"],
            after=["old1.psql", "new1.psql"],
        )

        run_database_backup(str(record.pk))

        record.refresh_from_db()
        assert record.status == BackupRecord.Status.SUCCESS
        assert record.file_name == "new1.psql"
        assert record.file_size_bytes == 1024
        assert record.storage_backend == "FakeS3Storage"
        assert mock_call.called

    @patch("apps.backups.services.backup_service.get_storage")
    @patch("apps.backups.services.backup_service.call_command")
    def test_b2_verification_raises_when_file_missing(self, mock_call, mock_get_storage):
        """If exists() returns False for the detected file, the backup fails."""
        record = BackupRecordFactory(status=BackupRecord.Status.PENDING)

        class FakeStorageMissingFile:
            def exists(self, name):
                return False  # file not actually reachable

        mock_storage = MagicMock()
        mock_storage.storage = FakeStorageMissingFile()
        mock_storage.list_backups.side_effect = [
            ["old1.psql"],
            ["old1.psql", "new1.psql"],
        ]
        mock_get_storage.return_value = mock_storage

        with pytest.raises(RuntimeError, match="cannot be accessed"):
            run_database_backup(str(record.pk))

        record.refresh_from_db()
        assert record.status == BackupRecord.Status.FAILED

    @patch("apps.backups.services.backup_service.get_storage")
    @patch("apps.backups.services.backup_service.call_command")
    def test_empty_diff_raises_not_false_positive(self, mock_call, mock_get_storage):
        """If before==after (no new file detected), raise rather than picking an old backup."""
        record = BackupRecordFactory(status=BackupRecord.Status.PENDING)
        existing = ["backup-2024-01-01.psql", "backup-2024-01-02.psql"]
        mock_get_storage.return_value = _make_mock_storage(
            before=existing,
            after=existing,  # diff is empty — dbbackup produced nothing new
        )

        with pytest.raises(RuntimeError, match="no new file was detected"):
            run_database_backup(str(record.pk))

        record.refresh_from_db()
        assert record.status == BackupRecord.Status.FAILED

    @patch("apps.backups.services.backup_service.get_storage")
    def test_run_database_backup_failure(self, mock_get_storage):
        record = BackupRecordFactory(status=BackupRecord.Status.PENDING)
        mock_get_storage.side_effect = Exception("Storage error")

        with pytest.raises(Exception):
            run_database_backup(str(record.pk))

        record.refresh_from_db()
        assert record.status == BackupRecord.Status.FAILED
        assert "Storage error" in record.error_message

    @patch("apps.backups.services.backup_service.get_storage")
    @patch("apps.backups.services.backup_service.call_command")
    @patch("apps.backups.services.backup_service.send_email")
    def test_email_sent_on_success_when_enabled(
        self, mock_send_email, mock_call, mock_get_storage
    ):
        BackupSettings.objects.update_or_create(
            pk=1, defaults={"email_on_success": True, "email_on_failure": False}
        )
        record = BackupRecordFactory(status=BackupRecord.Status.PENDING)
        mock_get_storage.return_value = _make_mock_storage(
            before=[], after=["backup.psql"]
        )

        with patch(
            "apps.backups.services.backup_service.django_settings"
        ) as mock_settings:
            mock_settings.ADMIN_ACCOUNT_ALERT_EMAIL = "admin@example.com"
            mock_settings.DEFAULT_FROM_EMAIL = "noreply@example.com"
            run_database_backup(str(record.pk))

        mock_send_email.assert_called_once()
        subject = mock_send_email.call_args[0][1]
        assert "succeeded" in subject

    @patch("apps.backups.services.backup_service.get_storage")
    @patch("apps.backups.services.backup_service.call_command")
    @patch("apps.backups.services.backup_service.send_email")
    def test_email_sent_on_failure_when_enabled(
        self, mock_send_email, mock_call, mock_get_storage
    ):
        BackupSettings.objects.update_or_create(
            pk=1, defaults={"email_on_success": False, "email_on_failure": True}
        )
        record = BackupRecordFactory(status=BackupRecord.Status.PENDING)
        mock_get_storage.side_effect = Exception("S3 connection refused")

        with patch(
            "apps.backups.services.backup_service.django_settings"
        ) as mock_settings:
            mock_settings.ADMIN_ACCOUNT_ALERT_EMAIL = "admin@example.com"
            mock_settings.DEFAULT_FROM_EMAIL = "noreply@example.com"
            with pytest.raises(Exception):
                run_database_backup(str(record.pk))

        mock_send_email.assert_called_once()
        subject = mock_send_email.call_args[0][1]
        assert "FAILED" in subject

    @patch("apps.backups.services.backup_service.get_storage")
    @patch("apps.backups.services.backup_service.call_command")
    @patch("apps.backups.services.backup_service.send_email")
    def test_no_email_when_switches_off(
        self, mock_send_email, mock_call, mock_get_storage
    ):
        BackupSettings.objects.update_or_create(
            pk=1, defaults={"email_on_success": False, "email_on_failure": False}
        )
        record = BackupRecordFactory(status=BackupRecord.Status.PENDING)
        mock_get_storage.return_value = _make_mock_storage(
            before=[], after=["backup.psql"]
        )

        run_database_backup(str(record.pk))

        mock_send_email.assert_not_called()

    @patch("django_q.tasks.async_task")
    def test_trigger_manual_backup(self, mock_async):
        user = UserFactory()
        record = trigger_manual_backup(user_id=str(user.pk))

        assert record.is_automatic is False
        assert record.triggered_by == user
        assert mock_async.called

    @patch("apps.backups.services.backup_service.call_command")
    def test_run_database_restore(self, mock_call):
        run_database_restore("test_backup.psql")
        mock_call.assert_called_once_with(
            "dbrestore", "--input-filename", "test_backup.psql", "--noinput"
        )
