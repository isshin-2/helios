import os
import shlex
import subprocess
import logging
from pathlib import Path
from typing import Tuple
from pydantic import BaseModel, Field

from tools.base import BaseTool
from security.permissions import PermissionManager, HELIOS_DIR, TERMINAL_TIMEOUT

logger = logging.getLogger(__name__)

class StatefulShellInput(BaseModel):
    command: str = Field(description="The command string to execute in the stateful shell.")

class StatefulShellTool(BaseTool):
    def __init__(self, permission_manager: PermissionManager):
        self.permission_manager = permission_manager
        # Persist environment and working directory across tool calls
        self.env = os.environ.copy()
        self.current_cwd = str(HELIOS_DIR)
        self.max_output_lines = 500  # SWE-agent style truncation

    @property
    def name(self) -> str:
        return "StatefulShellTool"

    @property
    def description(self) -> str:
        return "Executes commands in a persistent shell. Maintains environment variables and CWD across calls. Automatically truncates massive outputs to protect the context window."

    @property
    def input_schema(self) -> type[BaseModel]:
        return StatefulShellInput

    @property
    def requires_permission(self) -> bool:
        return True

    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        command = kwargs.get("command")
        if not command:
            return ("Error: No command provided.", self.name)

        # Handle 'cd' commands natively in Python to persist state
        if command.strip().startswith("cd "):
            target_dir = command.strip()[3:].strip().strip("\"'")
            try:
                new_cwd = Path(self.current_cwd) / target_dir
                new_cwd = new_cwd.resolve()
                if new_cwd.is_dir():
                    self.current_cwd = str(new_cwd)
                    return (f"Changed directory to {self.current_cwd}", self.name)
                else:
                    return (f"Error: Directory not found {target_dir}", self.name)
            except Exception as e:
                return (f"Error changing directory: {e}", self.name)

        # Basic permission check
        parts = shlex.split(command, posix=(os.name != 'nt'))
        if parts:
            perm = self.permission_manager.can_execute(user_id, parts[0], parts[1:], self.current_cwd)
            if not perm.allowed:
                return (f"**Permission denied**: {perm.reason}", self.name)

            if self.permission_manager.needs_approval(parts[0]):
                if not self.permission_manager.approval_manager.has_session_approval(user_id, "execute", parts[0]):
                    return (f"APPROVAL_REQUIRED::execute::{command}", self.name)

        try:
            # Execute with persistent environment
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.current_cwd,
                env=self.env,
                capture_output=True,
                text=True,
                timeout=TERMINAL_TIMEOUT,
            )

            stdout = self._smart_truncate(result.stdout)
            stderr = self._smart_truncate(result.stderr)

            # Update environment if it was an export/set command
            if command.startswith("set ") or command.startswith("export "):
                self._update_env_from_system()

            return (self._format_result(command, result.returncode, stdout, stderr), self.name)

        except subprocess.TimeoutExpired:
            return (f"Command timed out after {TERMINAL_TIMEOUT} seconds.\nCommand: `{command}`", self.name)
        except Exception as exc:
            logger.exception("Unexpected shell error")
            return (f"Unexpected error: {exc}", self.name)

    def _update_env_from_system(self):
        # In a full openinterpreter implementation, we'd source the env. 
        # For this prototype, we'll keep it simple.
        pass

    def _smart_truncate(self, text: str) -> str:
        if not text:
            return ""
        lines = text.splitlines()
        if len(lines) <= self.max_output_lines:
            return text
        
        # Keep first 100 and last 400 lines (SWE-agent methodology)
        head = "\n".join(lines[:100])
        tail = "\n".join(lines[-400:])
        return f"{head}\n\n... [TRUNCATED {len(lines) - 500} LINES] ...\n\n{tail}"

    @staticmethod
    def _format_result(command: str, return_code: int, stdout: str, stderr: str) -> str:
        status = "✅" if return_code == 0 else "❌"
        lines = [f"{status} Command finished (exit code {return_code})"]
        lines.append(f"```bash\n$ {command}\n```")
        if stdout: lines.append(f"**stdout**\n```\n{stdout}\n```")
        if stderr: lines.append(f"**stderr**\n```\n{stderr}\n```")
        if not stdout and not stderr: lines.append("_(no output)_")
        return "\n\n".join(lines)
