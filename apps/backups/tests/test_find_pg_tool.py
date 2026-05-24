import pytest
from unittest.mock import patch

from config.settings.base import _find_pg_tool


@pytest.mark.unit
class TestFindPgTool:
    def test_versioned_debian_path_preferred_over_path(self):
        # Versioned Debian path takes priority even when shutil.which finds something.
        target = "/usr/lib/postgresql/18/bin/pg_dump"
        with (
            patch("config.settings.base.os.path.isfile", side_effect=lambda p: p == target),
            patch("config.settings.base.shutil.which", return_value="/usr/bin/pg_dump"),
        ):
            assert _find_pg_tool("pg_dump") == target

    def test_higher_version_wins_when_multiple_exist(self):
        # When 17 and 16 both exist, 17 wins (range iterates high to low).
        available = {
            "/usr/lib/postgresql/17/bin/pg_dump",
            "/usr/lib/postgresql/16/bin/pg_dump",
        }
        with patch("config.settings.base.os.path.isfile", side_effect=lambda p: p in available):
            assert _find_pg_tool("pg_dump") == "/usr/lib/postgresql/17/bin/pg_dump"

    def test_found_on_path_when_no_versioned_binary(self):
        # Falls back to PATH when no versioned Debian binary is present.
        with (
            patch("config.settings.base.os.path.isfile", return_value=False),
            patch("config.settings.base.shutil.which", return_value="/usr/bin/pg_dump"),
        ):
            assert _find_pg_tool("pg_dump") == "/usr/bin/pg_dump"

    def test_debian_apt_path(self):
        # Versioned Debian path is found (highest matching version returned).
        target = "/usr/lib/postgresql/14/bin/pg_dump"
        with (
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

    def test_bash_login_shell_fallback(self):
        bash_path = "/nix/var/nix/profiles/default/bin/pg_dump"
        mock_result = type("R", (), {"returncode": 0, "stdout": bash_path + "\n"})()
        with (
            patch("config.settings.base.shutil.which", return_value=None),
            patch("config.settings.base.os.path.isfile", return_value=False),
            patch("config.settings.base.glob.glob", return_value=[]),
            patch("config.settings.base.subprocess.run", return_value=mock_result),
        ):
            assert _find_pg_tool("pg_dump") == bash_path

    def test_bare_name_fallback_when_not_found(self):
        mock_result = type("R", (), {"returncode": 1, "stdout": ""})()
        with (
            patch("config.settings.base.shutil.which", return_value=None),
            patch("config.settings.base.os.path.isfile", return_value=False),
            patch("config.settings.base.glob.glob", return_value=[]),
            patch("config.settings.base.subprocess.run", return_value=mock_result),
        ):
            assert _find_pg_tool("pg_dump") == "pg_dump"
