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


class SelfModificationSkill(BaseSkill):
    """
    Skill that enables HELIOS to experiment on its own editable components.
    
    The LLM can:
      - Create experiments
      - Copy/write files into experiment workspaces
      - Run tests
      - Request human review
    
    The LLM CANNOT:
      - Approve experiments
      - Deploy experiments
      - Roll back experiments
      - Modify protected system zones
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
            r"run experiment tests",
            r"evaluate experiment",
            r"run.*benchmark"
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
                    f"({exp['files_count']} files)"
                )
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
