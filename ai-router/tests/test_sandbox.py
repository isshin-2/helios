"""Tests for the sandbox package."""

import pytest
from unittest.mock import patch, MagicMock
from sandbox.manager import SandboxManager
from sandbox.docker_sandbox import DockerSandboxManager

class TestSandboxManager:
    @patch("sandbox.docker_sandbox.subprocess.run")
    def test_docker_available_creates_docker_sandbox(self, mock_run):
        # Mock check_availability to return success
        mock_result_info = MagicMock()
        mock_result_info.returncode = 0
        
        # Mock start_sandbox to return success
        mock_result_start = MagicMock()
        mock_result_start.returncode = 0
        
        mock_run.side_effect = [mock_result_info, mock_result_start]
        
        manager = SandboxManager(use_docker=True)
        assert manager.use_docker is True
        
        sandbox_id = manager.create_sandbox()
        assert sandbox_id in manager.active_sandboxes
        assert manager.active_sandboxes[sandbox_id] == "docker"
        
        # Verify run was called with docker run
        assert mock_run.call_count == 2
        args = mock_run.call_args_list[1][0][0]
        assert "docker" in args
        assert "run" in args

    @patch("sandbox.docker_sandbox.subprocess.run")
    def test_docker_unavailable_falls_back_to_local(self, mock_run):
        # Mock check_availability to fail
        mock_run.side_effect = FileNotFoundError()
        
        manager = SandboxManager(use_docker=True)
        assert manager.use_docker is False
        
        sandbox_id = manager.create_sandbox()
        assert manager.active_sandboxes[sandbox_id] == "local"
        
        # Should not attempt to run docker run
        assert mock_run.call_count == 1

    @patch("sandbox.docker_sandbox.subprocess.run")
    def test_docker_execute_command(self, mock_run):
        # Setup mock for check and start
        mock_result_good = MagicMock()
        mock_result_good.returncode = 0
        mock_result_good.stdout = "hello\n"
        mock_result_good.stderr = ""
        mock_run.return_value = mock_result_good
        
        manager = SandboxManager(use_docker=True)
        sandbox_id = manager.create_sandbox()
        
        code, stdout, stderr = manager.execute(sandbox_id, "echo hello")
        
        assert code == 0
        assert stdout == "hello\n"
        assert manager.active_sandboxes[sandbox_id] == "docker"

    @patch("sandbox.manager.subprocess.run")
    @patch("sandbox.docker_sandbox.DockerSandboxManager.check_availability")
    def test_local_execute_command(self, mock_check, mock_run):
        mock_check.return_value = False
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "local execution\n"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        manager = SandboxManager(use_docker=True)
        sandbox_id = manager.create_sandbox()
        
        code, stdout, stderr = manager.execute(sandbox_id, "echo local execution")
        
        assert code == 0
        assert stdout == "local execution\n"
        assert manager.active_sandboxes[sandbox_id] == "local"
        
        # Verify local subprocess was called
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == "echo local execution"
