import pytest
from unittest.mock import patch

from config.settings.base import _find_pg_tool


@pytest.mark.unit
class TestFindPgTool:
    def test_env_var_override_pg_dump(self, monkeypatch):
        monkeypatch.setenv("PG_DUMP_PATH", "/custom/bin/pg_dump")
        assert _find_pg_tool("pg_dump") == "/custom/bin/pg_dump"

    def test_env_var_override_pg_restore(self, monkeypatch):
        monkeypatch.setenv("PG_RESTORE_PATH", "/custom/bin/pg_restore")
        assert _find_pg_tool("pg_restore") == "/custom/bin/pg_restore"

    def test_found_on_path(self):
        # Debian versioned paths are checked first; mock isfile so none match,
        # then shutil.which provides the result.
        with (
            patch("config.settings.base.os.path.isfile", return_value=False),
            patch("config.settings.base.shutil.which", return_value="/usr/bin/pg_dump"),
        ):
            assert _find_pg_tool("pg_dump") == "/usr/bin/pg_dump"

    def test_debian_versioned_path_beats_which(self):
        # A versioned Debian binary (e.g. pg18) is preferred over a lower-version
        # binary that shutil.which might find on PATH.
        target = "/usr/lib/postgresql/18/bin/pg_dump"
        with (
            patch("config.settings.base.os.path.isfile", side_effect=lambda p: p == target),
            patch("config.settings.base.shutil.which", return_value="/usr/bin/pg_dump"),
        ):
            assert _find_pg_tool("pg_dump") == target

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
