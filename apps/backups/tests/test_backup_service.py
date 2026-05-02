import pytest
from unittest.mock import patch, MagicMock
from apps.tests.factories import UserFactory, BackupRecordFactory
from apps.backups.models import BackupRecord
from apps.backups.services.backup_service import (
    run_database_backup, 
    trigger_manual_backup, 
    run_database_restore
)

@pytest.mark.django_db
class TestBackupService:
    @patch("dbbackup.storage.get_storage")
    @patch("apps.backups.services.backup_service.call_command")
    def test_run_database_backup_success(self, mock_call, mock_get_storage):
        record = BackupRecordFactory(status=BackupRecord.Status.PENDING)
        
        mock_storage = MagicMock()
        mock_storage.list_backups.side_effect = [
            ["old1.psql"], # before
            ["old1.psql", "new1.psql"] # after
        ]
        mock_storage.size.return_value = 1024
        mock_get_storage.return_value = mock_storage
        
        run_database_backup(str(record.pk))
        
        record.refresh_from_db()
        assert record.status == BackupRecord.Status.SUCCESS
        assert record.file_name == "new1.psql"
        assert record.file_size_bytes == 1024
        assert mock_call.called

    @patch("dbbackup.storage.get_storage")
    def test_run_database_backup_failure(self, mock_get_storage):
        record = BackupRecordFactory(status=BackupRecord.Status.PENDING)
        mock_get_storage.side_effect = Exception("Storage error")
        
        with pytest.raises(Exception):
            run_database_backup(str(record.pk))
            
        record.refresh_from_db()
        assert record.status == BackupRecord.Status.FAILED
        assert "Storage error" in record.error_message

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
