from datetime import datetime, timedelta, timezone
import types

import pytest

from apps.backups.models import BackupRecord
from apps.backups.services import retention_policy


class DummyStorage:
    def __init__(self):
        self.deleted = []

    def delete(self, file_name):
        self.deleted.append(file_name)


def patch_dbbackup_storage(monkeypatch, storage):
    fake_module = types.SimpleNamespace(get_storage=lambda: storage)
    monkeypatch.setitem(__import__("sys").modules, "dbbackup.storage", fake_module)


@pytest.mark.django_db
class TestRetentionPolicy:
    def _create_backup(self, file_name: str, created_at: datetime) -> BackupRecord:
        backup = BackupRecord.objects.create(
            status=BackupRecord.Status.SUCCESS,
            file_name=file_name,
            is_automatic=True,
        )
        BackupRecord.objects.filter(pk=backup.pk).update(created_at=created_at)
        backup.refresh_from_db()
        return backup

    def test_keeps_all_backups_newer_than_14_days(self, monkeypatch):
        now = datetime(2026, 4, 22, 12, 0, tzinfo=timezone.utc)
        storage = DummyStorage()

        monkeypatch.setattr(retention_policy.tz, "now", lambda: now)
        patch_dbbackup_storage(monkeypatch, storage)

        self._create_backup("daily-1", now - timedelta(days=1))
        self._create_backup("daily-7", now - timedelta(days=7))
        self._create_backup("daily-13", now - timedelta(days=13))

        retention_policy.apply_retention_policy()

        assert BackupRecord.objects.count() == 3
        assert storage.deleted == []

    def test_keeps_oldest_backup_per_week_for_14_to_60_days(self, monkeypatch):
        now = datetime(2026, 4, 22, 12, 0, tzinfo=timezone.utc)
        storage = DummyStorage()

        monkeypatch.setattr(retention_policy.tz, "now", lambda: now)
        patch_dbbackup_storage(monkeypatch, storage)

        # Same ISO week: keep oldest (earliest date)
        self._create_backup(
            "week14-oldest", datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)
        )
        self._create_backup(
            "week14-newer", datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc)
        )
        # Different ISO week: should be kept too
        self._create_backup(
            "week15-only", datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
        )

        retention_policy.apply_retention_policy()

        remaining = set(BackupRecord.objects.values_list("file_name", flat=True))
        assert remaining == {"week14-oldest", "week15-only"}
        assert storage.deleted == ["week14-newer"]

    def test_keeps_oldest_backup_per_month_for_60_to_365_days(self, monkeypatch):
        now = datetime(2026, 4, 22, 12, 0, tzinfo=timezone.utc)
        storage = DummyStorage()

        monkeypatch.setattr(retention_policy.tz, "now", lambda: now)
        patch_dbbackup_storage(monkeypatch, storage)

        # Same month bucket (January): keep oldest
        self._create_backup(
            "jan-oldest", datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc)
        )
        self._create_backup(
            "jan-newer", datetime(2026, 1, 20, 10, 0, tzinfo=timezone.utc)
        )
        # Different month bucket (February): keep this one
        self._create_backup(
            "feb-only", datetime(2026, 2, 10, 10, 0, tzinfo=timezone.utc)
        )

        retention_policy.apply_retention_policy()

        remaining = set(BackupRecord.objects.values_list("file_name", flat=True))
        assert remaining == {"jan-oldest", "feb-only"}
        assert storage.deleted == ["jan-newer"]

    def test_deletes_backups_older_than_or_equal_to_365_days(self, monkeypatch):
        now = datetime(2026, 4, 22, 12, 0, tzinfo=timezone.utc)
        storage = DummyStorage()

        monkeypatch.setattr(retention_policy.tz, "now", lambda: now)
        patch_dbbackup_storage(monkeypatch, storage)

        self._create_backup("too-old", now - timedelta(days=366))
        self._create_backup("boundary-365", now - timedelta(days=365))
        self._create_backup("monthly-364", now - timedelta(days=364))

        retention_policy.apply_retention_policy()

        remaining = set(BackupRecord.objects.values_list("file_name", flat=True))
        assert remaining == {"monthly-364"}
        assert set(storage.deleted) == {"too-old", "boundary-365"}
