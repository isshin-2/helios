"""
HELIOS — Self-Modification Workspace Manager
===============================================
Manages experiment directories, file copying, diff generation,
backup/restore, and deployment.

All filesystem mutations go through PermissionManager.
The workspace itself never bypasses the security boundary.
"""

import difflib
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

from security.permissions import PermissionManager, HELIOS_DIR
from .models import (
    ExperimentMetadata, ExperimentStatus, FileEntry,
    RiskLevel, compute_sha256, EvaluationSummary,
    Actor, transition_experiment, BenchmarkComparison, BenchmarkResult
)
from .benchmark import BenchmarkRunner, BENCHMARK_REGISTRY, build_evaluation_summary
from .validator import (
    classify_risk, validate_experiment_source, validate_experiment_target,
)
from db import get_db

logger = logging.getLogger(__name__)

EXPERIMENTS_DIR = os.path.join(HELIOS_DIR, "experiments")


# ─── Experiment ID Generation ───────────────────────────────────────────────

def generate_experiment_id() -> str:
    """Generate a unique, timestamped experiment ID."""
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y%m%d")
    time_suffix = now.strftime("%H%M%S")

    # Find the next sequential number for today by checking DB instead of filesystem
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM experiments WHERE id LIKE ?", (f"change_{date_str}_%",))
    rows = cursor.fetchall()
    conn.close()
    
    seq = len(rows) + 1
    return f"change_{date_str}_{seq:03d}_{time_suffix}"


# ─── Workspace Operations ───────────────────────────────────────────────────

