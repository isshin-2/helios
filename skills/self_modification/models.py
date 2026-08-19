"""
HELIOS — Self-Modification Models
===================================
Data structures, state machine, and risk classification for
the controlled self-modification system.
"""

import hashlib
import json
import logging
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from db import get_db

logger = logging.getLogger(__name__)


class ExperimentStatus(str, Enum):
    """Explicit state machine for experiment lifecycle."""
    DRAFT = "DRAFT"
    EXPERIMENTING = "EXPERIMENTING"
    TESTING = "TESTING"
    EVALUATING = "EVALUATING"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    DEPLOYED = "DEPLOYED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    DISCARDED = "DISCARDED"
    ROLLED_BACK = "ROLLED_BACK"
    INCONCLUSIVE = "INCONCLUSIVE"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Actor(str, Enum):
    LLM = "LLM"
    EVALUATOR = "EVALUATOR"
    HUMAN = "HUMAN"
    SYSTEM = "SYSTEM"


# ─── State Transition Rules ────────────────────────────────────────────────

ALLOWED_TRANSITIONS = {
    Actor.LLM: {
        ExperimentStatus.DRAFT: [ExperimentStatus.EXPERIMENTING, ExperimentStatus.DISCARDED],
        ExperimentStatus.EXPERIMENTING: [ExperimentStatus.DISCARDED, ExperimentStatus.EVALUATING],
        ExperimentStatus.INCONCLUSIVE: [ExperimentStatus.DISCARDED, ExperimentStatus.EXPERIMENTING],
        ExperimentStatus.FAILED: [ExperimentStatus.DISCARDED, ExperimentStatus.EXPERIMENTING],
    },
    Actor.EVALUATOR: {
        ExperimentStatus.EVALUATING: [
            ExperimentStatus.READY_FOR_REVIEW,
            ExperimentStatus.INCONCLUSIVE,
            ExperimentStatus.FAILED,
            ExperimentStatus.SECURITY_VIOLATION
        ]
    },
    Actor.HUMAN: {
        ExperimentStatus.READY_FOR_REVIEW: [ExperimentStatus.APPROVED, ExperimentStatus.REJECTED],
        ExperimentStatus.APPROVED: [ExperimentStatus.DEPLOYED],
        ExperimentStatus.DEPLOYED: [ExperimentStatus.ROLLED_BACK],
    },
}

def validate_transition(current: ExperimentStatus, target: ExperimentStatus, actor: Actor) -> bool:
    if actor == Actor.SYSTEM:
        return True
    
    actor_rules = ALLOWED_TRANSITIONS.get(actor, {})
    allowed_targets = actor_rules.get(current, [])
    return target in allowed_targets


def transition_experiment(experiment_id: str, target_state: ExperimentStatus, actor: Actor, reason: str = ""):
    """Authoritative transition function that enforces rules and logs to database."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("BEGIN EXCLUSIVE")
    try:
        # Get current state
        cursor.execute("SELECT status FROM experiments WHERE id = ?", (experiment_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Experiment {experiment_id} not found")
        
        current_state = ExperimentStatus(row["status"])
        
        if not validate_transition(current_state, target_state, actor):
            raise PermissionError(f"Actor {actor} cannot transition from {current_state} to {target_state}")
        
        # Prerequisites checks
        if target_state == ExperimentStatus.READY_FOR_REVIEW:
            # Must have evaluation results
            cursor.execute("SELECT id FROM evaluation_runs WHERE experiment_id = ?", (experiment_id,))
            if not cursor.fetchone():
                raise ValueError("Cannot reach READY_FOR_REVIEW without an evaluation run")
        
        # Update state
        cursor.execute("UPDATE experiments SET status = ? WHERE id = ?", (target_state.value, experiment_id))
        
        # Audit Log
        cursor.execute(
            """INSERT INTO experiment_audit_log (actor, experiment_id, action, previous_state, new_state, reason)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (actor.value, experiment_id, "STATE_TRANSITION", current_state.value, target_state.value, reason)
        )
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# ─── File Entry ─────────────────────────────────────────────────────────────

class FileEntry:
    """Represents a single file modification within an experiment."""

    def __init__(self, source: str, target: str):
        self.source = source   # Relative path inside experiment/modified/
        self.target = target   # Relative path inside HELIOS project root
        self.baseline_sha256: Optional[str] = None
        self.pre_deploy_sha256: Optional[str] = None
        self.deployed_sha256: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "baseline_sha256": self.baseline_sha256,
            "pre_deploy_sha256": self.pre_deploy_sha256,
            "deployed_sha256": self.deployed_sha256,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileEntry":
        entry = cls(source=data["source"], target=data["target"])
        entry.baseline_sha256 = data.get("baseline_sha256")
        entry.pre_deploy_sha256 = data.get("pre_deploy_sha256")
        entry.deployed_sha256 = data.get("deployed_sha256")
        return entry


