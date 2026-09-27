"""
HELIOS — Permission Manager Security Tests
=============================================
Tests path validation, command validation, and security boundaries.
The LLM is NEVER the security boundary — these tests verify the backend
PermissionManager enforces all access rules independently.
"""

import os
import sys
import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security.permissions import (
    validate_path,
    is_blocked_system_path,
    is_binary_file,
    PermissionManager,
    PermissionResult,
    BLOCKED_COMMANDS,
    PRIVILEGED_COMMANDS,
    DANGEROUS_PYTHON_FLAGS,
    DEFAULT_SYSTEM_ACCESS,
    MAX_FILE_SIZE_BYTES,
    HELIOS_DIR,
)


# ─── Path Validation Tests ──────────────────────────────────────────────────

class TestPathValidation:
    """Test the core path validation logic."""

    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.allowed = [self.test_dir]
        # Create some test files/dirs
        os.makedirs(os.path.join(self.test_dir, "subdir"), exist_ok=True)
        Path(os.path.join(self.test_dir, "test.py")).touch()
        Path(os.path.join(self.test_dir, "subdir", "nested.py")).touch()

    def test_exact_match(self):
        result = validate_path(self.test_dir, self.allowed)
        assert result.allowed is True

    def test_file_inside_allowed(self):
        result = validate_path(
            os.path.join(self.test_dir, "test.py"), self.allowed
        )
        assert result.allowed is True

    def test_nested_file_inside_allowed(self):
        result = validate_path(
            os.path.join(self.test_dir, "subdir", "nested.py"), self.allowed
        )
        assert result.allowed is True

    def test_traversal_dot_dot_slash(self):
        """../ traversal must be DENIED."""
        evil_path = os.path.join(self.test_dir, "..", "secret")
        result = validate_path(evil_path, self.allowed)
        assert result.allowed is False

    def test_traversal_dot_dot_backslash(self):
        """..\\ traversal must be DENIED."""
        evil_path = self.test_dir + "\\..\\Windows\\System32"
        result = validate_path(evil_path, self.allowed)
        assert result.allowed is False

    def test_absolute_path_outside(self):
        """Absolute path outside allowed directory must be DENIED."""
        result = validate_path("C:\\Windows\\System32\\config", self.allowed)
        assert result.allowed is False

    def test_different_drive_letter(self):
        """Different drive letter must be DENIED."""
        result = validate_path("D:\\SomeFolder\\file.txt", self.allowed)
        assert result.allowed is False

    def test_unc_path(self):
        """UNC paths must be DENIED."""
        result = validate_path("\\\\server\\share\\file.txt", self.allowed)
        assert result.allowed is False

    def test_case_insensitive_windows(self):
        """Windows is case-insensitive — same path different case should match."""
        upper_path = self.test_dir.upper()
        result = validate_path(
            os.path.join(upper_path, "test.py"), self.allowed
        )
        # On Windows, this should be allowed (case-insensitive)
        if os.name == "nt":
            assert result.allowed is True

    def test_empty_allowed_paths(self):
        result = validate_path(self.test_dir, [])
        assert result.allowed is False

    def test_invalid_path(self):
        result = validate_path("", self.allowed)
        # Empty string resolves to CWD — may or may not be inside allowed
        # Just verify it doesn't crash
        assert isinstance(result, PermissionResult)


# ─── Blocked System Paths ────────────────────────────────────────────────────

class TestBlockedSystemPaths:
    @pytest.mark.skipif(os.name != 'nt', reason="Windows specific path tests")
    def test_windows_directory(self):
        assert is_blocked_system_path("C:\\Windows\\System32") is True

    @pytest.mark.skipif(os.name != 'nt', reason="Windows specific path tests")
    def test_program_files(self):
        assert is_blocked_system_path("C:\\Program Files\\SomeApp") is True

    @pytest.mark.skipif(os.name != 'nt', reason="Windows specific path tests")
    def test_program_files_x86(self):
        assert is_blocked_system_path("C:\\Program Files (x86)\\SomeApp") is True

    @pytest.mark.skipif(os.name != 'nt', reason="Windows specific path tests")
    def test_recovery(self):
        assert is_blocked_system_path("C:\\Recovery\\something") is True

    @pytest.mark.skipif(os.name != 'posix', reason="POSIX specific path tests")
    def test_posix_system(self):
        assert is_blocked_system_path("/System/Library") is True

    @pytest.mark.skipif(os.name != 'posix', reason="POSIX specific path tests")
    def test_posix_etc(self):
        assert is_blocked_system_path("/etc/passwd") is True

    @pytest.mark.skipif(os.name != 'posix', reason="POSIX specific path tests")
    def test_posix_bin(self):
        assert is_blocked_system_path("/bin/bash") is True

    def test_normal_path(self):
        # We need a cross-platform normal path
        assert is_blocked_system_path(os.path.join(tempfile.gettempdir(), "test_file.txt")) is False


