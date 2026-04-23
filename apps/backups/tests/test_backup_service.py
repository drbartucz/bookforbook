import types

import pytest

from apps.backups.models import BackupRecord
from apps.backups.services import backup_service
from apps.tests.factories import UserFactory


class DummyStorage:
    def __init__(self):
        self.after_backup = False

    def list_backups(self):
        if self.after_backup:
            return ["existing.sql.gz", "new-backup.sql.gz"]
        return ["existing.sql.gz"]

    def size(self, _filename):
        return len(b"backup-bytes")


def patch_dbbackup_storage(monkeypatch, storage):
    fake_module = types.SimpleNamespace(get_storage=lambda: storage)
    monkeypatch.setitem(__import__("sys").modules, "dbbackup.storage", fake_module)


@pytest.mark.django_db
class TestBackupService:
    def test_run_database_backup_marks_success_and_sets_filename_and_size(
        self, monkeypatch
    ):
        storage = DummyStorage()
        record = BackupRecord.objects.create(
            backup_type=BackupRecord.BackupType.DATABASE,
            status=BackupRecord.Status.PENDING,
            is_automatic=True,
        )

        def fake_call_command(*args, **kwargs):
            assert args == ("dbbackup", "--clean")
            assert kwargs == {"verbosity": 0}
            storage.after_backup = True

        patch_dbbackup_storage(monkeypatch, storage)
        monkeypatch.setattr(backup_service, "call_command", fake_call_command)

        backup_service.run_database_backup(str(record.pk))

        record.refresh_from_db()
        assert record.status == BackupRecord.Status.SUCCESS
        assert record.file_name == "new-backup.sql.gz"
        assert record.file_size_bytes == len(b"backup-bytes")
        assert record.completed_at is not None

    def test_run_database_backup_succeeds_even_if_size_lookup_fails(self, monkeypatch):
        storage = DummyStorage()
        record = BackupRecord.objects.create(
            backup_type=BackupRecord.BackupType.DATABASE,
            status=BackupRecord.Status.PENDING,
            is_automatic=True,
        )

        def fake_size(_filename):
            raise OSError("cannot read file size")

        def fake_call_command(*_args, **_kwargs):
            storage.after_backup = True

        storage.size = fake_size

        patch_dbbackup_storage(monkeypatch, storage)
        monkeypatch.setattr(backup_service, "call_command", fake_call_command)

        backup_service.run_database_backup(str(record.pk))

        record.refresh_from_db()
        assert record.status == BackupRecord.Status.SUCCESS
        assert record.file_name == "new-backup.sql.gz"
        assert record.file_size_bytes is None

    def test_run_database_backup_marks_failed_and_raises_on_command_error(
        self, monkeypatch
    ):
        storage = DummyStorage()
        record = BackupRecord.objects.create(
            backup_type=BackupRecord.BackupType.DATABASE,
            status=BackupRecord.Status.PENDING,
            is_automatic=True,
        )

        def fake_call_command(*_args, **_kwargs):
            raise RuntimeError("dbbackup failed")

        patch_dbbackup_storage(monkeypatch, storage)
        monkeypatch.setattr(backup_service, "call_command", fake_call_command)

        with pytest.raises(RuntimeError, match="dbbackup failed"):
            backup_service.run_database_backup(str(record.pk))

        record.refresh_from_db()
        assert record.status == BackupRecord.Status.FAILED
        assert "dbbackup failed" in record.error_message
        assert record.completed_at is not None

    def test_trigger_manual_backup_creates_record_and_dispatches_task(
        self, monkeypatch
    ):
        user = UserFactory()
        captured = {}

        def fake_async_task(task_name, record_id):
            captured["task_name"] = task_name
            captured["record_id"] = record_id

        monkeypatch.setattr("django_q.tasks.async_task", fake_async_task)

        record = backup_service.trigger_manual_backup(str(user.pk))

        assert record.status == BackupRecord.Status.PENDING
        assert record.is_automatic is False
        assert str(record.triggered_by_id) == str(user.pk)
        assert (
            captured["task_name"]
            == "apps.backups.services.backup_service.run_database_backup"
        )
        assert captured["record_id"] == str(record.pk)

    def test_run_database_restore_calls_dbrestore_command(self, monkeypatch):
        captured = {}

        def fake_call_command(*args):
            captured["args"] = args

        monkeypatch.setattr(backup_service, "call_command", fake_call_command)

        backup_service.run_database_restore("snapshot.sql.gz")

        assert captured["args"] == (
            "dbrestore",
            "--input-filename",
            "snapshot.sql.gz",
            "--noinput",
        )
