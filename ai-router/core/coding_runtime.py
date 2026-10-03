"""
HELIOS — Coding Task Runtime & Isolated Workspace Manager
Provides an isolated execution environment (git worktree + sandbox) and
shared structured state (CodingContext) for multi-agent coding swarms.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from core.checkpoints import CheckpointManager
from core.task_contract import StepRecord, TaskContract
from security.permissions import PermissionManager, validate_path

logger = logging.getLogger("helios.coding_runtime")


class CodingContext(BaseModel):
    """
    Structured state shared across all agents in the coding swarm.
    Prevents agents from redundantly discovering repository state.
    """
    task_id: str
    objective: str
    repository_root: str
    worktree: Optional[str] = None
    relevant_files: List[str] = Field(default_factory=list)
    changed_files: List[str] = Field(default_factory=list)
    plan: Optional[Dict[str, Any]] = None
    architecture: Optional[Dict[str, Any]] = None
    test_command: Optional[str] = None
    build_command: Optional[str] = None
    lint_command: Optional[str] = None
    test_results: Optional[Dict[str, Any]] = None
    failures: List[Dict[str, Any]] = Field(default_factory=list)
    previous_attempts: List[Dict[str, Any]] = Field(default_factory=list)
    remaining_budget: Dict[str, Any] = Field(default_factory=dict)
    artifacts: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def record_failure(self, failure_info: Dict[str, Any]) -> None:
        """Record failure evidence into the context."""
        self.failures.append(failure_info)
        self.previous_attempts.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "failure": failure_info,
            "changed_files": list(self.changed_files),
        })

    def update_budget(self, contract: TaskContract) -> None:
        """Update remaining budget metrics from the TaskContract."""
        self.remaining_budget = {
            "iterations_left": max(0, contract.budget.max_iterations - contract.iterations),
            "retries_left": max(0, contract.budget.max_retries - contract.retry_count),
            "tool_calls_left": max(0, contract.budget.max_tool_calls - contract.tool_calls),
            "agent_calls_left": max(0, contract.budget.max_agent_calls - contract.agent_calls),
        }


class WorkspaceManager:
    """
    Manages an isolated workspace for a coding task.
    Prefers git worktree; falls back to an isolated shadow directory.
    Guarantees the user's primary working tree is never silently modified.
    """

    def __init__(self, repo_root: str, task_id: str):
        self.repo_root = os.path.abspath(repo_root)
        self.task_id = task_id
        self.branch_name = f"helios-swarm-{task_id[:8]}"
        self.worktree_dir = os.path.join(self.repo_root, ".helios_worktrees", self.task_id)
        self.is_git = self._check_is_git()
        self.is_worktree = False
        self.is_shadow = False

    def _check_is_git(self) -> bool:
        """Check if repository_root is a git repository."""
        git_dir = os.path.join(self.repo_root, ".git")
        return os.path.exists(git_dir)

    def setup(self) -> str:
        """Create and return the isolated working directory path."""
        os.makedirs(os.path.dirname(self.worktree_dir), exist_ok=True)

        if self.is_git:
            try:
                # First cleanup any previous worktree with the same path
                subprocess.run(
                    ["git", "worktree", "remove", "--force", self.worktree_dir],
                    cwd=self.repo_root,
                    capture_output=True,
                    text=True,
                )
                subprocess.run(
                    ["git", "branch", "-D", self.branch_name],
                    cwd=self.repo_root,
                    capture_output=True,
                    text=True,
                )

                # Attempt git worktree creation
                cmd = ["git", "worktree", "add", "-b", self.branch_name, self.worktree_dir]
                res = subprocess.run(cmd, cwd=self.repo_root, capture_output=True, text=True, timeout=15)
                if res.returncode == 0 and os.path.isdir(self.worktree_dir):
                    self.is_worktree = True
                    logger.info(f"[WORKSPACE] Created git worktree at {self.worktree_dir} on branch {self.branch_name}")
                    return self.worktree_dir
                else:
                    logger.warning(f"[WORKSPACE] git worktree failed: {res.stderr}; falling back to shadow directory.")
            except Exception as e:
                logger.warning(f"[WORKSPACE] Exception creating git worktree: {e}; falling back.")

        # Fallback: Isolated shadow directory
        self._setup_shadow()
        return self.worktree_dir

    def _setup_shadow(self) -> None:
        """Create isolated shadow directory copying necessary source files."""
        if os.path.exists(self.worktree_dir):
            shutil.rmtree(self.worktree_dir, ignore_errors=True)

        def ignore_patterns(folder, contents):
            return {".git", ".helios_worktrees", "__pycache__", "venv", ".pytest_cache", "node_modules"}

        shutil.copytree(self.repo_root, self.worktree_dir, ignore=ignore_patterns)
        self.is_shadow = True
        logger.info(f"[WORKSPACE] Created isolated shadow directory at {self.worktree_dir}")

    def get_working_path(self) -> str:
        """Return the active isolated workspace path."""
        return self.worktree_dir if (self.is_worktree or self.is_shadow) else self.repo_root

    def get_diff(self) -> str:
        """Capture git diff or directory diff against base."""
        working_path = self.get_working_path()
        if self.is_worktree:
            try:
                res = subprocess.run(["git", "diff", "HEAD"], cwd=working_path, capture_output=True, text=True)
                diff = res.stdout
                # Also include untracked new files
                untracked = subprocess.run(
                    ["git", "status", "--porcelain"], cwd=working_path, capture_output=True, text=True
                )
                if untracked.stdout.strip():
                    diff += f"\n--- Untracked/Status ---\n{untracked.stdout}"
                return diff
            except Exception as e:
                logger.error(f"[WORKSPACE] Failed to get git diff: {e}")
                return ""
        elif self.is_shadow:
            return self._compute_shadow_diff()
        return ""

    def _compute_shadow_diff(self) -> str:
        """Compute unified diff between repo_root and shadow directory."""
        import difflib
        diff_lines = []
        skip_dirs = {".git", ".helios_worktrees", "__pycache__", "venv", ".pytest_cache", "node_modules"}

        for root, dirs, files in os.walk(self.worktree_dir):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for file in files:
                shadow_file = os.path.join(root, file)
                rel_path = os.path.relpath(shadow_file, self.worktree_dir)
                original_file = os.path.join(self.repo_root, rel_path)

                if not os.path.exists(original_file):
                    diff_lines.append(f"New file created: {rel_path}\n")
                    continue

                try:
                    with open(original_file, "r", encoding="utf-8", errors="ignore") as f1, \
                         open(shadow_file, "r", encoding="utf-8", errors="ignore") as f2:
                        u_diff = list(difflib.unified_diff(
                            f1.readlines(), f2.readlines(),
                            fromfile=f"a/{rel_path}", tofile=f"b/{rel_path}"
                        ))
                        if u_diff:
                            diff_lines.extend(u_diff)
                except Exception:
                    pass

        return "".join(diff_lines)

    def get_changed_files(self) -> List[str]:
        """Detect modified or added files relative to base."""
        working_path = self.get_working_path()
        changed: List[str] = []

        if self.is_worktree:
            try:
                res = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=working_path,
                    capture_output=True,
                    text=True,
                )
                for line in res.stdout.splitlines():
                    if line.strip():
                        # format is 'XY path'
                        parts = line.strip().split(maxsplit=1)
                        if len(parts) == 2:
                            changed.append(parts[1])
            except Exception as e:
                logger.error(f"[WORKSPACE] Error reading git status: {e}")
        elif self.is_shadow:
            skip_dirs = {".git", ".helios_worktrees", "__pycache__", "venv", ".pytest_cache", "node_modules"}
            for root, dirs, files in os.walk(self.worktree_dir):
                dirs[:] = [d for d in dirs if d not in skip_dirs]
                for file in files:
                    shadow_file = os.path.join(root, file)
                    rel_path = os.path.relpath(shadow_file, self.worktree_dir)
                    orig_file = os.path.join(self.repo_root, rel_path)
                    if not os.path.exists(orig_file):
                        changed.append(rel_path)
                    else:
                        try:
                            if os.path.getmtime(shadow_file) > os.path.getmtime(orig_file):
                                changed.append(rel_path)
                        except OSError:
                            pass
        return sorted(list(set(changed)))

    def rollback(self) -> bool:
        """Roll back all modifications in the isolated workspace."""
        working_path = self.get_working_path()
        if self.is_worktree:
            try:
                subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=working_path, capture_output=True, check=True)
                subprocess.run(["git", "clean", "-fd"], cwd=working_path, capture_output=True, check=True)
                logger.info(f"[WORKSPACE] Rolled back git worktree at {working_path}")
                return True
            except Exception as e:
                logger.error(f"[WORKSPACE] Failed to rollback git worktree: {e}")
                return False
        elif self.is_shadow:
            self._setup_shadow()
            logger.info(f"[WORKSPACE] Restored shadow workspace at {working_path}")
            return True
        return False

    def cleanup(self) -> None:
        """Remove isolated worktree or shadow directory upon task completion/cancellation."""
        if self.is_worktree:
            try:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", self.worktree_dir],
                    cwd=self.repo_root,
                    capture_output=True,
                    text=True,
                )
                subprocess.run(
                    ["git", "branch", "-D", self.branch_name],
                    cwd=self.repo_root,
                    capture_output=True,
                    text=True,
                )
                logger.info(f"[WORKSPACE] Cleaned up git worktree {self.worktree_dir}")
            except Exception as e:
                logger.warning(f"[WORKSPACE] Cleanup error for worktree: {e}")
        elif self.is_shadow:
            shutil.rmtree(self.worktree_dir, ignore_errors=True)
            logger.info(f"[WORKSPACE] Cleaned up shadow workspace {self.worktree_dir}")


class CodingTaskRuntime:
    """
    Execution environment for coding tasks.
    Coordinates the TaskContract, WorkspaceManager, CodingContext,
    Checkpoints, and Security controls.
    """

    def __init__(
        self,
        contract: TaskContract,
        repo_root: str,
        permission_manager: Optional[PermissionManager] = None,
        checkpoint_manager: Optional[CheckpointManager] = None,
    ):
        self.contract = contract
        self.repo_root = os.path.abspath(repo_root)
        self.permission_manager = permission_manager or PermissionManager()
        self.checkpoint_manager = checkpoint_manager or CheckpointManager()

        # Initialize Workspace
        self.workspace = WorkspaceManager(self.repo_root, self.contract.task_id)
        worktree_path = self.workspace.setup()

        # Initialize Shared Coding Context
        self.context = CodingContext(
            task_id=self.contract.task_id,
            objective=self.contract.objective,
            repository_root=self.repo_root,
            worktree=worktree_path,
        )
        self.context.update_budget(self.contract)

        # Sync contract metadata
        self.contract.metadata["worktree"] = worktree_path
        self.contract.metadata["is_coding_task"] = True
        self.contract.metadata["workflow"] = "coding"

        # Initial checkpoint
        self.checkpoint_manager.save_checkpoint(self.contract)

    @property
    def working_directory(self) -> str:
        return self.workspace.get_working_path()

    def sync_context(self) -> CodingContext:
        """Refresh changed files and budget into context."""
        self.context.changed_files = self.workspace.get_changed_files()
        self.context.update_budget(self.contract)
        return self.context

    def save_checkpoint(self) -> bool:
        """Persist current contract and context to checkpoint database."""
        self.contract.metadata["context"] = self.context.model_dump()
        return self.checkpoint_manager.save_checkpoint(self.contract)

    def rollback(self) -> bool:
        """Roll back all workspace changes."""
        success = self.workspace.rollback()
        self.sync_context()
        return success

    def cleanup(self) -> None:
        """Clean up the isolated workspace."""
        self.workspace.cleanup()