# ─── Binary File Detection ──────────────────────────────────────────────────

class TestBinaryDetection:
    def test_text_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Hello, world!")
            f.flush()
            assert is_binary_file(Path(f.name)) is False
        os.unlink(f.name)

    def test_binary_file(self):
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".bin", delete=False) as f:
            f.write(b"\x00\x01\x02\x03\x04")
            f.flush()
            assert is_binary_file(Path(f.name)) is True
        os.unlink(f.name)

    def test_nonexistent_file(self):
        assert is_binary_file(Path("nonexistent_file.xyz")) is True


# ─── Command Validation ─────────────────────────────────────────────────────

class TestCommandValidation:
    def test_blocked_commands_are_frozen(self):
        """Verify all dangerous commands are in the blocked set."""
        for cmd in ["powershell", "cmd", "bash", "rm", "del", "shutdown",
                     "format", "diskpart", "reg", "taskkill"]:
            assert cmd in BLOCKED_COMMANDS, f"{cmd} should be blocked"

    def test_privileged_commands_are_identified(self):
        """Verify privileged commands are identified."""
        for cmd in ["npm", "pip", "git", "node", "python"]:
            assert cmd in PRIVILEGED_COMMANDS, f"{cmd} should be privileged"

    def test_dangerous_python_flags(self):
        for flag in ["-c", "-m", "-i", "--interactive"]:
            assert flag in DANGEROUS_PYTHON_FLAGS


# ─── Permission Manager ─────────────────────────────────────────────────────

class TestPermissionManager:
    """Test PermissionManager with a mocked database."""

    def setup_method(self):
        self.pm = PermissionManager()
        self.test_dir = tempfile.mkdtemp()
        Path(os.path.join(self.test_dir, "script.py")).touch()

    @patch("security.permissions.get_db")
    def test_file_read_disabled(self, mock_db):
        """Reading should be denied when file_read is disabled."""
        access = {"file_read": {"enabled": False, "paths": []},
                  "file_write": {"enabled": False, "paths": []},
                  "directory_list": {"enabled": False, "paths": []},
                  "terminal": {"enabled": False, "commands": []}}
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"system_access": json.dumps(access)}
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        result = self.pm.can_read_file(1, "C:\\some\\file.txt")
        assert result.allowed is False
        assert "disabled" in result.reason.lower()

    @patch("security.permissions.get_db")
    def test_file_read_outside_allowed(self, mock_db):
        """Reading outside allowed paths should be denied."""
        access = {"file_read": {"enabled": True, "paths": [self.test_dir]},
                  "file_write": {"enabled": False, "paths": []},
                  "directory_list": {"enabled": False, "paths": []},
                  "terminal": {"enabled": False, "commands": []}}
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"system_access": json.dumps(access)}
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        result = self.pm.can_read_file(1, "C:\\Windows\\System32\\hosts")
        assert result.allowed is False

    @patch("security.permissions.get_db")
    def test_file_read_inside_allowed(self, mock_db):
        """Reading inside allowed paths should be approved."""
        access = {"file_read": {"enabled": True, "paths": [self.test_dir]},
                  "file_write": {"enabled": False, "paths": []},
                  "directory_list": {"enabled": False, "paths": []},
                  "terminal": {"enabled": False, "commands": []}}
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"system_access": json.dumps(access)}
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        result = self.pm.can_read_file(
            1, os.path.join(self.test_dir, "script.py")
        )
        assert result.allowed is True

    @patch("security.permissions.get_db")
    def test_terminal_blocked_command(self, mock_db):
        """Blocked commands must be denied regardless of user config."""
        access = {"file_read": {"enabled": True, "paths": [self.test_dir]},
                  "file_write": {"enabled": False, "paths": []},
                  "directory_list": {"enabled": True, "paths": [self.test_dir]},
                  "terminal": {"enabled": True, "commands": ["powershell"]}}
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"system_access": json.dumps(access)}
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        result = self.pm.can_execute(1, "powershell", [], self.test_dir)
        assert result.allowed is False
        assert "blocked" in result.reason.lower()

    @patch("security.permissions.get_db")
    def test_terminal_not_in_allowlist(self, mock_db):
        """Commands not in the user's allowlist should be denied."""
        access = {"file_read": {"enabled": True, "paths": [self.test_dir]},
                  "file_write": {"enabled": False, "paths": []},
                  "directory_list": {"enabled": True, "paths": [self.test_dir]},
                  "terminal": {"enabled": True, "commands": ["dir"]}}
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"system_access": json.dumps(access)}
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        result = self.pm.can_execute(1, "python", ["test.py"], self.test_dir)
        assert result.allowed is False
        assert "not in your allowed" in result.reason.lower()

    @patch("security.permissions.get_db")
    def test_python_c_flag_blocked(self, mock_db):
        """python -c should be blocked."""
        access = {"file_read": {"enabled": True, "paths": [self.test_dir]},
                  "file_write": {"enabled": False, "paths": []},
                  "directory_list": {"enabled": True, "paths": [self.test_dir]},
                  "terminal": {"enabled": True, "commands": ["python"]}}
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"system_access": json.dumps(access)}
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        result = self.pm.can_execute(
            1, "python", ["-c", "import os; os.system('rm -rf /')"],
            self.test_dir
        )
        assert result.allowed is False
        assert "blocked" in result.reason.lower() or "dangerous" in result.reason.lower()

    @patch("security.permissions.get_db")
    def test_python_m_flag_blocked(self, mock_db):
        """python -m should be blocked."""
        access = {"file_read": {"enabled": True, "paths": [self.test_dir]},
                  "file_write": {"enabled": False, "paths": []},
                  "directory_list": {"enabled": True, "paths": [self.test_dir]},
                  "terminal": {"enabled": True, "commands": ["python"]}}
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"system_access": json.dumps(access)}
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        result = self.pm.can_execute(
            1, "python", ["-m", "http.server"], self.test_dir
        )
        assert result.allowed is False

    @patch("security.permissions.get_db")
    def test_python_script_outside_allowed(self, mock_db):
        """python <script> where script is outside allowed paths should be denied."""
        access = {"file_read": {"enabled": True, "paths": [self.test_dir]},
                  "file_write": {"enabled": False, "paths": []},
                  "directory_list": {"enabled": True, "paths": [self.test_dir]},
                  "terminal": {"enabled": True, "commands": ["python"]}}
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"system_access": json.dumps(access)}
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        result = self.pm.can_execute(
            1, "python", ["C:\\Windows\\evil.py"], self.test_dir
        )
        assert result.allowed is False

    @patch("security.permissions.get_db")
    def test_cwd_outside_allowed(self, mock_db):
        """Working directory outside allowed paths should be denied."""
        access = {"file_read": {"enabled": True, "paths": [self.test_dir]},
                  "file_write": {"enabled": False, "paths": []},
                  "directory_list": {"enabled": True, "paths": [self.test_dir]},
                  "terminal": {"enabled": True, "commands": ["dir"]}}
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"system_access": json.dumps(access)}
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        result = self.pm.can_execute(
            1, "dir", [], "C:\\Windows\\System32"
        )
        assert result.allowed is False
        assert "not inside" in result.reason.lower()


