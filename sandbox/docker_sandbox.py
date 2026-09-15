"""
HELIOS — Docker Sandbox
Provides isolated execution of terminal commands and code tests.
Uses the docker CLI via subprocess.
"""

import logging
import subprocess
import shlex
from typing import Tuple, Optional

logger = logging.getLogger("helios.sandbox.docker")

class DockerSandboxManager:
    """Manages ephemeral Docker containers for execution isolation."""
    
    def __init__(self, image: str = "python:3.13-slim"):
        self.image = image
    
    def check_availability(self) -> bool:
        """Check if the docker CLI is available and the daemon is running."""
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def start_sandbox(self, sandbox_id: str, memory_limit: str = "512m") -> bool:
        """
        Starts a detached container that keeps running.
        sandbox_id is used as the container name.
        """
        try:
            # We run the container in detached mode (-d), keeping stdin open (-i) 
            # and running a sleep loop so it stays alive.
            cmd = [
                "docker", "run", "-d", "-i",
                "--name", sandbox_id,
                "--memory", memory_limit,
                "--network", "none",  # Default strict isolation
                self.image,
                "sleep", "infinity"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                logger.error(f"Failed to start sandbox {sandbox_id}: {result.stderr}")
                return False
            return True
        except Exception as e:
            logger.error(f"Exception starting sandbox {sandbox_id}: {e}")
            return False

    def execute_command(self, sandbox_id: str, command: str, timeout: int = 60) -> Tuple[int, str, str]:
        """
        Executes a command inside the running sandbox using `docker exec`.
        Returns (exit_code, stdout, stderr).
        """
        try:
            # We use shlex.split on the command, or pass it to sh -c
            cmd = [
                "docker", "exec", sandbox_id,
                "sh", "-c", command
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired as e:
            logger.warning(f"Command timed out in sandbox {sandbox_id}")
            return -1, (e.stdout.decode() if e.stdout else ""), "Execution timed out."
        except Exception as e:
            logger.error(f"Exception executing command in sandbox {sandbox_id}: {e}")
            return -1, "", str(e)

    def destroy_sandbox(self, sandbox_id: str) -> bool:
        """Forcefully removes the sandbox container."""
        try:
            cmd = ["docker", "rm", "-f", sandbox_id]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Exception destroying sandbox {sandbox_id}: {e}")
            return False
