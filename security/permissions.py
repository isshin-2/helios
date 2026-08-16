"""
HELIOS — Permission Manager
============================
Single security authority for all sandboxed system access.
The LLM, classifier, router, skills, frontend, and API must NEVER
independently decide whether an operation is allowed. Everything goes
through PermissionManager.

Flow:
    LLM → Router → Skill → PermissionManager → ApprovalManager → OS/FS
"""

import json
import logging
import os
import uuid
from pathlib import Path
from typing import NamedTuple, Optional, List, Dict, Any

from db import get_db

logger = logging.getLogger(__name__)

# ─── Data Types ─────────────────────────────────────────────────────────────

class PermissionResult(NamedTuple):
    allowed: bool
    reason: str
    resolved_path: Optional[Path] = None


# ─── Default Permissions ────────────────────────────────────────────────────

HELIOS_DIR = str(Path(__file__).resolve().parent.parent)

DEFAULT_SYSTEM_ACCESS = {
    "file_read": {
        "enabled": True,
        "paths": [HELIOS_DIR]
    },
    "file_write": {
        "enabled": False,
        "paths": []
    },
    "directory_list": {
        "enabled": True,
        "paths": [HELIOS_DIR]
    },
    "terminal": {
        "enabled": False,
        "commands": []
    }
}

# ─── Hardcoded Security Rules ───────────────────────────────────────────────

# Commands that can NEVER be executed, regardless of user configuration
BLOCKED_COMMANDS = frozenset({
    "powershell", "pwsh", "cmd", "bash", "sh", "zsh", "csh", "ksh",
    "rm", "del", "rmdir", "rd",
    "format", "diskpart", "fdisk",
    "reg", "regedit",
    "shutdown", "reboot", "halt", "poweroff",
    "net", "netsh", "netstat",
    "schtasks", "at",
    "taskkill", "kill", "pkill", "killall",
    "mkfs", "dd", "chmod", "chown",
    "sudo", "su", "runas",
    "curl", "wget",  # network access
})

# Commands that are privileged — require approval even when allowed
PRIVILEGED_COMMANDS = frozenset({
    "npm", "npx", "pip", "pip3", "pipx",
    "git", "node", "python", "python3", "py",
    "cargo", "rustc", "gcc", "g++", "make", "cmake",
})

# Dangerous Python invocation patterns
DANGEROUS_PYTHON_FLAGS = frozenset({"-c", "-m", "-i", "--interactive"})

# System-critical paths that can never be added
if os.name == "nt":
    BLOCKED_PATH_PREFIXES = [
        "C:\\Windows",
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        "C:\\ProgramData",
        "C:\\Recovery",
        "C:\\$Recycle.Bin",
    ]
else:
    BLOCKED_PATH_PREFIXES = [
        "/System",
        "/etc",
        "/var",
        "/usr/sbin",
        "/usr/bin",
        "/bin",
        "/sbin",
    ]

# ─── File Reading Limits ────────────────────────────────────────────────────

MAX_FILE_SIZE_BYTES = 1 * 1024 * 1024   # 1 MB
MAX_OUTPUT_BYTES = 100 * 1024            # 100 KB for terminal output
MAX_COMMAND_LENGTH = 1024
TERMINAL_TIMEOUT = 30  # seconds

# ─── Directory Listing Limits ───────────────────────────────────────────────

MAX_DIR_DEPTH = 3
MAX_DIR_ENTRIES = 200


# ─── Path Validation ────────────────────────────────────────────────────────