# ─── Config Validation ───────────────────────────────────────────────────────

class TestConfigValidation:
    def setup_method(self):
        self.pm = PermissionManager()

    def test_valid_config(self):
        config = {
            "file_read": {"enabled": True, "paths": [tempfile.mkdtemp()]},
            "file_write": {"enabled": False, "paths": []},
            "directory_list": {"enabled": True, "paths": [tempfile.mkdtemp()]},
            "terminal": {"enabled": False, "commands": []}
        }
        is_valid, error = self.pm.validate_config(config)
        assert is_valid is True
        assert error is None

    def test_blocked_command_in_config(self):
        config = {
            "file_read": {"enabled": True, "paths": []},
            "file_write": {"enabled": False, "paths": []},
            "directory_list": {"enabled": True, "paths": []},
            "terminal": {"enabled": True, "commands": ["powershell"]}
        }
        is_valid, error = self.pm.validate_config(config)
        assert is_valid is False
        assert "blocked" in error.lower()

    def test_system_path_in_config(self):
        if os.name == 'nt':
            blocked_path = "C:\\Windows\\System32"
        else:
            blocked_path = "/System/Library"
            
        config = {
            "file_read": {"enabled": True, "paths": [blocked_path]},
            "file_write": {"enabled": False, "paths": []},
            "directory_list": {"enabled": True, "paths": []},
            "terminal": {"enabled": False, "commands": []}
        }
        is_valid, error = self.pm.validate_config(config)
        assert is_valid is False
        assert "system-critical" in error.lower()

    def test_missing_key(self):
        config = {
            "file_read": {"enabled": True, "paths": []},
            # missing file_write, directory_list, terminal
        }
        is_valid, error = self.pm.validate_config(config)
        assert is_valid is False

    def test_invalid_type(self):
        is_valid, error = self.pm.validate_config("not a dict")
        assert is_valid is False


# ─── Approval Manager ───────────────────────────────────────────────────────

