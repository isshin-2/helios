"""
HELIOS — Coder Agent
Genuine tool-using coding agent executing an iterative loop:
inspect → plan locally → edit → test → fix → return structured artifacts.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from agents.base import AgentResult, AgentStatus, BaseAgent
from core.coding_runtime import CodingContext
from core.model_router import model_router
from gateway.host_gateway import HostGateway
from gateway.tool_gateway import ToolGateway
from providers.base import BaseProvider
from security.permissions import PermissionManager, validate_path

logger = logging.getLogger("helios.agents.coder")


class CoderAgent(BaseAgent):
    """
    Iterative coding agent with local tool loop and safety bounds.
    """

    def __init__(
        self,
        provider: BaseProvider,
        tool_gateway: Optional[ToolGateway] = None,
        host_gateway: Optional[HostGateway] = None,
        permission_manager: Optional[PermissionManager] = None,
        max_iterations: int = 12,
        max_file_changes: int = 30,
        max_command_time_seconds: int = 120,
        agent_id: Optional[str] = None,
    ):
        super().__init__(agent_id)
        self.provider = provider
        self.tool_gateway = tool_gateway
        self.host_gateway = host_gateway
        self.permission_manager = permission_manager or PermissionManager()
        self.max_iterations = max_iterations
        self.max_file_changes = max_file_changes
        self.max_command_time_seconds = max_command_time_seconds

    @property
    def agent_type(self) -> str:
        return "coder"

    def _execute_read_file(self, workspace_root: str, file_path: str) -> str:
        """Read a file within the workspace safely."""
        target = os.path.normpath(os.path.join(workspace_root, file_path)) if not os.path.isabs(file_path) else os.path.normpath(file_path)
        if not target.startswith(os.path.normpath(workspace_root)):
            return f"Error: Cannot access file outside workspace: {file_path}"
        if not os.path.exists(target):
            return f"Error: File not found: {file_path}"
        try:
            with open(target, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return content if len(content) <= 30000 else content[:30000] + "\n...[truncated]"
        except Exception as e:
            return f"Error reading {file_path}: {e}"

    def _execute_write_file(self, workspace_root: str, file_path: str, content: str) -> str:
        """Write content to file within workspace safely."""
        target = os.path.normpath(os.path.join(workspace_root, file_path)) if not os.path.isabs(file_path) else os.path.normpath(file_path)
        if not target.startswith(os.path.normpath(workspace_root)):
            return f"Error: Cannot write outside workspace: {file_path}"
        # Validate against HELIOS core protected paths
        if not self.permission_manager.validate_path_access(target):
            return f"Error: Write operation blocked by security policy for {file_path}"
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote {len(content)} characters to {file_path}"
        except Exception as e:
            return f"Error writing {file_path}: {e}"

    def _execute_patch_file(self, workspace_root: str, file_path: str, search_block: str, replace_block: str) -> str:
        """Surgically edit file by replacing an exact text block."""
        target = os.path.normpath(os.path.join(workspace_root, file_path)) if not os.path.isabs(file_path) else os.path.normpath(file_path)
        if not target.startswith(os.path.normpath(workspace_root)):
            return f"Error: Path outside workspace: {file_path}"
        if not self.permission_manager.validate_path_access(target):
            return f"Error: Write operation blocked by security policy for {file_path}"
        if not os.path.exists(target):
            return f"Error: File {file_path} not found"
        try:
            with open(target, "r", encoding="utf-8") as f:
                content = f.read()
            if search_block not in content:
                # Try normalized comparison
                norm_c = content.replace("\r\n", "\n")
                norm_s = search_block.replace("\r\n", "\n")
                if norm_s in norm_c:
                    new_content = norm_c.replace(norm_s, replace_block.replace("\r\n", "\n"), 1)
                else:
                    return f"Error: search_block not found in {file_path}. Ensure exact match."
            else:
                new_content = content.replace(search_block, replace_block, 1)

            with open(target, "w", encoding="utf-8") as f:
                f.write(new_content)
            return f"Successfully patched {file_path}"
        except Exception as e:
            return f"Error patching {file_path}: {e}"

    def _execute_run_command(self, workspace_root: str, command: str) -> str:
        """Executes a command safely inside the isolated workspace."""
        base_cmd = command.split()[0] if command.strip() else ""
        if not self.permission_manager.is_command_allowed(base_cmd):
            return f"Error: Command '{base_cmd}' is blocked by HELIOS security policy."

        try:
            res = subprocess.run(
                command,
                shell=True,
                cwd=workspace_root,
                capture_output=True,
                text=True,
                timeout=min(self.max_command_time_seconds, 60),
            )
            out = res.stdout
            if res.stderr:
                out += f"\nSTDERR:\n{res.stderr}"
            return f"Exit code {res.returncode}\n{out}"
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {self.max_command_time_seconds}s"
        except Exception as e:
            return f"Command execution failed: {e}"

    def _parse_action(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Extract tool invocation from LLM output."""
        text = response_text.strip()
        # Look for JSON block
        m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        m = re.search(r"(\{[\s\S]*\})", text)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        return None

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

        # Ensure directory is normalized
        workspace_root = os.path.abspath(workspace_root)

        model_name, options = await model_router.prepare_model_for_agent("coder", self.provider)

        plan = context.get("plan") or (coding_ctx.plan if coding_ctx else None) or {}
        arch = context.get("architecture") or (coding_ctx.architecture if coding_ctx else None) or {}
        relevant_files = (coding_ctx.relevant_files if coding_ctx else []) or context.get("relevant_files", [])

        system_prompt = f"""You are the HELIOS Lead Coder Agent working in an isolated workspace.
Your task is to implement the given objective using tool actions.

WORKSPACE: {workspace_root}
OBJECTIVE: {objective}
PLAN: {json.dumps(plan)}
ARCHITECTURE: {json.dumps(arch)}
RELEVANT FILES: {json.dumps(relevant_files)}

In each step, respond with a JSON action:
1. Read a file:
   {{"action": "read_file", "path": "relative/path/to/file.py"}}
2. Patch a file:
   {{"action": "patch_file", "path": "path.py", "search_block": "exact code", "replace_block": "new code"}}
3. Write/create a file:
   {{"action": "write_file", "path": "path.py", "content": "full content"}}
4. Run a test/command:
   {{"action": "run_command", "command": "pytest tests/test_foo.py"}}
5. Finish task:
   {{"action": "finish", "summary": "Detailed summary of completed changes"}}

Output strictly valid JSON for your chosen action.
"""

        messages = [{"role": "system", "content": system_prompt}]
        modified_files: Set[str] = set()
        iterations = 0
        final_summary = ""

        while iterations < self.max_iterations:
            iterations += 1

            # Format current iteration prompt
            user_msg = f"Iteration {iterations}/{self.max_iterations}. State your next action as JSON."
            messages.append({"role": "user", "content": user_msg})

            try:
                # Chat or generate
                if hasattr(self.provider, "chat"):
                    resp = await self.provider.chat(
                        model=model_name,
                        messages=messages,
                        options=options,
                    )
                    content = resp.get("message", {}).get("content", "") or resp.get("response", "")
                else:
                    combined = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
                    resp = await self.provider.generate(model=model_name, prompt=combined, options=options)
                    content = resp.get("response", "")

                action_obj = self._parse_action(content)
                if not action_obj or "action" not in action_obj:
                    # Provide feedback and retry
                    messages.append({"role": "assistant", "content": content})
                    messages.append({"role": "user", "content": "Invalid response format. Please provide valid JSON with an 'action' field."})
                    continue

                action = action_obj.get("action")
                messages.append({"role": "assistant", "content": json.dumps(action_obj)})

                if action == "finish":
                    final_summary = action_obj.get("summary", "Coding objective completed.")
                    break

                elif action == "read_file":
                    p = action_obj.get("path", "")
                    tool_res = self._execute_read_file(workspace_root, p)
                    messages.append({"role": "user", "content": f"Tool Result (read_file):\n{tool_res}"})

                elif action == "write_file":
                    p = action_obj.get("path", "")
                    c = action_obj.get("content", "")
                    tool_res = self._execute_write_file(workspace_root, p, c)
                    modified_files.add(p)
                    messages.append({"role": "user", "content": f"Tool Result (write_file):\n{tool_res}"})

                elif action == "patch_file":
                    p = action_obj.get("path", "")
                    s = action_obj.get("search_block", "")
                    r = action_obj.get("replace_block", "")
                    tool_res = self._execute_patch_file(workspace_root, p, s, r)
                    modified_files.add(p)
                    messages.append({"role": "user", "content": f"Tool Result (patch_file):\n{tool_res}"})

                elif action == "run_command":
                    cmd = action_obj.get("command", "")
                    tool_res = self._execute_run_command(workspace_root, cmd)
                    messages.append({"role": "user", "content": f"Tool Result (run_command):\n{tool_res}"})

                else:
                    messages.append({"role": "user", "content": f"Unknown action: {action}"})

            except Exception as e:
                self.logger.error(f"Error during coder iteration {iterations}: {e}")
                messages.append({"role": "user", "content": f"Execution error: {str(e)}"})

        if not final_summary:
            final_summary = f"Coder reached iteration limit ({self.max_iterations}). Modified {len(modified_files)} files."

        # Update CodingContext
        if coding_ctx:
            coding_ctx.changed_files = sorted(list(set(coding_ctx.changed_files + list(modified_files))))
            coding_ctx.artifacts.extend(list(modified_files))

        return self._make_result(
            status=AgentStatus.SUCCESS if modified_files or "completed" in final_summary.lower() else AgentStatus.PARTIAL,
            summary=final_summary,
            detail=f"Iterations: {iterations}. Modified files: {sorted(list(modified_files))}",
            artifacts=sorted(list(modified_files)),
            evidence={
                "iterations": iterations,
                "modified_files": sorted(list(modified_files)),
                "workspace": workspace_root,
            },
            started_at=started_at,
            confidence=0.9 if modified_files else 0.6,
        )
