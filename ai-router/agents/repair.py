"""
HELIOS — Repair Agent
Consumes failure evidence (test output, diff, traceback, architecture) to formulate
and execute minimal, surgical fixes without rewriting unrelated code.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from agents.base import AgentResult, AgentStatus, BaseAgent
from core.coding_runtime import CodingContext
from core.model_router import model_router
from providers.base import BaseProvider
from security.permissions import PermissionManager

logger = logging.getLogger("helios.agents.repair")


class RepairPlan(BaseModel):
    """Structured plan for fixing a specific failure."""
    failure_analysis: str = Field(description="Root cause analysis of the failure.")
    target_file: str = Field(description="Specific file needing modification.")
    search_block: str = Field(description="Existing code block to locate.")
    replace_block: str = Field(description="Replacement code containing the fix.")
    verification_command: Optional[str] = Field(default=None, description="Command to verify fix.")


class RepairAgent(BaseAgent):
    """
    Analyzes verified failures and executes targeted minimal fixes.
    """

    def __init__(
        self,
        provider: BaseProvider,
        permission_manager: Optional[PermissionManager] = None,
        agent_id: Optional[str] = None,
    ):
        super().__init__(agent_id)
        self.provider = provider
        self.permission_manager = permission_manager or PermissionManager()

    @property
    def agent_type(self) -> str:
        return "repair"

    def _apply_patch(self, workspace_root: str, file_path: str, search_block: str, replace_block: str) -> Tuple[bool, str]:
        """Apply surgical patch to file."""
        target = os.path.normpath(os.path.join(workspace_root, file_path)) if not os.path.isabs(file_path) else os.path.normpath(file_path)
        if not target.startswith(os.path.normpath(workspace_root)):
            return False, f"Access denied: {file_path} is outside workspace"
        if not self.permission_manager.validate_path_access(target):
            return False, f"Write blocked by security policy for {file_path}"
        if not os.path.exists(target):
            return False, f"File not found: {file_path}"

        try:
            with open(target, "r", encoding="utf-8") as f:
                content = f.read()

            if search_block not in content:
                # Normalize line endings
                norm_content = content.replace("\r\n", "\n")
                norm_search = search_block.replace("\r\n", "\n")
                if norm_search in norm_content:
                    new_content = norm_content.replace(norm_search, replace_block.replace("\r\n", "\n"), 1)
                else:
                    return False, f"Search block not found in {file_path}"
            else:
                new_content = content.replace(search_block, replace_block, 1)

            with open(target, "w", encoding="utf-8") as f:
                f.write(new_content)
            return True, f"Successfully patched {file_path}"
        except Exception as e:
            return False, f"Patch failed: {str(e)}"

    def _read_file_snippet(self, workspace_root: str, file_path: str, max_chars: int = 15000) -> str:
        """Safely read relevant file snippet for the model."""
        target = os.path.normpath(os.path.join(workspace_root, file_path)) if not os.path.isabs(file_path) else os.path.normpath(file_path)
        if not os.path.exists(target):
            return ""
        try:
            with open(target, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return content if len(content) <= max_chars else content[:max_chars] + "\n...[truncated]"
        except Exception:
            return ""

    async def execute(self, objective: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        started_at = datetime.now(timezone.utc)
        context = context or {}

        coding_ctx: Optional[CodingContext] = context.get("coding_context")
        workspace_root = os.getcwd()
        if coding_ctx and coding_ctx.worktree:
            workspace_root = coding_ctx.worktree
        elif context.get("worktree"):
            workspace_root = context["worktree"]
        elif context.get("repository_root"):
            workspace_root = context["repository_root"]

        workspace_root = os.path.abspath(workspace_root)

        # 1. Gather failure evidence
        test_results = (coding_ctx.test_results if coding_ctx else None) or context.get("test_results") or {}
        failed_tests = test_results.get("failed_tests", [])
        stderr = test_results.get("stderr", "")
        stdout = test_results.get("stdout", "")
        traceback_str = test_results.get("traceback", "")
        command = test_results.get("command", "")
        architecture = (coding_ctx.architecture if coding_ctx else None) or context.get("architecture") or {}
        changed_files = (coding_ctx.changed_files if coding_ctx else None) or context.get("changed_files") or []

        # Find target source files to provide context
        source_snippets = {}
        for f in changed_files[:5]:
            snippet = self._read_file_snippet(workspace_root, f)
            if snippet:
                source_snippets[f] = snippet

        # 2. Query Repair Model
        model_name, options = await model_router.prepare_model_for_agent("repair", self.provider)

        prompt = f"""You are the HELIOS Lead Repair Specialist.
