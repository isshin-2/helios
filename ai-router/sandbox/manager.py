"""
HELIOS — Sandbox Manager
Coordinates sandboxed execution, falling back to local isolated subprocesses
if Docker is not available.
"""

import logging
import uuid
import subprocess
from typing import Tuple, Optional
from sandbox.docker_sandbox import DockerSandboxManager

logger = logging.getLogger("helios.sandbox.manager")

class SandboxManager:
    """
    Unified manager for executing untrusted or side-effecting code.
    Uses Docker if available, otherwise falls back to local subprocess.
    """
    def __init__(self, use_docker: bool = True):
        self.docker = DockerSandboxManager()
        # Fallback to local if docker isn't explicitly disabled but is unavailable
        self.use_docker = use_docker and self.docker.check_availability()
        
        if not self.use_docker and use_docker:
            logger.warning("Docker is not available. Falling back to local subprocess execution.")
            
        self.active_sandboxes = {}

    def create_sandbox(self) -> str:
        """Creates a new sandbox environment and returns its ID."""
        sandbox_id = f"helios-sandbox-{uuid.uuid4().hex[:8]}"
        
        if self.use_docker:
            success = self.docker.start_sandbox(sandbox_id)
            if success:
                self.active_sandboxes[sandbox_id] = "docker"
                return sandbox_id
            else:
                logger.warning(f"Failed to create Docker sandbox {sandbox_id}. Falling back to local.")
        
        # Local fallback (we don't pre-start a container, just track the ID)
        self.active_sandboxes[sandbox_id] = "local"
        return sandbox_id

    def execute(self, sandbox_id: str, command: str, timeout: int = 60) -> Tuple[int, str, str]:
        """
        Executes a command in the specified sandbox.
        """
        if sandbox_id not in self.active_sandboxes:
            return -1, "", f"Sandbox {sandbox_id} does not exist or was destroyed."
            
        sandbox_type = self.active_sandboxes[sandbox_id]
        
        if sandbox_type == "docker":
            return self.docker.execute_command(sandbox_id, command, timeout)
        else:
            # Local fallback execution
            try:
                result = subprocess.run(
                    command, 
                    shell=True, 
                    capture_output=True, 
                    text=True, 
                    timeout=timeout
                )
                return result.returncode, result.stdout, result.stderr
            except subprocess.TimeoutExpired as e:
                return -1, (e.stdout.decode() if e.stdout else ""), "Execution timed out."
            except Exception as e:
                return -1, "", str(e)

    def destroy_sandbox(self, sandbox_id: str) -> bool:
        """Destroys the specified sandbox."""
        if sandbox_id not in self.active_sandboxes:
            return False
            
        sandbox_type = self.active_sandboxes.pop(sandbox_id)
        
        if sandbox_type == "docker":
            return self.docker.destroy_sandbox(sandbox_id)
        else:
            # Local sandboxes have no persistent state to tear down
            return True
