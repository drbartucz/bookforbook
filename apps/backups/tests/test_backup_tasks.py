import pytest
from unittest.mock import patch, MagicMock
from apps.backups.tasks import nightly_database_backup, apply_backup_retention_policy
from apps.backups.models import BackupRecord

@pytest.mark.django_db
class TestBackupTasks:
    @patch("apps.backups.services.backup_service.run_database_backup")
    def test_nightly_database_backup_task(self, mock_run):
        nightly_database_backup()
        assert BackupRecord.objects.filter(backup_type=BackupRecord.BackupType.DATABASE, is_automatic=True).exists()
        assert mock_run.called

    @patch("apps.backups.services.retention_policy.apply_retention_policy")
    def test_apply_backup_retention_policy_task(self, mock_apply):
        apply_backup_retention_policy()
        assert mock_apply.called