# ─── Benchmark Data Models ──────────────────────────────────────────────────

class BenchmarkResult:
    def __init__(self, mean: Optional[float] = None, median: Optional[float] = None,
                 min_val: Optional[float] = None, max_val: Optional[float] = None,
                 p95: Optional[float] = None, std_dev: Optional[float] = None,
                 sample_count: int = 0):
        self.mean = mean
        self.median = median
        self.min = min_val
        self.max = max_val
        self.p95 = p95
        self.std_dev = std_dev
        self.sample_count = sample_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mean": self.mean,
            "median": self.median,
            "min": self.min,
            "max": self.max,
            "p95": self.p95,
            "std_dev": self.std_dev,
            "sample_count": self.sample_count
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkResult":
        return cls(
            mean=data.get("mean"), median=data.get("median"),
            min_val=data.get("min"), max_val=data.get("max"),
            p95=data.get("p95"), std_dev=data.get("std_dev"),
            sample_count=data.get("sample_count", 0)
        )


class BenchmarkComparison:
    def __init__(self, metric: str, direction: str, 
                 baseline: BenchmarkResult, experiment: BenchmarkResult,
                 change_percent: Optional[float], result: str):
        self.metric = metric
        self.direction = direction
        self.baseline = baseline
        self.experiment = experiment
        self.change_percent = change_percent
        self.result = result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "direction": self.direction,
            "baseline": self.baseline.to_dict(),
            "experiment": self.experiment.to_dict(),
            "change_percent": self.change_percent,
            "result": self.result
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkComparison":
        return cls(
            metric=data["metric"],
            direction=data["direction"],
            baseline=BenchmarkResult.from_dict(data["baseline"]),
            experiment=BenchmarkResult.from_dict(data["experiment"]),
            change_percent=data.get("change_percent"),
            result=data["result"]
        )


class EvaluationSummary:
    def __init__(self, classification: str, timestamp: str, baseline_hash: str):
        self.classification = classification
        self.timestamp = timestamp
        self.baseline_hash = baseline_hash
        self.comparisons: Dict[str, BenchmarkComparison] = {}
        self.critical_regressions: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "classification": self.classification,
            "timestamp": self.timestamp,
            "baseline_hash": self.baseline_hash,
            "comparisons": {k: v.to_dict() for k, v in self.comparisons.items()},
            "critical_regressions": self.critical_regressions
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationSummary":
        summary = cls(
            classification=data["classification"],
            timestamp=data["timestamp"],
            baseline_hash=data["baseline_hash"]
        )
        summary.critical_regressions = data.get("critical_regressions", [])
        summary.comparisons = {
            k: BenchmarkComparison.from_dict(v) 
            for k, v in data.get("comparisons", {}).items()
        }
        return summary


# ─── Experiment Metadata ────────────────────────────────────────────────────

class ExperimentMetadata:
    """Complete metadata for a single self-modification experiment."""

    def __init__(self, experiment_id: str, objective: str,
                 risk_level: RiskLevel = RiskLevel.LOW):
        self.experiment_id = experiment_id
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.objective = objective
        self.risk_level = risk_level
        self.status = ExperimentStatus.DRAFT
        self.files: List[FileEntry] = []
        self.tests: Dict[str, Any] = {}
        self.deployment: Dict[str, Any] = {}
        self.evaluation: Optional[EvaluationSummary] = None
        self.diff_stats: Dict[str, int] = {"files_changed": 0, "lines_added": 0, "lines_removed": 0}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "created_at": self.created_at,
            "objective": self.objective,
            "risk_level": self.risk_level.value,
            "status": self.status.value,
            "files": [f.to_dict() for f in self.files],
            "tests": self.tests,
            "deployment": self.deployment,
            "evaluation": self.evaluation.to_dict() if self.evaluation else None,
            "diff_stats": self.diff_stats,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperimentMetadata":
        meta = cls(
            experiment_id=data["experiment_id"],
            objective=data["objective"],
            risk_level=RiskLevel(data.get("risk_level", "LOW")),
        )
        meta.created_at = data.get("created_at", meta.created_at)
        meta.status = ExperimentStatus(data.get("status", "DRAFT"))
        meta.files = [FileEntry.from_dict(f) for f in data.get("files", [])]
        meta.tests = data.get("tests", {})
        meta.deployment = data.get("deployment", {})
        
        eval_data = data.get("evaluation")
        if eval_data:
            meta.evaluation = EvaluationSummary.from_dict(eval_data)
            
        meta.diff_stats = data.get("diff_stats", {"files_changed": 0, "lines_added": 0, "lines_removed": 0})
        return meta


def compute_sha256(filepath: str) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
