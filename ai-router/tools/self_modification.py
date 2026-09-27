from typing import Tuple, Optional, Literal
from pydantic import BaseModel, Field, model_validator

from tools.base import BaseTool
from security.permissions import PermissionManager
from skills.self_modification.workspace import ExperimentWorkspace
from skills.self_modification.models import ExperimentStatus
from db import get_db

class SelfModificationInput(BaseModel):
    action: Literal[
        "list_experiments",
        "show_experiment",
        "create_experiment",
        "copy_file",
        "write_file",
        "evaluate",
        "discard"
    ] = Field(description="The self-modification action to perform.")
    
    experiment_id: Optional[str] = Field(default=None, description="The ID of the experiment. Required for all actions except list_experiments and create_experiment.")
    objective: Optional[str] = Field(default=None, description="The objective of the new experiment. Required for create_experiment.")
    target_path: Optional[str] = Field(default=None, description="The target file path. Required for copy_file and write_file.")
    content: Optional[str] = Field(default=None, description="The file content to write. Required for write_file.")

    @model_validator(mode="after")
    def validate_action_requirements(self):
        if self.action == "show_experiment" and not self.experiment_id:
            raise ValueError("experiment_id is required for show_experiment")
        if self.action == "create_experiment" and not self.objective:
            raise ValueError("objective is required for create_experiment")
        if self.action == "copy_file":
            if not self.experiment_id or not self.target_path:
                raise ValueError("experiment_id and target_path are required for copy_file")
        if self.action == "write_file":
            if not self.experiment_id or not self.target_path or not self.content:
                raise ValueError("experiment_id, target_path, and content are required for write_file")
        if self.action in ("evaluate", "discard") and not self.experiment_id:
            raise ValueError(f"experiment_id is required for {self.action}")
        return self

class SelfModificationTool(BaseTool):
    """
    Tool that enables HELIOS to experiment on its own editable components.
    
    The LLM can:
      - Create experiments
      - Copy production files into experiment workspaces
      - Write modified code into experiment workspaces
      - Inspect experiment status
      - Run tests and benchmarks (evaluation)
      - Request human review
      - Discard experiments
    """
    
    def __init__(self, permission_manager: PermissionManager):
        self.permission_manager = permission_manager
        self.workspace = ExperimentWorkspace(permission_manager)

    @property
    def name(self) -> str:
        return "SelfModificationTool"

    @property
    def description(self) -> str:
        return (
            "Enables HELIOS to perform self-modification experiments safely. "
            "Supports actions: list_experiments, show_experiment, create_experiment, "
            "copy_file, write_file, evaluate, discard."
        )

    @property
    def input_schema(self) -> type[BaseModel]:
        return SelfModificationInput

    @property
    def requires_permission(self) -> bool:
        return True

    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        # Validate Pydantic model
        try:
            args = SelfModificationInput(**kwargs)
        except Exception as e:
            return (f"Invalid arguments: {e}", self.name)
            
        action = args.action

        if action == "list_experiments":
            experiments = self.workspace.list_experiments()
            if not experiments:
                return ("No experiments found.", self.name)
            lines = ["**Active Experiments:**\n"]
            for exp in experiments:
                lines.append(
                    f"- **{exp['experiment_id']}** — {exp['objective']} "
                    f"[{exp['status']}] ({exp['risk_level']}) "
                    f"({len(exp.get('files', []))} files)"
                )
            return ("\n".join(lines), self.name)

        elif action == "show_experiment":
            metadata = self.workspace.load_metadata(args.experiment_id)
            if metadata is None:
                return (f"Experiment '{args.experiment_id}' not found.", self.name)

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
                    (args.experiment_id,)
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

            return ("\n".join(lines), self.name)

        elif action == "create_experiment":
            metadata = self.workspace.create_experiment(args.objective)

            self.permission_manager.log_operation(
                user_id,
                "self_modification", "create_experiment",
                metadata.experiment_id, "APPROVED", "SUCCESS"
            )

            return (
                f"✅ Experiment **{metadata.experiment_id}** created.\n"
                f"Objective: {metadata.objective}\n"
                f"Status: {metadata.status.value}\n\n"
                f"You can now copy or write files into this experiment.",
                self.name
            )

        elif action == "copy_file":
            success, msg = self.workspace.copy_file_to_experiment(args.experiment_id, args.target_path)

            self.permission_manager.log_operation(
                user_id,
                "self_modification", "copy_file_to_experiment",
                f"{args.experiment_id}:{args.target_path}", "APPROVED" if success else "DENIED",
                "SUCCESS" if success else "FAILED"
            )

            return (msg, self.name)

        elif action == "write_file":
            success, msg = self.workspace.write_experiment_file(args.experiment_id, args.target_path, args.content)

            self.permission_manager.log_operation(
                user_id,
                "self_modification", "write_experiment_file",
                f"{args.experiment_id}:{args.target_path}", "APPROVED" if success else "DENIED",
                "SUCCESS" if success else "FAILED"
            )

            return (msg, self.name)

        elif action == "evaluate":
            success, msg = self.workspace.evaluate_experiment(args.experiment_id)

            self.permission_manager.log_operation(
                user_id,
                "self_modification", "evaluate_experiment",
                args.experiment_id, "APPROVED",
                "SUCCESS" if success else "FAILED"
            )

            return (msg, self.name)

        elif action == "discard":
            success, msg = self.workspace.discard_experiment(args.experiment_id)
            return (msg, self.name)

        return ("Invalid action.", self.name)