def validate_path(requested: str, allowed_paths: List[str]) -> PermissionResult:
    """
    Resolve, canonicalize, and check containment of a requested path
    against the allowed paths list.

    Uses pathlib's resolve() for canonicalization and structural parent
    comparison — never string prefix matching.

    Handles: ../, ..\, absolute paths, different drive letters, UNC paths,
    case differences (Windows is case-insensitive), symlinks, junctions.
    """
    try:
        resolved = Path(requested).resolve(strict=False)
    except (OSError, ValueError) as e:
        return PermissionResult(False, f"Invalid path: {e}")

    # Check if the resolved path has escaped via symlink/junction
    # by comparing the resolved path string to the original
    # (resolve() follows symlinks, so if it leads outside, we catch it)
    for allowed in allowed_paths:
        try:
            allowed_resolved = Path(allowed).resolve(strict=False)
        except (OSError, ValueError):
            continue

        # Case-insensitive comparison on Windows
        resolved_lower = str(resolved).lower()
        allowed_lower = str(allowed_resolved).lower()

        if resolved_lower == allowed_lower:
            return PermissionResult(True, "Exact match with allowed path.", resolved)

        # Check if allowed_resolved is a parent of resolved
        # We compare lowered strings of all parents for case-insensitive matching
        resolved_parents_lower = [str(p).lower() for p in resolved.parents]
        if allowed_lower in resolved_parents_lower:
            return PermissionResult(True, f"Inside allowed directory: {allowed}", resolved)

    return PermissionResult(
        False,
        f"Path '{requested}' is not inside any approved location. "
        f"You can add it from Settings → System Access."
    )


def is_blocked_system_path(path_str: str) -> bool:
    """Check if a path falls under a system-critical location."""
    try:
        resolved = str(Path(path_str).resolve(strict=False)).lower()
    except (OSError, ValueError):
        return True  # If we can't resolve it, block it

    for prefix in BLOCKED_PATH_PREFIXES:
        if resolved.startswith(prefix.lower()):
            return True
    return False


def is_binary_file(filepath: Path, sample_size: int = 8192) -> bool:
    """Detect binary files by checking for null bytes in the first chunk."""
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(sample_size)
        return b"\x00" in chunk
    except (OSError, IOError):
        return True  # If we can't read it, treat as binary


# ─── Approval Manager ───────────────────────────────────────────────────────

class ApprovalManager:
    """
    Manages in-memory session approvals.
    
    - 'once' approvals are consumed after one use.
    - 'session' approvals persist until the session ends.
    - Neither modifies the database.
    """

    def __init__(self):
        # { (user_id, operation, target): scope }
        self._session_approvals: Dict[tuple, str] = {}
        # Pending approval futures: { request_id: asyncio.Future }
        self._pending: Dict[str, Any] = {}

    def generate_request_id(self) -> str:
        return str(uuid.uuid4())

    def has_session_approval(self, user_id: int, operation: str, target: str) -> bool:
        key = (user_id, operation, target)
        scope = self._session_approvals.get(key)
        if scope == "session":
            return True
        if scope == "once":
            # Consume once-approval
            del self._session_approvals[key]
            return True
        return False

    def grant_approval(self, user_id: int, operation: str, target: str, scope: str):
        key = (user_id, operation, target)
        self._session_approvals[key] = scope

    def register_pending(self, request_id: str, future):
        self._pending[request_id] = future

    def resolve_pending(self, request_id: str, approved: bool, scope: str):
        future = self._pending.pop(request_id, None)
        if future and not future.done():
            future.set_result({"approved": approved, "scope": scope})

    def clear_session(self):
        """Clear all session approvals (called on session end)."""
        self._session_approvals.clear()
        # Cancel any pending approvals
        for request_id, future in self._pending.items():
            if not future.done():
                future.set_result({"approved": False, "scope": "deny"})
        self._pending.clear()


# ─── Permission Manager ─────────────────────────────────────────────────────

