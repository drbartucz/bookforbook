import pytest
from unittest.mock import patch

from config.settings.base import _find_pg_tool


@pytest.mark.unit
class TestFindPgTool:
    def test_found_on_path(self):
        with patch("config.settings.base.shutil.which", return_value="/usr/bin/pg_dump"):
            assert _find_pg_tool("pg_dump") == "/usr/bin/pg_dump"

    def test_debian_apt_fallback(self):
        # Matches /usr/lib/postgresql/14/bin/pg_dump (first existing version wins)
        target = "/usr/lib/postgresql/14/bin/pg_dump"
        with (
            patch("config.settings.base.shutil.which", return_value=None),
            patch("config.settings.base.os.path.isfile", side_effect=lambda p: p == target),
        ):
            assert _find_pg_tool("pg_dump") == target

    def test_nix_profile_fallback(self):
        target = "/root/.nix-profile/bin/pg_dump"
        with (
            patch("config.settings.base.shutil.which", return_value=None),
            patch("config.settings.base.os.path.isfile", side_effect=lambda p: p == target),
            patch("config.settings.base.glob.glob", return_value=[]),
        ):
            assert _find_pg_tool("pg_dump") == target

    def test_nix_store_glob_fallback(self):
        store_path = "/nix/store/abc123-postgresql-14/bin/pg_dump"
        with (
            patch("config.settings.base.shutil.which", return_value=None),
            patch("config.settings.base.os.path.isfile", return_value=False),
            patch("config.settings.base.glob.glob", return_value=[store_path]),
        ):
            assert _find_pg_tool("pg_dump") == store_path

    def test_nix_store_versioned_name_fallback(self):
        # Railway/Nixpacks may name the store entry 'postgresql_16' not 'postgresql'
        store_path = "/nix/store/xyz-postgresql_16-16.3/bin/pg_dump"
        def _glob(pattern):
            return [store_path] if "postgresql_" in pattern else []
        with (
            patch("config.settings.base.shutil.which", return_value=None),
            patch("config.settings.base.os.path.isfile", return_value=False),
            patch("config.settings.base.glob.glob", side_effect=_glob),
        ):
            assert _find_pg_tool("pg_dump") == store_path

    def test_bare_name_fallback_when_not_found(self):
        with (
            patch("config.settings.base.shutil.which", return_value=None),
            patch("config.settings.base.os.path.isfile", return_value=False),
            patch("config.settings.base.glob.glob", return_value=[]),
        ):
            assert _find_pg_tool("pg_dump") == "pg_dump"