class ExperimentWorkspace:
    def __init__(self, permission_manager: PermissionManager):
        self.permission_manager = permission_manager

    # ── Create ───────────────────────────────────────────────────────────

    def create_experiment(self, objective: str,
                          risk_level: RiskLevel = RiskLevel.LOW) -> ExperimentMetadata:
        """Create a new isolated experiment workspace."""
        experiment_id = generate_experiment_id()
        exp_dir = os.path.join(EXPERIMENTS_DIR, experiment_id)

        os.makedirs(os.path.join(exp_dir, "modified"), exist_ok=True)
        os.makedirs(os.path.join(exp_dir, "backup"), exist_ok=True)
        os.makedirs(os.path.join(exp_dir, "tests"), exist_ok=True)

        metadata = ExperimentMetadata(
            experiment_id=experiment_id,
            objective=objective,
            risk_level=risk_level,
        )
        self._save_metadata(metadata)
        
        # Log transition
        transition_experiment(experiment_id, ExperimentStatus.DRAFT, Actor.SYSTEM, "Created experiment")

        logger.info(f"Created experiment: {experiment_id}")
        return metadata

    # ── File Operations ──────────────────────────────────────────────────

    def copy_file_to_experiment(self, experiment_id: str,
                                 production_target: str) -> Tuple[bool, str]:
        metadata = self.load_metadata(experiment_id)
        if metadata is None:
            return False, f"Experiment '{experiment_id}' not found."

        if metadata.status not in (ExperimentStatus.DRAFT, ExperimentStatus.EXPERIMENTING):
            return False, f"Cannot modify files in status '{metadata.status.value}'."

        abs_target = os.path.join(HELIOS_DIR, production_target)
        if not validate_experiment_target(abs_target, self.permission_manager):
            return False, "This operation is blocked because the target belongs to a protected HELIOS system zone."

        exp_dir = os.path.join(EXPERIMENTS_DIR, experiment_id)
        source_path = Path(abs_target).resolve(strict=False)
        dest_path = (Path(exp_dir) / "modified" / production_target).resolve(strict=False)

        # SECURITY: Path Traversal Check
        if not dest_path.is_relative_to((Path(exp_dir) / "modified").resolve(strict=False)):
            return False, "Path traversal detected."

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        baseline_hash = None
        if source_path.exists():
            shutil.copy2(str(source_path), str(dest_path))
            baseline_hash = compute_sha256(str(source_path))
        else:
            dest_path.touch()

        existing_entry = next((f for f in metadata.files if f.target == production_target), None)
        if not existing_entry:
            file_entry = FileEntry(
                source=f"modified/{production_target}",
                target=production_target,
            )
            file_entry.baseline_sha256 = baseline_hash
            metadata.files.append(file_entry)
            
            file_risk = classify_risk(production_target)
            if file_risk.value > metadata.risk_level.value:
                metadata.risk_level = file_risk
        else:
            existing_entry.baseline_sha256 = baseline_hash

        self._save_metadata(metadata)
        
        if metadata.status == ExperimentStatus.DRAFT:
            transition_experiment(experiment_id, ExperimentStatus.EXPERIMENTING, Actor.LLM, "Added file")

        return True, f"File '{production_target}' copied to experiment."

    def write_experiment_file(self, experiment_id: str,
                               production_target: str,
                               content: str) -> Tuple[bool, str]:
        metadata = self.load_metadata(experiment_id)
        if metadata is None:
            return False, f"Experiment '{experiment_id}' not found."

        if metadata.status not in (ExperimentStatus.DRAFT, ExperimentStatus.EXPERIMENTING):
            return False, f"Cannot modify files in status '{metadata.status.value}'."

        abs_target = os.path.join(HELIOS_DIR, production_target)
        if not validate_experiment_target(abs_target, self.permission_manager):
            return False, "This operation is blocked because the target belongs to a protected HELIOS system zone."

        exp_dir = os.path.join(EXPERIMENTS_DIR, experiment_id)
        dest_path = (Path(exp_dir) / "modified" / production_target).resolve(strict=False)
        
        # SECURITY: Path Traversal Check
        if not dest_path.is_relative_to((Path(exp_dir) / "modified").resolve(strict=False)):
            return False, "Path traversal detected."

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(content, encoding="utf-8")

        existing_entry = next((f for f in metadata.files if f.target == production_target), None)
        if not existing_entry:
            file_entry = FileEntry(
                source=f"modified/{production_target}",
                target=production_target,
            )
            if os.path.exists(abs_target):
                file_entry.baseline_sha256 = compute_sha256(abs_target)
                
            metadata.files.append(file_entry)
            file_risk = classify_risk(production_target)
            if file_risk.value > metadata.risk_level.value:
                metadata.risk_level = file_risk

        self._save_metadata(metadata)

        if metadata.status == ExperimentStatus.DRAFT:
            transition_experiment(experiment_id, ExperimentStatus.EXPERIMENTING, Actor.LLM, "Wrote file")

        return True, f"File '{production_target}' written to experiment."

    # ── Testing ──────────────────────────────────────────────────────────

    def _run_tests(self, metadata: ExperimentMetadata) -> Tuple[bool, str]:
        # Run pytest
        from core.platform.process import launch_isolated_process
        try:
            proc = launch_isolated_process(
                [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
                cwd=HELIOS_DIR
            )
            stdout, stderr = proc.communicate(timeout=120)
            test_output = stdout + stderr
            tests_passed = proc.returncode == 0
        except subprocess.TimeoutExpired:
            test_output = "Test execution timed out after 120 seconds."
            tests_passed = False
        except Exception as e:
            test_output = f"Test execution failed: {e}"
            tests_passed = False

        metadata.tests = {
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "passed": tests_passed,
            "output": test_output[:10000],  # Cap output
            "returncode": proc.returncode if 'proc' in dir() else -1,
        }

        status_msg = "PASSED" if tests_passed else "FAILED"
        return tests_passed, f"Tests {'passed' if tests_passed else 'failed'}. Status: {status_msg}"

    # ── Evaluation & Benchmarking ─────────────────────────────────────────

    def evaluate_experiment(self, experiment_id: str) -> Tuple[bool, str]:
        metadata = self.load_metadata(experiment_id)
        if metadata is None:
            return False, f"Experiment '{experiment_id}' not found."
            
        if metadata.status != ExperimentStatus.EXPERIMENTING:
            return False, f"Cannot evaluate in status '{metadata.status.value}'. Must be EXPERIMENTING."

        transition_experiment(experiment_id, ExperimentStatus.EVALUATING, Actor.LLM, "Requesting evaluation")
        # Load again to get updated status
        metadata = self.load_metadata(experiment_id)

        tests_passed, tests_msg = self._run_tests(metadata)
        if not tests_passed:
            self._save_metadata(metadata)
            transition_experiment(experiment_id, ExperimentStatus.FAILED, Actor.EVALUATOR, "Functional tests failed")
            return False, f"Evaluation halted because functional tests failed: {tests_msg}"

        if not self._verify_baseline_integrity(metadata):
            self._save_metadata(metadata)
            transition_experiment(experiment_id, ExperimentStatus.SECURITY_VIOLATION, Actor.EVALUATOR, "Baseline integrity violation")
            return False, "Evaluation halted: Production baseline integrity violation (hash mismatch)."

        if not self._verify_experiment_integrity(metadata):
            self._save_metadata(metadata)
            transition_experiment(experiment_id, ExperimentStatus.FAILED, Actor.EVALUATOR, "Experiment integrity violation")
            return False, "Evaluation halted: Experiment workspace has been tampered with."
            
        baseline_results, exp_results = self.run_benchmarks(metadata)
        
        if not self._verify_baseline_integrity(metadata):
            self._save_metadata(metadata)
            transition_experiment(experiment_id, ExperimentStatus.SECURITY_VIOLATION, Actor.EVALUATOR, "Baseline integrity violation during benchmarking")
            return False, "Evaluation halted: Production baseline was modified DURING benchmarking (Security Violation)."
            
        comparisons = self.compare_results(baseline_results, exp_results)
        
        baseline_hash = self._calculate_baseline_hash(metadata)
        summary = self.evaluate_results(comparisons, baseline_hash)
        metadata.evaluation = summary
        
        self._generate_diff(metadata)
        metadata.diff_stats = self._calculate_diff_stats(metadata)
        
        # Save before transitioning to READY_FOR_REVIEW since it requires an evaluation_run entry
        self._save_metadata(metadata)
        
        transition_experiment(experiment_id, ExperimentStatus.READY_FOR_REVIEW, Actor.EVALUATOR, "Evaluation completed")
        metadata = self.load_metadata(experiment_id)
        
        report = self.generate_report(metadata)
        return True, report

    def _verify_baseline_integrity(self, metadata: ExperimentMetadata) -> bool:
        for f in metadata.files:
            prod_path = os.path.join(HELIOS_DIR, f.target)
            if f.baseline_sha256 is None:
                if os.path.exists(prod_path):
                    return False
                continue
            if not os.path.exists(prod_path):
                return False
            current_hash = compute_sha256(prod_path)
            if current_hash != f.baseline_sha256:
                return False
        return True

    def _verify_experiment_integrity(self, metadata: ExperimentMetadata) -> bool:
        exp_dir = os.path.join(EXPERIMENTS_DIR, metadata.experiment_id)
        for f in metadata.files:
            exp_path = os.path.join(exp_dir, f.source)
            if not os.path.exists(exp_path):
                return False
        return True

    def _calculate_baseline_hash(self, metadata: ExperimentMetadata) -> str:
        import hashlib
        h = hashlib.sha256()
        for f in sorted(metadata.files, key=lambda x: x.target):
            if f.baseline_sha256:
                h.update(f.baseline_sha256.encode("utf-8"))
        return h.hexdigest()

    def run_benchmarks(self, metadata: ExperimentMetadata):
        runner = BenchmarkRunner(HELIOS_DIR)
        exp_dir = os.path.join(EXPERIMENTS_DIR, metadata.experiment_id)
        
        baseline_results = {}
        exp_results = {}
        
        for def_id, benchmark_def in BENCHMARK_REGISTRY.items():
            baseline_results[def_id] = runner.run_benchmark(benchmark_def, is_baseline=True)
            exp_results[def_id] = runner.run_benchmark(benchmark_def, is_baseline=False, experiment_dir=exp_dir)
            
        return baseline_results, exp_results

    def compare_results(self, baseline_results, exp_results):
        runner = BenchmarkRunner(HELIOS_DIR)
        comparisons = []
        for def_id, benchmark_def in BENCHMARK_REGISTRY.items():
            if def_id not in baseline_results or def_id not in exp_results:
                continue
            b_res = baseline_results[def_id]
            e_res = exp_results[def_id]
            for m in benchmark_def.metrics:
                if m.name in b_res and m.name in e_res:
                    cmp = runner.evaluate_metric(m, b_res[m.name], e_res[m.name])
                    comparisons.append(cmp)
        return comparisons

    def evaluate_results(self, comparisons, baseline_hash: str) -> EvaluationSummary:
        return build_evaluation_summary(comparisons, baseline_hash)

    def generate_report(self, metadata: ExperimentMetadata) -> str:
        lines = [f"Experiment Evaluation ({metadata.experiment_id})\\n"]
        tests_msg = "Passed" if metadata.tests.get("passed") else "Failed"
        lines.append(f"Tests:\\n{tests_msg}\\n")
        
        if metadata.evaluation:
            for cmp in metadata.evaluation.comparisons.values():
                b_mean = cmp.baseline.mean if cmp.baseline.mean is not None else 0
                e_mean = cmp.experiment.mean if cmp.experiment.mean is not None else 0
                lines.append(f"{cmp.metric}:")
                lines.append(f"{b_mean:.2f} → {e_mean:.2f}")
                if cmp.change_percent is not None:
                    arrow = "↓" if cmp.change_percent < 0 else "↑"
                    lines.append(f"{arrow} {abs(cmp.change_percent):.1f}% ({cmp.result})")
                else:
                    lines.append(f"Result: {cmp.result}")
                lines.append("")
                
            lines.append(f"Evaluation:\\n{metadata.evaluation.classification}\\n")
            crit_regs = metadata.evaluation.critical_regressions
            lines.append(f"Critical regressions:\\n{'None' if not crit_regs else ', '.join(crit_regs)}\\n")
            
        lines.append(f"Status:\\n{metadata.status.value}")
        return "\\n".join(lines)

    def _calculate_diff_stats(self, metadata: ExperimentMetadata) -> Dict[str, int]:
        diff_path = os.path.join(EXPERIMENTS_DIR, metadata.experiment_id, "diff.patch")
        added = 0
        removed = 0
        if os.path.exists(diff_path):
            with open(diff_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("+") and not line.startswith("+++"):
                        added += 1
                    elif line.startswith("-") and not line.startswith("---"):
                        removed += 1
        return {
            "files_changed": len(metadata.files),
            "lines_added": added,
            "lines_removed": removed
        }

    def _generate_diff(self, metadata: ExperimentMetadata) -> None:
        exp_dir = os.path.join(EXPERIMENTS_DIR, metadata.experiment_id)
        diff_lines = []

        for file_entry in metadata.files:
            production_path = os.path.join(HELIOS_DIR, file_entry.target)
            experiment_path = os.path.join(exp_dir, file_entry.source)

            original_lines = []
            if os.path.exists(production_path):
                try:
                    with open(production_path, "r", encoding="utf-8") as f:
                        original_lines = f.readlines()
                except (UnicodeDecodeError, IOError):
                    original_lines = ["<binary or unreadable file>\\n"]

            modified_lines = []
            if os.path.exists(experiment_path):
                try:
                    with open(experiment_path, "r", encoding="utf-8") as f:
                        modified_lines = f.readlines()
                except (UnicodeDecodeError, IOError):
                    modified_lines = ["<binary or unreadable file>\\n"]

            diff = difflib.unified_diff(
                original_lines,
                modified_lines,
                fromfile=f"a/{file_entry.target}",
                tofile=f"b/{file_entry.target}",
                lineterm="",
            )
            diff_lines.extend(diff)
            diff_lines.append("")

        diff_path = os.path.join(exp_dir, "diff.patch")
        with open(diff_path, "w", encoding="utf-8") as f:
            f.write("\\n".join(diff_lines))

    def get_diff(self, experiment_id: str) -> Optional[str]:
        diff_path = os.path.join(EXPERIMENTS_DIR, experiment_id, "diff.patch")
        if os.path.exists(diff_path):
            with open(diff_path, "r", encoding="utf-8") as f:
                return f.read()
        return None

    # ── Deployment (Human-triggered only) ────────────────────────────────

    def deploy(self, experiment_id: str, user_id: int) -> Tuple[bool, str]:
        metadata = self.load_metadata(experiment_id)
        if metadata is None:
            return False, f"Experiment '{experiment_id}' not found."

        if metadata.status != ExperimentStatus.APPROVED:
            return False, f"Experiment must be APPROVED before deployment. Current: {metadata.status.value}"

        exp_dir = os.path.join(EXPERIMENTS_DIR, experiment_id)
        deployed_files: List[Dict[str, str]] = []
        errors: List[str] = []

        for file_entry in metadata.files:
            abs_target = (Path(HELIOS_DIR) / file_entry.target).resolve(strict=False)
            abs_source = (Path(exp_dir) / file_entry.source).resolve(strict=False)

            if not validate_experiment_source(abs_source, Path(exp_dir)):
                errors.append(f"Source '{file_entry.source}' is outside experiment workspace.")
                continue

            if not abs_target.is_relative_to(Path(HELIOS_DIR).resolve(strict=False)):
                errors.append(f"Target '{file_entry.target}' escapes HELIOS_DIR.")
                continue

            if self.permission_manager.is_protected_path(abs_target):
                errors.append(f"Target '{file_entry.target}' is in a protected system zone.")
                continue

            perm = self.permission_manager.can_write_file(user_id, str(abs_target))
            if not perm.allowed:
                errors.append(f"Write denied for '{file_entry.target}': {perm.reason}")
                continue

            backup_path = (Path(exp_dir) / "backup" / file_entry.target).resolve(strict=False)
            if not backup_path.is_relative_to((Path(exp_dir) / "backup").resolve(strict=False)):
                errors.append("Path traversal in backup path.")
                continue

            backup_path.parent.mkdir(parents=True, exist_ok=True)
            if abs_target.exists():
                file_entry.pre_deploy_sha256 = compute_sha256(str(abs_target))
                shutil.copy2(str(abs_target), str(backup_path))
            else:
                file_entry.pre_deploy_sha256 = None

            try:
                abs_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(abs_source), str(abs_target))
                file_entry.deployed_sha256 = compute_sha256(str(abs_target))
                deployed_files.append({
                    "target": file_entry.target,
                    "deployed_sha256": file_entry.deployed_sha256,
                })
            except Exception as e:
                errors.append(f"Failed to deploy '{file_entry.target}': {e}")

        if errors:
            for deployed in deployed_files:
                backup = os.path.join(exp_dir, "backup", deployed["target"])
                production = os.path.join(HELIOS_DIR, deployed["target"])
                if os.path.exists(backup):
                    shutil.copy2(backup, production)
                elif os.path.exists(production):
                    os.remove(production)

            metadata.deployment = {
                "attempted_at": datetime.now(timezone.utc).isoformat(),
                "result": "FAILED",
                "errors": errors,
            }
            self._save_metadata(metadata)
            transition_experiment(experiment_id, ExperimentStatus.FAILED, Actor.SYSTEM, f"Deployment failed: {'; '.join(errors)}")
            return False, f"Deployment aborted. Errors: {'; '.join(errors)}"

        metadata.deployment = {
            "deployed_at": datetime.now(timezone.utc).isoformat(),
            "deployed_by": user_id,
            "result": "SUCCESS",
            "files": deployed_files,
        }
        self._save_metadata(metadata)
        transition_experiment(experiment_id, ExperimentStatus.DEPLOYED, Actor.HUMAN, "Deployed successfully")

        self.permission_manager.log_operation(
            user_id, "self_modification", "deploy",
            experiment_id, "APPROVED", "SUCCESS"
        )
        return True, f"Experiment '{experiment_id}' deployed successfully."

    # ── Rollback (Human-triggered only) ──────────────────────────────────

    def rollback(self, experiment_id: str, user_id: int) -> Tuple[bool, str]:
        metadata = self.load_metadata(experiment_id)
        if metadata is None:
            return False, f"Experiment '{experiment_id}' not found."

        if metadata.status != ExperimentStatus.DEPLOYED:
            return False, f"Only DEPLOYED experiments can be rolled back. Current: {metadata.status.value}"

        exp_dir = os.path.join(EXPERIMENTS_DIR, experiment_id)
        rolled_back: List[str] = []
        blocked: List[str] = []

        for file_entry in metadata.files:
            abs_target = (Path(HELIOS_DIR) / file_entry.target).resolve(strict=False)
            backup_path = (Path(exp_dir) / "backup" / file_entry.target).resolve(strict=False)

            if self.permission_manager.is_protected_path(abs_target):
                blocked.append(f"{file_entry.target}: protected system zone")
                continue

            if abs_target.exists() and file_entry.deployed_sha256:
                current_sha = compute_sha256(str(abs_target))
                if current_sha != file_entry.deployed_sha256:
                    blocked.append(f"{file_entry.target}: production file has changed since deployment.")
                    continue

            if backup_path.exists():
                shutil.copy2(str(backup_path), str(abs_target))
                rolled_back.append(file_entry.target)
            elif file_entry.pre_deploy_sha256 is None:
                if abs_target.exists():
                    abs_target.unlink()
                rolled_back.append(file_entry.target)

        if blocked:
            msg = f"Partial rollback. Restored: {rolled_back}. Blocked: {'; '.join(blocked)}"
            self.permission_manager.log_operation(
                user_id, "self_modification", "rollback",
                experiment_id, "PARTIAL", msg[:200]
            )
            return False, msg

        metadata.deployment["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
        metadata.deployment["rolled_back_by"] = user_id
        self._save_metadata(metadata)
        
        transition_experiment(experiment_id, ExperimentStatus.ROLLED_BACK, Actor.HUMAN, "Rolled back successfully")

        self.permission_manager.log_operation(
            user_id, "self_modification", "rollback",
            experiment_id, "APPROVED", "SUCCESS"
        )
        return True, f"Experiment '{experiment_id}' rolled back successfully."

    # ── State Transitions ────────────────────────────────────────────────

    def transition_llm(self, experiment_id: str,
                        target_status: ExperimentStatus) -> Tuple[bool, str]:
        try:
            transition_experiment(experiment_id, target_status, Actor.LLM, "LLM requested transition")
            return True, f"Experiment transitioned to {target_status.value}."
        except Exception as e:
            return False, str(e)

    def transition_human(self, experiment_id: str,
                          target_status: ExperimentStatus) -> Tuple[bool, str]:
        try:
            transition_experiment(experiment_id, target_status, Actor.HUMAN, "Human requested transition")
            return True, f"Experiment transitioned to {target_status.value}."
        except Exception as e:
            return False, str(e)

    # ── Database Persistence ─────────────────────────────────────────────

    def list_experiments(self) -> List[Dict[str, Any]]:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM experiments")
        rows = cursor.fetchall()
        conn.close()
        
        experiments = []
        for row in rows:
            meta = self.load_metadata(row["id"])
            if meta:
                experiments.append(meta.to_dict())
        return experiments

    def load_metadata(self, experiment_id: str) -> Optional[ExperimentMetadata]:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM experiments WHERE id = ?", (experiment_id,))
        exp_row = cursor.fetchone()
        if not exp_row:
            conn.close()
            return None
            
        metadata = ExperimentMetadata(
            experiment_id=exp_row["id"],
            objective=exp_row["objective"],
            risk_level=RiskLevel(exp_row["risk_level"])
        )
        metadata.created_at = exp_row["created_at"]
        metadata.status = ExperimentStatus(exp_row["status"])
        
        if exp_row["diff_stats"]:
            metadata.diff_stats = json.loads(exp_row["diff_stats"])
        if exp_row["deployment"]:
            metadata.deployment = json.loads(exp_row["deployment"])
            
        cursor.execute("SELECT * FROM experiment_files WHERE experiment_id = ?", (experiment_id,))
        for f_row in cursor.fetchall():
            entry = FileEntry(source=f_row["source"], target=f_row["target"])
            entry.baseline_sha256 = f_row["baseline_sha256"]
            entry.pre_deploy_sha256 = f_row["pre_deploy_sha256"]
            entry.deployed_sha256 = f_row["deployed_sha256"]
            metadata.files.append(entry)
            
        cursor.execute("SELECT * FROM evaluation_runs WHERE experiment_id = ?", (experiment_id,))
        eval_row = cursor.fetchone()
        if eval_row:
            summary = EvaluationSummary(
                classification=eval_row["classification"],
                timestamp=eval_row["started_at"],
                baseline_hash=eval_row["baseline_hash"]
            )
            if eval_row["critical_regressions"]:
                summary.critical_regressions = json.loads(eval_row["critical_regressions"])
            
            cursor.execute("SELECT * FROM evaluation_comparisons WHERE evaluation_id = ?", (eval_row["id"],))
            for c_row in cursor.fetchall():
                baseline_result = BenchmarkResult.from_dict(json.loads(c_row["baseline_result"]))
                experiment_result = BenchmarkResult.from_dict(json.loads(c_row["experiment_result"]))
                
                cmp = BenchmarkComparison(
                    metric=c_row["metric"],
                    direction=c_row["direction"],
                    baseline=baseline_result,
                    experiment=experiment_result,
                    change_percent=c_row["change_percent"],
                    result=c_row["result"]
                )
                summary.comparisons[cmp.metric] = cmp
            
            metadata.evaluation = summary

        # We also need to read tests from disk if it was saved, or add it to DB.
        # But wait, tests output is huge. Let's add tests to diff_stats or just keep it in memory/json.
        # For full resilience, we can save `metadata.json` as a read-only artifact.
        # Read tests from metadata.json if it exists.
        meta_path = os.path.join(EXPERIMENTS_DIR, experiment_id, "metadata.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    disk_data = json.load(f)
                metadata.tests = disk_data.get("tests", {})
            except Exception:
                pass

        conn.close()
        return metadata

    def _save_metadata(self, metadata: ExperimentMetadata) -> None:
        """Save authoritative experiment metadata to database, and write artifact to disk."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("BEGIN EXCLUSIVE")
        try:
            cursor.execute("SELECT id FROM experiments WHERE id = ?", (metadata.experiment_id,))
            exists = cursor.fetchone()
            
            if exists:
                cursor.execute(
                    "UPDATE experiments SET objective = ?, risk_level = ?, status = ?, diff_stats = ?, deployment = ? WHERE id = ?",
                    (
                        metadata.objective, 
                        metadata.risk_level.value, 
                        metadata.status.value,
                        json.dumps(metadata.diff_stats),
                        json.dumps(metadata.deployment),
                        metadata.experiment_id
                    )
                )
            else:
                cursor.execute(
                    "INSERT INTO experiments (id, created_at, objective, risk_level, status, diff_stats, deployment) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        metadata.experiment_id,
                        metadata.created_at,
                        metadata.objective,
                        metadata.risk_level.value,
                        metadata.status.value,
                        json.dumps(metadata.diff_stats),
                        json.dumps(metadata.deployment)
                    )
                )

            # Update files (delete and re-insert for simplicity)
            cursor.execute("DELETE FROM experiment_files WHERE experiment_id = ?", (metadata.experiment_id,))
            for f in metadata.files:
                cursor.execute(
                    "INSERT INTO experiment_files (experiment_id, source, target, baseline_sha256, pre_deploy_sha256, deployed_sha256) VALUES (?, ?, ?, ?, ?, ?)",
                    (metadata.experiment_id, f.source, f.target, f.baseline_sha256, f.pre_deploy_sha256, f.deployed_sha256)
                )

            # Evaluations are immutable; we only write if not already written (handled in evaluate_experiment?)
            # Actually, _save_metadata is called everywhere. So we only write evaluation if there isn't one already for this timestamp
            if metadata.evaluation:
                cursor.execute("SELECT id FROM evaluation_runs WHERE experiment_id = ? AND started_at = ?", 
                               (metadata.experiment_id, metadata.evaluation.timestamp))
                if not cursor.fetchone():
                    cursor.execute(
                        "INSERT INTO evaluation_runs (experiment_id, started_at, classification, baseline_hash, critical_regressions) VALUES (?, ?, ?, ?, ?)",
                        (
                            metadata.experiment_id, 
                            metadata.evaluation.timestamp, 
                            metadata.evaluation.classification,
                            metadata.evaluation.baseline_hash,
                            json.dumps(metadata.evaluation.critical_regressions)
                        )
                    )
                    eval_id = cursor.lastrowid
                    for cmp in metadata.evaluation.comparisons.values():
                        cursor.execute(
                            "INSERT INTO evaluation_comparisons (evaluation_id, metric, direction, baseline_result, experiment_result, change_percent, result) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (
                                eval_id,
                                cmp.metric,
                                cmp.direction,
                                json.dumps(cmp.baseline.to_dict()),
                                json.dumps(cmp.experiment.to_dict()),
                                cmp.change_percent,
                                cmp.result
                            )
                        )
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

        # Write read-only artifact to disk for compatibility/debug
        exp_dir = os.path.join(EXPERIMENTS_DIR, metadata.experiment_id)
        os.makedirs(exp_dir, exist_ok=True)
        meta_path = os.path.join(exp_dir, "metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata.to_dict(), f, indent=2)

    # ── Discard ──────────────────────────────────────────────────────────

    def discard_experiment(self, experiment_id: str) -> Tuple[bool, str]:
        try:
            transition_experiment(experiment_id, ExperimentStatus.DISCARDED, Actor.LLM, "LLM discarded experiment")
            return True, f"Experiment '{experiment_id}' discarded."
        except Exception as e:
            return False, str(e)