class TestApprovalManager:
    def setup_method(self):
        self.pm = PermissionManager()
        self.am = self.pm.approval_manager

    def test_once_approval_consumed(self):
        self.am.grant_approval(1, "file_write", "/some/path", "once")
        assert self.am.has_session_approval(1, "file_write", "/some/path") is True
        # Second check should fail — once is consumed
        assert self.am.has_session_approval(1, "file_write", "/some/path") is False

    def test_session_approval_persistent(self):
        self.am.grant_approval(1, "file_write", "/some/path", "session")
        assert self.am.has_session_approval(1, "file_write", "/some/path") is True
        # Should still be there
        assert self.am.has_session_approval(1, "file_write", "/some/path") is True

    def test_clear_session(self):
        self.am.grant_approval(1, "file_write", "/some/path", "session")
        self.am.clear_session()
        assert self.am.has_session_approval(1, "file_write", "/some/path") is False

    def test_request_id_unique(self):
        id1 = self.am.generate_request_id()
        id2 = self.am.generate_request_id()
        assert id1 != id2


# ─── Protected System Zones ──────────────────────────────────────────────────

class TestProtectedSystemZones:
    def setup_method(self):
        self.pm = PermissionManager()
        self.test_dir = tempfile.mkdtemp()
        
        # Override the protected paths to be inside our test directory for isolation
        self.pm._resolved_protected_paths = [
            (Path(self.test_dir) / "core").resolve(strict=False), 
            (Path(self.test_dir) / "security").resolve(strict=False)
        ]
        
        # Create core and security dirs
        os.makedirs(os.path.join(self.test_dir, "core"), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "security"), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "skills"), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "core_backup"), exist_ok=True)

    def _mock_access(self, mock_db):
        access = {"file_write": {"enabled": True, "paths": [self.test_dir]}}
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"system_access": json.dumps(access)}
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

    @patch("security.permissions.get_db")
    def test_allowed_access(self, mock_db):
        self._mock_access(mock_db)
        result = self.pm.can_write_file(1, os.path.join(self.test_dir, "skills", "test.py"))
        assert result.allowed is True

    @patch("security.permissions.get_db")
    def test_direct_protected_access(self, mock_db):
        self._mock_access(mock_db)
        result = self.pm.can_write_file(1, os.path.join(self.test_dir, "security", "permissions.py"))
        assert result.allowed is False
        assert "protected HELIOS system zone" in result.reason

    @patch("security.permissions.get_db")
    def test_nested_protected_access(self, mock_db):
        self._mock_access(mock_db)
        result = self.pm.can_write_file(1, os.path.join(self.test_dir, "core", "subdirectory", "test.py"))
        assert result.allowed is False

    @patch("security.permissions.get_db")
    def test_prefix_collision(self, mock_db):
        self._mock_access(mock_db)
        result = self.pm.can_write_file(1, os.path.join(self.test_dir, "core_backup", "test.py"))
        assert result.allowed is True

    @patch("security.permissions.get_db")
    def test_traversal_into_protected(self, mock_db):
        self._mock_access(mock_db)
        # /test_dir/skills/../core/test.py -> /test_dir/core/test.py
        path = os.path.join(self.test_dir, "skills", "..", "core", "test.py")
        result = self.pm.can_write_file(1, path)
        assert result.allowed is False

    @patch("security.permissions.get_db")
    def test_other_mutations(self, mock_db):
        self._mock_access(mock_db)
        core_file = os.path.join(self.test_dir, "core", "test.py")
        skills_file = os.path.join(self.test_dir, "skills", "test.py")

        assert self.pm.can_delete_file(1, core_file).allowed is False
        assert self.pm.can_rename_file(1, core_file, skills_file).allowed is False
        assert self.pm.can_rename_file(1, skills_file, core_file).allowed is False
        assert self.pm.can_move_file(1, core_file, skills_file).allowed is False
        assert self.pm.can_copy_file(1, skills_file, core_file).allowed is False
        # Valid moves
        assert self.pm.can_rename_file(1, skills_file, os.path.join(self.test_dir, "skills", "test2.py")).allowed is True

    @patch("security.permissions.get_db")
    def test_symlink_traversal(self, mock_db):
        self._mock_access(mock_db)
        try:
            link_path = os.path.join(self.test_dir, "skills", "link_to_core")
            os.symlink(os.path.join(self.test_dir, "core"), link_path, target_is_directory=True)
            
            # Write to skills/link_to_core/test.py -> resolves to core/test.py
            # Testing symlinked parent directories
            path = os.path.join(link_path, "test.py")
            result = self.pm.can_write_file(1, path)
            assert result.allowed is False
        except OSError:
            pass  # Skip symlink test on systems that don't support it

    @patch("security.permissions.get_db")
    def test_nonexistent_destination_resolution(self, mock_db):
        self._mock_access(mock_db)
        # Explicitly testing Path.resolve() for nonexistent destination paths
        nonexistent = os.path.join(self.test_dir, "core", "doesnt_exist_yet.py")
        result = self.pm.can_write_file(1, nonexistent)
        assert result.allowed is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

