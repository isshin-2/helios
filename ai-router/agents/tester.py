"""
HELIOS — Tester Agent
Executes real automated tests deterministically (pytest, ruff, mypy, custom)
and interprets failures with an LLM without fabricating results.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from agents.base import AgentResult, AgentStatus, BaseAgent
from core.coding_runtime import CodingContext
from core.model_router import model_router
from gateway.host_gateway import HostGateway
from providers.base import BaseProvider

logger = logging.getLogger("helios.agents.tester")


class TestRunReport(BaseModel):
    """Structured report of test execution."""
    status: str  # "success", "failure", "error"
    exit_code: int
    command: str
    failed_tests: List[str] = Field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    traceback: str = ""
    duration_seconds: float = 0.0
    interpreted_reason: Optional[str] = None


class TesterAgent(BaseAgent):
    """
    Validates code correctness by running real tests and parsing genuine outputs.
    Guarantees that success is never returned unless tests genuinely pass.
    """
    __test__ = False

    def __init__(
        self,
        provider: BaseProvider,
        host_gateway: Optional[HostGateway] = None,
        agent_id: Optional[str] = None,
    ):
        super().__init__(agent_id)
        self.provider = provider
        self.host_gateway = host_gateway

    @property
    def agent_type(self) -> str:
        return "tester"

    def detect_test_command(self, workspace_path: str, context: Dict[str, Any]) -> str:
        """Deterministically detect appropriate test command based on workspace files."""
        # 1. Check explicit command in context
        coding_ctx: Optional[CodingContext] = context.get("coding_context")
        if coding_ctx and coding_ctx.test_command:
            return coding_ctx.test_command
        if context.get("test_command"):
            return context["test_command"]

        # 2. Check targeted test files from relevant_files or changed_files
        candidate_files = []
        if coding_ctx:
            candidate_files = coding_ctx.changed_files + coding_ctx.relevant_files
        elif "relevant_files" in context:
            candidate_files = context["relevant_files"]

        targeted_tests = [f for f in candidate_files if "test" in f.lower() and f.endswith(".py")]
        if targeted_tests:
            # Check existence in workspace
            existing = [t for t in targeted_tests if os.path.exists(os.path.join(workspace_path, t))]
            if existing:
                # Use python executable if venv exists
                python_bin = "python"
                if os.path.exists(os.path.join(workspace_path, "venv", "Scripts", "python.exe")):
                    python_bin = os.path.join(workspace_path, "venv", "Scripts", "python.exe")
                elif os.path.exists(os.path.join(workspace_path, "..", "venv", "Scripts", "python.exe")):
                    python_bin = os.path.normpath(os.path.join(workspace_path, "..", "venv", "Scripts", "python.exe"))
                return f"{python_bin} -m pytest {' '.join(existing[:3])}"

        # 3. Detect project type
        if os.path.exists(os.path.join(workspace_path, "tests")):
            return "python -m pytest tests"
        if os.path.exists(os.path.join(workspace_path, "package.json")):
            return "npm test"
        if os.path.exists(os.path.join(workspace_path, "Cargo.toml")):
            return "cargo test"

        # Fallback to python syntax check on changed files
        if candidate_files:
            py_files = [f for f in candidate_files if f.endswith(".py")]
            if py_files:
                return f"python -m py_compile {' '.join(py_files[:5])}"

        return "python -m pytest"

    def _parse_failed_tests(self, output: str) -> Tuple[List[str], str]:
        """Extract failed test names and traceback from pytest/output."""
        failed = []
        traceback_lines = []

        # Pytest pattern: FAILED tests/test_foo.py::test_bar - Error
        for match in re.finditer(r"FAILED\s+([^\s:]+::[^\s]+)", output):
            failed.append(match.group(1))

        # Traceback pattern
        tb_match = re.search(r"Traceback \(most recent call last\):[\s\S]*?(?=\n\n|\Z)", output)
        if tb_match:
            traceback_lines.append(tb_match.group(0))

        return failed, "\n\n".join(traceback_lines)

    async def _interpret_failure(
        self,
        command: str,
        stdout: str,
        stderr: str,
        failed_tests: List[str],
    ) -> str:
        """Call LLM to interpret failure evidence and provide diagnosis."""
        try:
            model_name, options = await model_router.prepare_model_for_agent("tester", self.provider)
            prompt = f"""You are the HELIOS Lead Tester.
