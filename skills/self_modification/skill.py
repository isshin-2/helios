"""
HELIOS — Self-Modification Skill
==================================
Provides controlled self-modification capabilities to HELIOS.

The LLM can create experiments, modify files, run tests, and request review.
It can NEVER approve, deploy, or roll back — those are human-only actions.
"""

import re
from typing import Tuple

from skills.base import BaseSkill
from security.permissions import PermissionManager
from .workspace import ExperimentWorkspace
from .models import ExperimentStatus, RiskLevel
from db import get_db


class SelfModificationSkill(BaseSkill):
    """
    Skill that enables HELIOS to experiment on its own editable components.
    
    The LLM can:
      - Create experiments
      - Copy production files into experiment workspaces
      - Write modified code into experiment workspaces
      - Inspect experiment status
      - Run tests and benchmarks (evaluation)
      - Request human review
      - Discard experiments
    
    The LLM CANNOT:
      - Approve experiments
      - Deploy experiments
      - Roll back experiments
      - Modify protected system zones
      - Directly modify authoritative experiment state
      - Directly modify the experiment database
    """

    def __init__(self, permission_manager: PermissionManager):
        self.permission_manager = permission_manager
        self.workspace = ExperimentWorkspace(permission_manager)

    def match(self, prompt: str) -> bool:
        """Match prompts related to self-modification."""
        prompt_lower = prompt.lower().strip()
        patterns = [
            r"self[- ]?modif",
            r"create experiment",
            r"new experiment",
            r"improve (my|your|the) (skill|prompt|tool|code)",
            r"modify (skill|prompt|frontend|static)",
            r"experiment on",
            r"optimize (skill|prompt|routing)",
            r"list experiments",
            r"show experiments",
            r"show experiment\b",
            r"run experiment tests",
            r"evaluate experiment",
            r"run.*benchmark",
            r"copy.*(?:file|to).*experiment",
            r"copy.*experiment",
            r"write experiment file",
            r"write.*to experiment",
            r"discard experiment",
        ]
        return any(re.search(p, prompt_lower) for p in patterns)

    async def execute(self, prompt: str, **kwargs) -> Tuple[str, str]:
        """
        Route self-modification requests to the appropriate workspace action.
        
        The LLM calls this method via the skill system. It can only trigger
        LLM-allowed actions. Approve/deploy/rollback are NOT exposed here.
        """
        prompt_lower = prompt.lower().strip()

        # ── List experiments ─────────────────────────────────────────
        if re.search(r"list experiments|show experiments", prompt_lower):
            experiments = self.workspace.list_experiments()
            if not experiments:
                return ("No experiments found.", "self_modification")
            lines = ["**Active Experiments:**\n"]
            for exp in experiments:
                lines.append(
                    f"- **{exp['experiment_id']}** — {exp['objective']} "
                    f"[{exp['status']}] ({exp['risk_level']}) "
                    f"({len(exp.get('files', []))} files)"
                )
            return ("\n".join(lines), "self_modification")

        # ── Show single experiment ───────────────────────────────────
        if re.search(r"show experiment\b", prompt_lower):
            experiment_id = self._extract_experiment_id(prompt)
            if not experiment_id:
                return ("Please specify an experiment ID.", "self_modification")

            metadata = self.workspace.load_metadata(experiment_id)
            if metadata is None:
                return (f"Experiment '{experiment_id}' not found.", "self_modification")

            lines = [
                f"**Experiment: {metadata.experiment_id}**\n",
                f"**Objective:** {metadata.objective}",
                f"**Status:** {metadata.status.value}",
                f"**Risk Level:** {metadata.risk_level.value}",
                f"**Created:** {metadata.created_at}",
                f"**Files:** {len(metadata.files)}",
            ]

            if metadata.files:
                lines.append("\n**Modified Files:**")
                for f in metadata.files:
                    hash_info = f" (baseline: {f.baseline_sha256[:12]}...)" if f.baseline_sha256 else " (new file)"
                    lines.append(f"  - `{f.target}`{hash_info}")

            if metadata.diff_stats:
                stats = metadata.diff_stats
                lines.append(
                    f"\n**Diff Stats:** {stats.get('files_changed', 0)} files changed, "
                    f"+{stats.get('lines_added', 0)} / -{stats.get('lines_removed', 0)}"
                )

            if metadata.evaluation:
                ev = metadata.evaluation
                lines.append(f"\n**Evaluation:** {ev.classification}")
                if ev.comparisons:
                    lines.append("\n| Metric | Baseline | Experiment | Change | Result |")
                    lines.append("|--------|----------|------------|--------|--------|")
                    for cmp in ev.comparisons.values():
                        b_mean = f"{cmp.baseline.mean:.2f}" if cmp.baseline.mean is not None else "--"
                        e_mean = f"{cmp.experiment.mean:.2f}" if cmp.experiment.mean is not None else "--"
                        change = f"{cmp.change_percent:+.1f}%" if cmp.change_percent is not None else "--"
                        lines.append(f"| {cmp.metric} | {b_mean} | {e_mean} | {change} | {cmp.result} |")

                if ev.critical_regressions:
                    lines.append(f"\n⚠️ **Critical Regressions:** {', '.join(ev.critical_regressions)}")

            if metadata.tests:
                test_status = "✅ Passed" if metadata.tests.get("passed") else "❌ Failed"
                lines.append(f"\n**Tests:** {test_status}")

            # Fetch audit trail
            try:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT timestamp, actor, action, previous_state, new_state, reason "
                    "FROM experiment_audit_log WHERE experiment_id = ? ORDER BY timestamp DESC LIMIT 5",
                    (experiment_id,)
                )
                audit_rows = cursor.fetchall()
                conn.close()
                if audit_rows:
                    lines.append("\n**Recent Activity:**")
                    for row in audit_rows:
                        prev = row["previous_state"] or "—"
                        new = row["new_state"] or "—"
                        reason = row["reason"] or ""
                        lines.append(f"  - [{row['actor']}] {prev} → {new} {reason}")
            except Exception:
                pass  # Read-only, non-critical

            return ("\n".join(lines), "self_modification")

        # ── Create experiment ────────────────────────────────────────
        if re.search(r"create experiment|new experiment", prompt_lower):
            # Extract objective from prompt
            objective = prompt.strip()
            # Try to extract a quoted objective
            match = re.search(r'["\'](.+?)["\']', prompt)
            if match:
                objective = match.group(1)
            elif ":" in prompt:
                objective = prompt.split(":", 1)[1].strip()

            metadata = self.workspace.create_experiment(objective)

            self.permission_manager.log_operation(
                kwargs.get("user_id", 0),
                "self_modification", "create_experiment",
                metadata.experiment_id, "APPROVED", "SUCCESS"
            )

            return (
                f"✅ Experiment **{metadata.experiment_id}** created.\n"
                f"Objective: {metadata.objective}\n"
                f"Status: {metadata.status.value}\n\n"
                f"You can now copy or write files into this experiment.",
                "self_modification"
            )

        # ── Copy file to experiment ──────────────────────────────────
        if re.search(r"copy.*(?:file|to).*experiment|copy.*experiment", prompt_lower):
            experiment_id = self._extract_experiment_id(prompt)
            if not experiment_id:
                return ("Please specify an experiment ID.", "self_modification")

            # Extract the file path from the prompt
            file_path = self._extract_file_path(prompt)
            if not file_path:
                return (
                    "Please specify a file path to copy.\n"
                    "Example: `copy router/classifier.py to experiment change_20260820_001_123456`",
                    "self_modification"
                )

            success, msg = self.workspace.copy_file_to_experiment(experiment_id, file_path)

            self.permission_manager.log_operation(
                kwargs.get("user_id", 0),
                "self_modification", "copy_file_to_experiment",
                f"{experiment_id}:{file_path}", "APPROVED" if success else "DENIED",
                "SUCCESS" if success else "FAILED"
            )

            return (msg, "self_modification")

        # ── Write experiment file ────────────────────────────────────
        if re.search(r"write experiment file|write.*to experiment", prompt_lower):
            experiment_id = self._extract_experiment_id(prompt)
            if not experiment_id:
                return ("Please specify an experiment ID.", "self_modification")

            file_path = self._extract_file_path(prompt)
            if not file_path:
                return (
                    "Please specify a target file path.\n"
                    "Example: `write experiment file router/classifier.py in change_20260820_001_123456`",
                    "self_modification"
                )

            # Extract code content from the prompt (everything in a code block, or after the file path)
            content = self._extract_code_content(prompt)
            if not content:
                return (
                    "Please include the file content in a code block.\n"
                    "Example:\n"
                    "```\n"
                    "write experiment file router/classifier.py in change_20260820_001_123456\n"
                    "```python\n"
                    "# your code here\n"
                    "```",
                    "self_modification"
                )

            success, msg = self.workspace.write_experiment_file(experiment_id, file_path, content)

            self.permission_manager.log_operation(
                kwargs.get("user_id", 0),
                "self_modification", "write_experiment_file",
                f"{experiment_id}:{file_path}", "APPROVED" if success else "DENIED",
                "SUCCESS" if success else "FAILED"
            )

            return (msg, "self_modification")

        # ── Evaluate experiment ──────────────────────────────────────
        if re.search(r"evaluate.*experiment|run.*benchmark|test.*experiment", prompt_lower):
            experiment_id = self._extract_experiment_id(prompt)
            if not experiment_id:
                return ("Please specify an experiment ID.", "self_modification")

            success, msg = self.workspace.evaluate_experiment(experiment_id)

            self.permission_manager.log_operation(
                kwargs.get("user_id", 0),
                "self_modification", "evaluate_experiment",
                experiment_id, "APPROVED",
                "SUCCESS" if success else "FAILED"
            )

            return (msg, "self_modification")

        # ── Discard experiment ───────────────────────────────────────
        if re.search(r"discard experiment", prompt_lower):
            experiment_id = self._extract_experiment_id(prompt)
            if not experiment_id:
                return ("Please specify an experiment ID.", "self_modification")

            success, msg = self.workspace.discard_experiment(experiment_id)
            return (msg, "self_modification")

        # ── Default: explain capabilities ────────────────────────────
        return (
            "**Self-Modification Capabilities:**\n\n"
            "I can:\n"
            "- `create experiment: <objective>` — Start a new experiment\n"
            "- `list experiments` — Show all experiments\n"
            "- `show experiment <id>` — View experiment details\n"
            "- `copy <file> to experiment <id>` — Copy a production file\n"
            "- `write experiment file <file> in <id>` — Write modified code\n"
            "- `evaluate experiment <id>` — Test, benchmark, and prepare for review\n"
            "- `discard experiment <id>` — Abandon an experiment\n\n"
            "After I prepare an experiment, you can review and approve it "
            "from the Self-Modification panel in the UI.",
            "self_modification"
        )

    def _extract_experiment_id(self, prompt: str) -> str:
        """Extract an experiment ID from a prompt string."""
        match = re.search(r"(change_\d{8}_\d{3}_\d{6})", prompt)
        if match:
            return match.group(1)
        # Try simpler pattern
        match = re.search(r"(change_\d{8}_\d+)", prompt)
        if match:
            return match.group(1)
        return ""

    def _extract_file_path(self, prompt: str) -> str:
        """Extract a file path from a prompt string."""
        # Match common file path patterns (with forward or back slashes and extensions)
        match = re.search(r'(?:file\s+|copy\s+)([a-zA-Z0-9_/.\\-]+\.\w+)', prompt)
        if match:
            return match.group(1).replace("\\", "/")
        # Try to find any path-like pattern with an extension
        match = re.search(r'(?<!\w)([a-zA-Z0-9_]+(?:/[a-zA-Z0-9_]+)*(?:/[a-zA-Z0-9_.]+\.\w+))', prompt)
        if match:
            return match.group(1)
        # Try bare filename
        match = re.search(r'(?<!\w)([a-zA-Z0-9_]+\.\w{1,4})(?!\w)', prompt)
        if match:
            return match.group(1)
        return ""

    def _extract_code_content(self, prompt: str) -> str:
        """Extract code content from a prompt, looking for code blocks."""
        # Look for fenced code blocks
        match = re.search(r'```(?:\w+)?\n(.*?)```', prompt, re.DOTALL)
        if match:
            return match.group(1).strip()
        # Look for indented content after a newline
        lines = prompt.split("\n")
        code_lines = []
        in_code = False
        for line in lines:
            if in_code:
                code_lines.append(line)
            elif line.startswith("    ") or line.startswith("\t"):
                in_code = True
                code_lines.append(line)
        if code_lines:
            return "\n".join(code_lines).strip()
        return ""
