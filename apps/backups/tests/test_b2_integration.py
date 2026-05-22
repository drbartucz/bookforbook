"""
Live integration tests for Backblaze B2 storage connectivity.

These tests require a real B2 bucket and credentials
(B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET_NAME) and are
automatically skipped in the default development environment where
DBBACKUP_STORAGE is a local FileSystemStorage.

Run them explicitly with:
    DJANGO_SETTINGS_MODULE=config.settings.production pytest -m integration apps/backups/tests/test_b2_integration.py
"""

import io
import uuid

import pytest
from django.conf import settings


def _get_b2_underlying_storage():
    """Return the underlying Django storage backend, or skip if not S3."""
    from dbbackup.storage import get_storage

    storage_type = getattr(settings, "DBBACKUP_STORAGE", "")
    if "s3boto3" not in storage_type.lower():
        pytest.skip(
            "B2/S3 storage not configured. "
            "Set B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY, and B2_BUCKET_NAME "
            "and use DJANGO_SETTINGS_MODULE=config.settings.production to run this test."
        )
    storage = get_storage()
    return getattr(storage, "storage", storage)


@pytest.mark.integration
class TestB2StorageIntegration:
    """Smoke-tests for Backblaze B2 connectivity.

    Each test uploads a uniquely named file, verifies it, then deletes it.
    A try/finally ensures the bucket stays clean even on assertion failure.
    """

    def test_upload_verify_delete(self):
        """Create a small file, confirm it exists, read it back, then delete it."""
        underlying = _get_b2_underlying_storage()
        test_name = f"_integration-test-{uuid.uuid4().hex}.txt"
        content = b"bookforbook B2 connectivity check"

        try:
            # 1. Upload
            underlying.save(test_name, io.BytesIO(content))

            # 2. Verify the file is present immediately after upload
            assert underlying.exists(test_name), (
                f"File '{test_name}' was not found in B2 immediately after upload"
            )

            # 3. Read the file back and confirm the content is intact
            with underlying.open(test_name) as fh:
                read_back = fh.read()
            assert read_back == content, (
                f"Content mismatch: expected {content!r}, got {read_back!r}"
            )

            # 4. Delete
            underlying.delete(test_name)

            # 5. Confirm the file is gone
            assert not underlying.exists(test_name), (
                f"File '{test_name}' still present in B2 after delete"
            )

        except Exception:
            # Best-effort cleanup so the bucket stays tidy if the test fails.
            try:
                underlying.delete(test_name)
            except Exception:
                pass
            raise

    def test_list_backups_is_iterable(self):
        """Confirm list_backups() returns an iterable (even if empty) without error."""
        from dbbackup.storage import get_storage

        storage_type = getattr(settings, "DBBACKUP_STORAGE", "")
        if "s3boto3" not in storage_type.lower():
            pytest.skip("B2/S3 storage not configured")

        storage = get_storage()
        result = list(storage.list_backups())
        assert isinstance(result, list)