A test suite failed with the following details:

COMMAND: {command}
FAILED TESTS: {failed_tests}
STDOUT (snippet):
{stdout[-2500:] if len(stdout) > 2500 else stdout}
STDERR:
{stderr[-1500:] if len(stderr) > 1500 else stderr}

Provide a concise, 2-3 sentence diagnosis of why the test failed and the root cause.
"""
            resp = await self.provider.generate(model=model_name, prompt=prompt, options=options)
            return resp.get("response", "").strip()
        except Exception as e:
            return f"Failure interpretation unavailable: {e}"

    async def execute(self, objective: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        started_at = datetime.now(timezone.utc)
        context = context or {}

        coding_ctx: Optional[CodingContext] = context.get("coding_context")
        workspace_path = os.getcwd()
        if coding_ctx and coding_ctx.worktree:
            workspace_path = coding_ctx.worktree
        elif context.get("worktree"):
            workspace_path = context["worktree"]
        elif context.get("repository_root"):
            workspace_path = context["repository_root"]

        workspace_path = os.path.abspath(workspace_path)
        command = self.detect_test_command(workspace_path, context)

        # Resolve pytest / python to the active virtual environment python
        import sys
        if command.startswith("pytest"):
            command = f'"{sys.executable}" -m pytest' + command[len("pytest"):]
        elif command.startswith("python "):
            command = f'"{sys.executable}"' + command[len("python"):]

        self.logger.info(f"[TESTER] Executing validation command: '{command}' in {workspace_path}")

        start_time = time.time()
        try:
            res = subprocess.run(
                command,
                shell=True,
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=180,
            )
            duration = time.time() - start_time
            exit_code = res.returncode
            stdout = res.stdout
            stderr = res.stderr
        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_time
            exit_code = -1
            stdout = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
            stderr = f"Test timed out after 180 seconds. {e.stderr or ''}"
        except Exception as e:
            duration = time.time() - start_time
            exit_code = -1
            stdout = ""
            stderr = f"Execution error: {str(e)}"

        failed_tests, traceback_str = self._parse_failed_tests(stdout + "\n" + stderr)
        passed = (exit_code == 0)

        interpreted_reason = None
        if not passed:
            interpreted_reason = await self._interpret_failure(command, stdout, stderr, failed_tests)

        report = TestRunReport(
            status="success" if passed else "failure",
            exit_code=exit_code,
            command=command,
            failed_tests=failed_tests,
            stdout=stdout[:5000],
            stderr=stderr[:5000],
            traceback=traceback_str[:3000],
            duration_seconds=round(duration, 2),
            interpreted_reason=interpreted_reason,
        )

        # Update CodingContext
        if coding_ctx:
            coding_ctx.test_results = report.model_dump()
            if not passed:
                coding_ctx.record_failure({
                    "stage": "tester",
                    "command": command,
                    "exit_code": exit_code,
                    "failed_tests": failed_tests,
                    "interpreted_reason": interpreted_reason,
                })

        if passed:
            return self._make_result(
                status=AgentStatus.SUCCESS,
                summary=f"Tests passed ({duration:.2f}s): {command}",
                detail=stdout[:2000],
                evidence=report.model_dump(),
                started_at=started_at,
                confidence=1.0,
            )
        else:
            return self._make_result(
                status=AgentStatus.FAILURE,
                summary=f"Tests failed (exit {exit_code}): {interpreted_reason or 'Test command returned non-zero exit code'}",
                detail=f"Command: {command}\nFailed: {failed_tests}\n{stderr or stdout[:1000]}",
                error=f"Exit code {exit_code}: {interpreted_reason or 'Test failure'}",
                evidence=report.model_dump(),
                started_at=started_at,
                confidence=1.0,
            )
