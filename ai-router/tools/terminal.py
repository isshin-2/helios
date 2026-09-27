import os
import re
import shlex
import subprocess
import logging
from pathlib import Path
from typing import Tuple, Optional
from pydantic import BaseModel, Field

from tools.base import BaseTool
from security.permissions import (
    PermissionManager, 
    HELIOS_DIR, 
    MAX_OUTPUT_BYTES,
    TERMINAL_TIMEOUT
)

logger = logging.getLogger(__name__)

class TerminalInput(BaseModel):
    command: str = Field(description="The complete command string to execute in the terminal (e.g., 'python test.py' or 'dir').")

class TerminalTool(BaseTool):
    def __init__(self, permission_manager: PermissionManager):
        self.permission_manager = permission_manager

    @property
    def name(self) -> str:
        return "TerminalTool"

    @property
    def description(self) -> str:
        return "Executes a command in the local terminal. Sandboxed and requires approval for sensitive commands."

    @property
    def input_schema(self) -> type[BaseModel]:
        return TerminalInput

    @property
    def requires_permission(self) -> bool:
        return True

    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        working_directory = kwargs.get("working_directory", HELIOS_DIR)
        command = kwargs.get("command")

        if not command and "prompt" in kwargs:
            try:
                executable, args = self._parse_command(kwargs["prompt"])
                command = f"{executable} {' '.join(args)}"
            except ValueError as exc:
                return (str(exc), self.name)
                
        if not command:
            return ("Error: No command provided.", self.name)

        try:
            parts = shlex.split(command, posix=(os.name != 'nt'))
            if not parts:
                return ("Error: Empty command provided.", self.name)
            executable = parts[0]
            args = parts[1:]
        except ValueError as exc:
            return (f"Error parsing command: {exc}", self.name)

        perm = self.permission_manager.can_execute(
            user_id, executable, args, working_directory
        )

        if not perm.allowed:
            self.permission_manager.log_operation(
                user_id, self.name, "execute",
                f"{executable} {' '.join(args)}",
                "DENIED", error=perm.reason,
            )
            return (f"**Permission denied**: {perm.reason}", self.name)

        validated_cwd = perm.resolved_path or Path(working_directory)

        if self.permission_manager.needs_approval(executable):
            has_approval = self.permission_manager.approval_manager.has_session_approval(
                user_id, "execute", executable
            )
            if not has_approval:
                cmd_display = f"{executable} {' '.join(args)}".strip()
                return (f"APPROVAL_REQUIRED::execute::{cmd_display}", self.name)

        try:
            result = subprocess.run(
                [executable] + args,
                shell=False,
                cwd=str(validated_cwd),
                capture_output=True,
                text=True,
                timeout=TERMINAL_TIMEOUT,
            )

            stdout = self._cap_output(result.stdout)
            stderr = self._cap_output(result.stderr)

            self.permission_manager.log_operation(
                user_id, self.name, "execute",
                f"{executable} {' '.join(args)}",
                "APPROVED",
                exec_result=f"exit_code={result.returncode}",
            )

            return (self._format_result(executable, args, result.returncode, stdout, stderr), self.name)

        except subprocess.TimeoutExpired:
            self.permission_manager.log_operation(
                user_id, self.name, "execute",
                f"{executable} {' '.join(args)}",
                "APPROVED",
                error=f"Timed out after {TERMINAL_TIMEOUT}s",
            )
            return (
                f"Command timed out after {TERMINAL_TIMEOUT} seconds.\n"
                f"Command: `{executable} {' '.join(args)}`",
                self.name,
            )
        except FileNotFoundError:
            return (
                f"Command not found: `{executable}`. Make sure it is installed and on the system PATH.",
                self.name,
            )
        except PermissionError as exc:
            return (f"OS permission error running `{executable}`: {exc}", self.name)
        except Exception as exc:
            logger.exception("Unexpected error executing command")
            self.permission_manager.log_operation(
                user_id, self.name, "execute",
                f"{executable} {' '.join(args)}",
                "APPROVED", error=str(exc),
            )
            return (f"Unexpected error: {exc}", self.name)

    @staticmethod
    def _parse_command(prompt: str) -> Tuple[str, list]:
        stripped = prompt.strip()
        if stripped.lower().startswith("!run "):
            cmd_string = stripped[5:].strip()
            if not cmd_string:
                raise ValueError("No command provided after `!run`.")
            parts = shlex.split(cmd_string, posix=(os.name != 'nt'))
            return parts[0], parts[1:]

        match = re.search(r"(?:run|execute)\s+(.+)", stripped, re.IGNORECASE)
        if match:
            cmd_string = match.group(1).strip()
            cmd_string = cmd_string.strip("`\"'")
            if not cmd_string:
                raise ValueError("Could not extract a command from the prompt.")
            parts = shlex.split(cmd_string, posix=(os.name != 'nt'))
            return parts[0], parts[1:]

        raise ValueError("Could not parse a command from your prompt.")

    @staticmethod
    def _cap_output(text: str) -> str:
        if not text:
            return ""
        encoded = text.encode("utf-8", errors="replace")
        if len(encoded) <= MAX_OUTPUT_BYTES:
            return text
        truncated = encoded[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
        return truncated + "\n\n[output truncated - exceeded 100 KB limit]"

    @staticmethod
    def _format_result(executable: str, args: list, return_code: int, stdout: str, stderr: str) -> str:
        cmd_display = f"{executable} {' '.join(args)}".strip()
        status = "✅" if return_code == 0 else "❌"

        lines = [f"{status} Command finished (exit code {return_code})"]
        lines.append(f"```bash\n$ {cmd_display}\n```")

        if stdout:
            lines.append(f"**stdout**\n```\n{stdout}\n```")
        if stderr:
            lines.append(f"**stderr**\n```\n{stderr}\n```")
        if not stdout and not stderr:
            lines.append("_(no output)_")

        return "\n\n".join(lines)