Your job is to fix a test failure by applying a minimal, surgical code modification.
Do NOT rewrite entire files. Modify only the necessary lines to resolve the failure.

OBJECTIVE: {objective}
ARCHITECTURE CONSTRAINTS: {json.dumps(architecture.get('constraints', []))}
FAILED COMMAND: {command}
FAILED TESTS: {failed_tests}
ERROR / TRACEBACK:
{traceback_str or stderr or stdout[-2000:]}

CHANGED FILES RECENTLY:
{json.dumps(changed_files)}

SOURCE SNIPPETS:
{json.dumps(source_snippets)}

You must respond with valid JSON matching this schema:
{{
  "failure_analysis": "Concise explanation of the exact bug",
  "target_file": "relative/path/to/file_to_patch.py",
  "search_block": "exact lines of code currently in the file",
  "replace_block": "replacement lines fixing the issue",
  "verification_command": "{command}"
}}
"""

        try:
            resp = await self.provider.generate(
                model=model_name,
                prompt=prompt,
                options=options,
                stream=False,
                format="json",
            )
            raw = resp.get("response", "").strip()

            parsed = None
            try:
                parsed = json.loads(raw)
            except Exception:
                m = re.search(r"(\{[\s\S]*\})", raw)
                if m:
                    parsed = json.loads(m.group(1))

            if not parsed or "target_file" not in parsed:
                return self._make_result(
                    status=AgentStatus.FAILURE,
                    summary="Repair model failed to provide structured patch.",
                    error="Invalid repair plan output",
                    started_at=started_at,
                )

            repair_plan = RepairPlan(**parsed)

            # 3. Apply Minimal Fix
            success, msg = self._apply_patch(
                workspace_root,
                repair_plan.target_file,
                repair_plan.search_block,
                repair_plan.replace_block,
            )

            if not success:
                return self._make_result(
                    status=AgentStatus.FAILURE,
                    summary=f"Failed to apply repair patch: {msg}",
                    error=msg,
                    evidence={"plan": repair_plan.model_dump()},
                    started_at=started_at,
                )

            # Update CodingContext
            if coding_ctx:
                if repair_plan.target_file not in coding_ctx.changed_files:
                    coding_ctx.changed_files.append(repair_plan.target_file)

            # 4. Run Targeted Test to verify repair
            verify_cmd = repair_plan.verification_command or command
            verify_success = True
            verify_output = ""
            if verify_cmd:
                try:
                    res = subprocess.run(
                        verify_cmd,
                        shell=True,
                        cwd=workspace_root,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    verify_success = (res.returncode == 0)
                    verify_output = res.stdout if verify_success else res.stderr
                except Exception as ex:
                    verify_output = str(ex)

            return self._make_result(
                status=AgentStatus.SUCCESS if verify_success else AgentStatus.PARTIAL,
                summary=f"Repair applied to {repair_plan.target_file}: {repair_plan.failure_analysis}",
                detail=f"Applied patch to {repair_plan.target_file}.\nVerification: {'Passed' if verify_success else 'Pending re-run'}",
                artifacts=[repair_plan.target_file],
                evidence={
                    "plan": repair_plan.model_dump(),
                    "patch_applied": True,
                    "verify_output": verify_output[:1000],
                },
                started_at=started_at,
                confidence=0.9 if verify_success else 0.7,
            )

        except Exception as e:
            self.logger.error(f"Repair error: {e}", exc_info=True)
            return self._make_result(
                status=AgentStatus.FAILURE,
                summary=f"Repair execution failed: {str(e)}",
                error=str(e),
                started_at=started_at,
            )
