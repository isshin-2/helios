"""
HELIOS — Host Gateway
Manages interactions with the host OS, such as file system operations,
sandboxed execution, and permission validation.
"""

import logging
import os
from typing import Tuple

from sandbox.manager import SandboxManager
from security.permissions import PermissionManager

logger = logging.getLogger("helios.gateway.host")

class HostGateway:
    """
    Facade for all operations that interact with the host system.
    """
    def __init__(self, permission_manager: PermissionManager, use_docker_sandbox: bool = True):
        self.permission_manager = permission_manager
        self.sandbox_manager = SandboxManager(use_docker=use_docker_sandbox)

    def is_path_allowed(self, path: str) -> bool:
        """Validates if the absolute path is allowed for read/write."""
        abs_path = os.path.abspath(path)
        return self.permission_manager.validate_path_access(abs_path)

    def execute_in_sandbox(self, command: str, timeout: int = 60) -> Tuple[int, str, str]:
        """
        Executes a command safely in an ephemeral sandbox.
        """
        sandbox_id = self.sandbox_manager.create_sandbox()
        try:
            return self.sandbox_manager.execute(sandbox_id, command, timeout)
        finally:
            self.sandbox_manager.destroy_sandbox(sandbox_id)

    def execute_host_command(self, command: str, user_id: int) -> Tuple[bool, str]:
        """
        Executes a command directly on the host (requires permission).
        Returns (success, output_or_error)
        """
        base_cmd = command.split()[0] if command else ""
        if not self.permission_manager.is_command_allowed(base_cmd):
            return False, f"Command '{base_cmd}' is blocked or not in allowed list."
            
        try:
            import subprocess
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=120
            )
            output = result.stdout
            if result.stderr:
                output += "\nSTDERR:\n" + result.stderr
            return result.returncode == 0, output
        except subprocess.TimeoutExpired as e:
            return False, f"Command timed out. STDOUT: {e.stdout.decode() if e.stdout else ''}"
        except Exception as e:
            return False, str(e)
