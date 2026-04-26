"""
Tests for backups.tasks scheduled task functions.
"""

import pytest
from unittest.mock import MagicMock, patch

pytestmark = pytest.mark.django_db


class TestNightlyDatabaseBackup:
    def test_creates_record_and_runs_backup(self):
        from apps.backups.models import BackupRecord
        from apps.backups.tasks import nightly_database_backup

        with patch("apps.backups.services.backup_service.run_database_backup") as mock_backup:
            # run_database_backup is called with the record pk; it doesn't update
            # the record in this test, so we just check it was called.
            nightly_database_backup()

        assert mock_backup.call_count == 1
        record = BackupRecord.objects.get()
        assert record.backup_type == BackupRecord.BackupType.DATABASE
        assert record.is_automatic is True
        # The pk passed to run_database_backup should match the created record.
        mock_backup.assert_called_once_with(str(record.pk))

    def test_record_has_automatic_flag(self):
        from apps.backups.models import BackupRecord
        from apps.backups.tasks import nightly_database_backup

        with patch("apps.backups.services.backup_service.run_database_backup"):
            nightly_database_backup()

        assert BackupRecord.objects.filter(is_automatic=True).exists()


class TestApplyBackupRetentionPolicy:
    def test_delegates_to_retention_policy_service(self):
        from apps.backups.tasks import apply_backup_retention_policy

        with patch(
            "apps.backups.services.retention_policy.apply_retention_policy"
        ) as mock_apply:
            apply_backup_retention_policy()

        mock_apply.assert_called_once()

    def test_called_exactly_once(self):
        from apps.backups.tasks import apply_backup_retention_policy

        with patch(
            "apps.backups.services.retention_policy.apply_retention_policy"
        ) as mock_apply:
            apply_backup_retention_policy()
            apply_backup_retention_policy()

        assert mock_apply.call_count == 2
