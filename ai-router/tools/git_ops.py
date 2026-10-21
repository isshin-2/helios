"""
HELIOS — Git Operations Tool
Enables agents to safely query repository status, inspect branches, view commits,
compute diffs, and create commits with zero-trust permission boundaries.
"""

import os
import subprocess
from typing import Tuple, List, Optional
from pydantic import BaseModel, Field
from tools.base import BaseTool
from security.permissions import PermissionManager, HELIOS_DIR, HELIOS_REPO_ROOT

class GitOpsInput(BaseModel):
    action: str = Field(
        ...,
        description="The git action to perform: 'status', 'diff', 'log', 'branch', 'show', 'commit'."
    )
    repo_path: Optional[str] = Field(
        default=None,
        description="Optional repository root path. Defaults to HELIOS project directory."
    )
    args: Optional[List[str]] = Field(
        default=None,
        description="Additional arguments (e.g. ['--stat'], ['-n', '5'], ['HEAD~1'])."
    )
    commit_message: Optional[str] = Field(
        default=None,
        description="Commit message when action='commit'."
    )

class GitOpsTool(BaseTool):
    """
    Direct, sandboxed Git operations tool for assistant and coding agents.
    """
    def __init__(self, permission_manager: Optional[PermissionManager] = None):
        self.permission_manager = permission_manager

    @property
    def name(self) -> str:
        return "git_ops"

    @property
    def aliases(self) -> List[str]:
        return ["GitOpsTool", "git"]

    @property
    def description(self) -> str:
        return (
            "Perform safe Git repository operations: query status, diffs, branch info, "
            "commit logs, and commit changes with permission oversight."
        )

    @property
    def input_schema(self) -> type[BaseModel]:
        return GitOpsInput

    @property
    def requires_permission(self) -> bool:
        return True

    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        action = kwargs.get("action", "").lower().strip()
        default_repo = HELIOS_REPO_ROOT if os.path.exists(os.path.join(HELIOS_REPO_ROOT, ".git")) else HELIOS_DIR
        repo_path = kwargs.get("repo_path") or str(default_repo)
        extra_args = kwargs.get("args") or []
        commit_message = kwargs.get("commit_message")

        if not os.path.isdir(repo_path):
            return (f"Error: Directory '{repo_path}' does not exist.", self.name)

        if not os.path.exists(os.path.join(repo_path, ".git")):
            return (f"Error: Directory '{repo_path}' is not a valid git repository.", self.name)

        # Enforce zero-trust approval for state-modifying actions
        if action == "commit":
            if not commit_message:
                return ("Error: 'commit_message' is required for action='commit'.", self.name)
            # Check approval
            if self.permission_manager:
                perm = self.permission_manager.approval_manager.is_approved(user_id, "git_commit", repo_path)
                if not perm:
                    return (f"APPROVAL_REQUIRED::git_commit::{repo_path}", self.name)

        allowed_actions = {
            "status": ["status", "--short"],
            "diff": ["diff"],
            "log": ["log", "-n", "10", "--oneline"],
            "branch": ["branch", "-a"],
            "show": ["show", "--stat"],
            "commit": ["commit", "-m", commit_message or ""]
        }

        if action not in allowed_actions:
            return (
                f"Error: Unsupported git action '{action}'. "
                f"Supported actions are: {list(allowed_actions.keys())}",
                self.name
            )

        cmd = ["git"] + allowed_actions[action]
        # Append safe user args for read actions
        if action != "commit" and extra_args:
            # Filter dangerous flags
            safe_args = [a for a in extra_args if not a.startswith("--exec") and ";" not in a and "&" not in a]
            cmd.extend(safe_args)

        try:
            res = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30.0,
                check=False
            )
            output = res.stdout if res.returncode == 0 else (res.stderr or res.stdout)
            if not output.strip():
                output = f"Git {action} completed successfully with empty output."
            
            # Truncate very large outputs to preserve context
            lines = output.splitlines()
            if len(lines) > 200:
                output = "\n".join(lines[:200]) + f"\n\n... [truncated {len(lines) - 200} lines] ..."

            return (output.strip(), self.name)
        except subprocess.TimeoutExpired:
            return ("Error: Git command timed out after 30 seconds.", self.name)
        except Exception as e:
            return (f"Error executing git command: {e}", self.name)
