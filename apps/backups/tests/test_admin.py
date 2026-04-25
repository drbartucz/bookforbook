"""
Tests for BackupRecordAdmin custom views and display methods.

Uses Django's test client with a superuser to exercise the admin
trigger-backup and restore views without a real backup service.
"""

import pytest
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory
from django.utils import timezone

from apps.backups.admin import BackupRecordAdmin
from apps.backups.models import BackupRecord
from apps.tests.factories import UserFactory


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_superuser():
    user = UserFactory(email_verified=True)
    user.is_staff = True
    user.is_superuser = True
    user.save(update_fields=["is_staff", "is_superuser"])
    return user


def _make_admin():
    site = AdminSite()
    return BackupRecordAdmin(BackupRecord, site)


def _make_record(**kwargs):
    defaults = dict(
        backup_type=BackupRecord.BackupType.DATABASE,
        status=BackupRecord.Status.SUCCESS,
        file_name="backup_2026.dump",
        file_size_bytes=1024 * 1024 * 50,  # 50 MB
        is_automatic=False,
    )
    defaults.update(kwargs)
    return BackupRecord.objects.create(**defaults)


# ---------------------------------------------------------------------------
# Display column helpers
# ---------------------------------------------------------------------------


class TestDisplayMethods:
    def test_status_badge_success(self):
        admin = _make_admin()
        record = _make_record(status=BackupRecord.Status.SUCCESS)
        html = admin.status_badge(record)
        assert "Success" in html
        assert "#2e7d32" in html  # green

    def test_status_badge_failed(self):
        admin = _make_admin()
        record = _make_record(status=BackupRecord.Status.FAILED)
        html = admin.status_badge(record)
        assert "Failed" in html
        assert "#c62828" in html  # red

    def test_status_badge_pending(self):
        admin = _make_admin()
        record = _make_record(status=BackupRecord.Status.PENDING)
        html = admin.status_badge(record)
        assert "#888" in html

    def test_file_size_display_with_size(self):
        admin = _make_admin()
        record = _make_record(file_size_bytes=1024 * 1024 * 50)
        assert "MB" in admin.file_size_display(record)

    def test_file_size_display_without_size(self):
        admin = _make_admin()
        record = _make_record(file_size_bytes=None)
        assert admin.file_size_display(record) == "—"

    def test_duration_display_with_timestamps(self):
        admin = _make_admin()
        record = _make_record()
        record.completed_at = record.created_at + timedelta(seconds=42)
        assert "42" in admin.duration_display(record)

    def test_duration_display_without_completed_at(self):
        admin = _make_admin()
        record = _make_record()
        assert admin.duration_display(record) == "—"

    def test_restore_button_shows_link_for_success_record(self):
        admin = _make_admin()
        record = _make_record(status=BackupRecord.Status.SUCCESS, file_name="db.dump")
        html = admin.restore_button(record)
        assert "Restore" in html
        assert "href" in html

    def test_restore_button_dash_for_failed_record(self):
        admin = _make_admin()
        record = _make_record(status=BackupRecord.Status.FAILED)
        assert admin.restore_button(record) == "—"

    def test_restore_button_dash_for_success_without_filename(self):
        admin = _make_admin()
        record = _make_record(status=BackupRecord.Status.SUCCESS, file_name="")
        assert admin.restore_button(record) == "—"


# ---------------------------------------------------------------------------
# trigger_backup_view
# ---------------------------------------------------------------------------


class TestTriggerBackupView:
    def test_get_request_redirects_to_changelist(self, client):
        superuser = _make_superuser()
        client.force_login(superuser)
        resp = client.get("/admin/backups/backuprecord/trigger-backup/")
        assert resp.status_code == 302
        assert "backuprecord" in resp["Location"]

    def test_post_triggers_backup_and_redirects(self, client):
        superuser = _make_superuser()
        client.force_login(superuser)

        mock_record = MagicMock()
        mock_record.pk = "fake-uuid"

        with patch(
            "apps.backups.services.backup_service.trigger_manual_backup",
            return_value=mock_record,
        ) as mock_trigger:
            resp = client.post("/admin/backups/backuprecord/trigger-backup/")

        assert resp.status_code == 302
        mock_trigger.assert_called_once_with(user_id=str(superuser.pk))


# ---------------------------------------------------------------------------
# restore_view
# ---------------------------------------------------------------------------


class TestRestoreView:
    def test_get_renders_confirmation_page(self, client):
        superuser = _make_superuser()
        client.force_login(superuser)
        record = _make_record()

        resp = client.get(f"/admin/backups/backuprecord/{record.pk}/restore/")
        assert resp.status_code == 200
        assert b"CONFIRM" in resp.content or b"restore" in resp.content.lower()

    def test_post_with_confirm_executes_restore(self, client):
        superuser = _make_superuser()
        client.force_login(superuser)
        record = _make_record()

        with patch(
            "apps.backups.services.backup_service.run_database_restore",
        ) as mock_restore:
            resp = client.post(
                f"/admin/backups/backuprecord/{record.pk}/restore/",
                {"confirmation": "CONFIRM"},
            )

        assert resp.status_code == 302
        mock_restore.assert_called_once_with(record.file_name)

    def test_post_without_confirm_aborts_restore(self, client):
        superuser = _make_superuser()
        client.force_login(superuser)
        record = _make_record()

        with patch("apps.backups.services.backup_service.run_database_restore") as mock_restore:
            resp = client.post(
                f"/admin/backups/backuprecord/{record.pk}/restore/",
                {"confirmation": "wrong"},
            )

        assert resp.status_code == 302
        mock_restore.assert_not_called()

    def test_post_with_restore_exception_shows_error(self, client):
        superuser = _make_superuser()
        client.force_login(superuser)
        record = _make_record()

        with patch(
            "apps.backups.services.backup_service.run_database_restore",
            side_effect=Exception("disk full"),
        ):
            resp = client.post(
                f"/admin/backups/backuprecord/{record.pk}/restore/",
                {"confirmation": "CONFIRM"},
            )

        # Should redirect back to changelist (not crash)
        assert resp.status_code == 302

    def test_restore_view_404_for_unknown_pk(self, client):
        superuser = _make_superuser()
        client.force_login(superuser)
        import uuid
        resp = client.get(f"/admin/backups/backuprecord/{uuid.uuid4()}/restore/")
        assert resp.status_code == 404

    def test_restore_requires_admin_login(self, client):
        record = _make_record()
        resp = client.get(f"/admin/backups/backuprecord/{record.pk}/restore/")
        # Unauthenticated requests are redirected to the admin login page
        assert resp.status_code == 302
        assert "login" in resp["Location"]