class PermissionManager:
    """
    Single security authority for all HELIOS system access.
    Every filesystem and terminal operation MUST go through this class.
    """

    def __init__(self):
        self.approval_manager = ApprovalManager()

    def _get_user_access(self, user_id: int) -> Dict[str, Any]:
        """Load the user's system_access config from the database."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT system_access FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()

        if row and row["system_access"]:
            try:
                return json.loads(row["system_access"])
            except (json.JSONDecodeError, TypeError):
                pass
        return DEFAULT_SYSTEM_ACCESS.copy()

    def log_operation(self, user_id: int, tool: str, operation: str,
                      target: str, perm_result: str,
                      exec_result: str = None, error: str = None):
        """Write to the audit log table."""
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO audit_log 
                   (user_id, tool, operation, target, permission_result, execution_result, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, tool, operation, target, perm_result, exec_result, error)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    # ── Capability Checks ───────────────────────────────────────────────

    def can_read_file(self, user_id: int, path: str) -> PermissionResult:
        """Check if the user is allowed to read the specified file."""
        access = self._get_user_access(user_id)
        file_read = access.get("file_read", {})

        if not file_read.get("enabled", False):
            return PermissionResult(False, "File reading is disabled for your account.")

        allowed_paths = file_read.get("paths", [])
        result = validate_path(path, allowed_paths)

        self.log_operation(
            user_id, "file_reader", "read_file", path,
            "APPROVED" if result.allowed else "DENIED"
        )
        return result

    def can_write_file(self, user_id: int, path: str) -> PermissionResult:
        """Check if the user is allowed to write to the specified file."""
        access = self._get_user_access(user_id)
        file_write = access.get("file_write", {})

        if not file_write.get("enabled", False):
            return PermissionResult(False, "File writing is disabled. Enable it in Settings → System Access.")

        allowed_paths = file_write.get("paths", [])
        result = validate_path(path, allowed_paths)

        self.log_operation(
            user_id, "file_writer", "write_file", path,
            "APPROVED" if result.allowed else "DENIED"
        )
        return result

    def can_list_directory(self, user_id: int, path: str) -> PermissionResult:
        """Check if the user is allowed to list the specified directory."""
        access = self._get_user_access(user_id)
        dir_list = access.get("directory_list", {})

        if not dir_list.get("enabled", False):
            return PermissionResult(False, "Directory listing is disabled for your account.")

        allowed_paths = dir_list.get("paths", [])
        result = validate_path(path, allowed_paths)

        self.log_operation(
            user_id, "directory_lister", "list_directory", path,
            "APPROVED" if result.allowed else "DENIED"
        )
        return result

    def can_execute(self, user_id: int, command: str, args: List[str],
                    cwd: str) -> PermissionResult:
        """
        Check if the user is allowed to execute the specified command.
        
        Validates:
        1. Terminal is enabled
        2. Command is not in the hardcoded block list
        3. Command is in the user's allowed commands list
        4. Working directory is inside an allowed path
        5. For python: script path is validated, dangerous flags are blocked
        6. Privileged commands are flagged for approval
        """
        access = self._get_user_access(user_id)
        terminal = access.get("terminal", {})

        if not terminal.get("enabled", False):
            return PermissionResult(
                False,
                "Terminal execution is disabled. Enable it in Settings → System Access."
            )

        cmd_lower = command.lower().strip()

        # 1. Hardcoded block list — can NEVER be overridden
        if cmd_lower in BLOCKED_COMMANDS:
            self.log_operation(
                user_id, "terminal", "execute", f"{command} {' '.join(args)}",
                "DENIED (blocked command)"
            )
            return PermissionResult(
                False,
                f"'{command}' is permanently blocked for security reasons."
            )

        # 2. Check user's allowed commands
        allowed_commands = [c.lower() for c in terminal.get("commands", [])]
        if cmd_lower not in allowed_commands:
            self.log_operation(
                user_id, "terminal", "execute", f"{command} {' '.join(args)}",
                "DENIED (not in allowlist)"
            )
            return PermissionResult(
                False,
                f"'{command}' is not in your allowed command list. "
                f"Add it in Settings → System Access → Terminal."
            )

        # 3. Validate working directory
        all_paths = []
        for cap in ["file_read", "file_write", "directory_list"]:
            all_paths.extend(access.get(cap, {}).get("paths", []))
        all_paths = list(set(all_paths))

        cwd_result = validate_path(cwd, all_paths)
        if not cwd_result.allowed:
            self.log_operation(
                user_id, "terminal", "execute",
                f"{command} {' '.join(args)} (cwd: {cwd})",
                "DENIED (cwd outside allowed paths)"
            )
            return PermissionResult(
                False,
                f"Working directory '{cwd}' is not inside any approved location."
            )

        # 4. Python-specific validation
        if cmd_lower in ("python", "python3", "py"):
            result = self._validate_python_args(user_id, args, all_paths)
            if not result.allowed:
                return result

        # 5. Check command length
        full_cmd = f"{command} {' '.join(args)}"
        if len(full_cmd) > MAX_COMMAND_LENGTH:
            return PermissionResult(
                False,
                f"Command exceeds maximum length of {MAX_COMMAND_LENGTH} characters."
            )

        # 6. Check if privileged (needs approval, handled by caller)
        needs_approval = cmd_lower in PRIVILEGED_COMMANDS
        reason = "Command is allowed."
        if needs_approval:
            reason = "Command is allowed but requires approval (privileged tool)."

        self.log_operation(
            user_id, "terminal", "execute", full_cmd,
            "APPROVED (pending approval)" if needs_approval else "APPROVED"
        )
        return PermissionResult(True, reason, cwd_result.resolved_path)

    def _validate_python_args(self, user_id: int, args: List[str],
                              allowed_paths: List[str]) -> PermissionResult:
        """Validate Python invocation arguments."""
        if not args:
            return PermissionResult(
                False,
                "Python requires a script file argument (e.g., 'python test.py')."
            )

        first_arg = args[0]

        # Block dangerous flags: -c, -m, -i, --interactive
        if first_arg in DANGEROUS_PYTHON_FLAGS:
            self.log_operation(
                user_id, "terminal", "execute",
                f"python {' '.join(args)}",
                f"DENIED (dangerous flag: {first_arg})"
            )
            return PermissionResult(
                False,
                f"'python {first_arg}' is blocked because it can execute arbitrary code. "
                f"Use 'python <script.py>' instead."
            )

        # If first arg looks like a flag we don't recognize, block it
        if first_arg.startswith("-"):
            return PermissionResult(
                False,
                f"Unrecognized Python flag '{first_arg}'. Only script execution is allowed."
            )

        # Validate the script path
        script_result = validate_path(first_arg, allowed_paths)
        if not script_result.allowed:
            return PermissionResult(
                False,
                f"Script '{first_arg}' is not inside any approved location."
            )

        return PermissionResult(True, "Python script execution validated.")

    # ── Approval Helpers ────────────────────────────────────────────────

    def needs_approval(self, command: str) -> bool:
        """Check if a command requires user approval."""
        return command.lower().strip() in PRIVILEGED_COMMANDS

    # ── Configuration Validation ────────────────────────────────────────

    def validate_config(self, config: Dict[str, Any]) -> tuple:
        """
        Validate a system_access configuration before saving.
        Returns (is_valid, error_message).
        """
        required_keys = {"file_read", "file_write", "directory_list", "terminal"}
        if not isinstance(config, dict):
            return False, "Configuration must be a JSON object."

        for key in required_keys:
            if key not in config:
                return False, f"Missing required key: {key}"

            section = config[key]
            if not isinstance(section, dict):
                return False, f"'{key}' must be an object."

            if "enabled" not in section:
                return False, f"'{key}' must have an 'enabled' field."

            if key == "terminal":
                commands = section.get("commands", [])
                if not isinstance(commands, list):
                    return False, "'terminal.commands' must be an array."
                for cmd in commands:
                    if cmd.lower() in BLOCKED_COMMANDS:
                        return False, f"Command '{cmd}' is permanently blocked."
            else:
                paths = section.get("paths", [])
                if not isinstance(paths, list):
                    return False, f"'{key}.paths' must be an array."
                for p in paths:
                    if is_blocked_system_path(p):
                        return False, f"Path '{p}' is in a system-critical location and cannot be added."
                    # Verify the path exists on disk
                    if not Path(p).exists():
                        return False, f"Path '{p}' does not exist on disk."

        return True, None

    def update_user_access(self, user_id: int, config: Dict[str, Any]) -> tuple:
        """Validate and save a user's system access configuration."""
        is_valid, error = self.validate_config(config)
        if not is_valid:
            return False, error

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET system_access = ? WHERE id = ?",
            (json.dumps(config), user_id)
        )
        conn.commit()
        conn.close()

        self.log_operation(
            user_id, "settings", "update_system_access",
            json.dumps(config)[:200], "APPROVED"
        )
        return True, None

    def get_user_access(self, user_id: int) -> Dict[str, Any]:
        """Public accessor for the user's system access config."""
        return self._get_user_access(user_id)

    def reset_user_access(self, user_id: int) -> Dict[str, Any]:
        """Reset user permissions to safe defaults."""
        defaults = DEFAULT_SYSTEM_ACCESS.copy()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET system_access = ? WHERE id = ?",
            (json.dumps(defaults), user_id)
        )
        conn.commit()
        conn.close()

        self.log_operation(
            user_id, "settings", "reset_permissions", "defaults", "APPROVED"
        )
        return defaults
