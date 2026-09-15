"""
HELIOS — Task Contract
Structured representation of every autonomous task.
Every autonomous task is converted into a TaskContract before the Supervisor operates on it.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field


# ─── Risk Levels ────────────────────────────────────────────────────────────

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ─── Capability Requirements ────────────────────────────────────────────────

class TaskCapability(str, Enum):
    """Capabilities a task may require. Maps to security/capabilities.py."""
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    TERMINAL_EXECUTE = "terminal_execute"
    NETWORK_ACCESS = "network_access"
    BROWSER_CONTROL = "browser_control"
    DOCKER_SANDBOX = "docker_sandbox"
    HOST_CONTROL = "host_control"
    SELF_MODIFICATION = "self_modification"


# ─── Budget ─────────────────────────────────────────────────────────────────

class TaskBudget(BaseModel):
    """Resource budget for a task. The Supervisor enforces these limits."""
    max_iterations: int = Field(default=10, ge=1, description="Maximum tool-use loop iterations.")
    max_agent_calls: int = Field(default=20, ge=1, description="Maximum total agent invocations.")
    max_tool_calls: int = Field(default=50, ge=1, description="Maximum total tool calls.")
    max_runtime_seconds: float = Field(default=600.0, gt=0, description="Wall-clock timeout in seconds.")
    max_retries: int = Field(default=3, ge=0, description="Maximum retries after verified failure.")
    max_repeated_failures: int = Field(default=3, ge=1, description="Max identical consecutive failures before hard stop.")


# ─── Stop Conditions ────────────────────────────────────────────────────────

class StopConditions(BaseModel):
    """Deterministic conditions that force task termination."""
    budget_exhausted: bool = False
    success: bool = False
    user_cancelled: bool = False
    permission_unavailable: bool = False
    loop_detected: bool = False
    unsafe_behavior: bool = False
    information_missing: bool = False
    no_progress: bool = False

    @property
    def should_stop(self) -> bool:
        return any([
            self.budget_exhausted,
            self.success,
            self.user_cancelled,
            self.permission_unavailable,
            self.loop_detected,
            self.unsafe_behavior,
            self.information_missing,
            self.no_progress,
        ])

    @property
    def reason(self) -> str:
        reasons = []
        if self.success:
            reasons.append("Task succeeded")
        if self.budget_exhausted:
            reasons.append("Budget exhausted")
        if self.user_cancelled:
            reasons.append("User cancelled")
        if self.permission_unavailable:
            reasons.append("Required permission unavailable")
        if self.loop_detected:
            reasons.append("Loop detected")
        if self.unsafe_behavior:
            reasons.append("Unsafe behavior detected")
        if self.information_missing:
            reasons.append("Required information missing")
        if self.no_progress:
            reasons.append("No progress detected")
        return "; ".join(reasons) if reasons else "No stop condition met"


# ─── Step Record ────────────────────────────────────────────────────────────

class StepRecord(BaseModel):
    """Immutable record of a single execution step."""
    step_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_id: Optional[str] = None
    action: str = ""
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    result_status: Optional[str] = None
    result_summary: Optional[str] = None
    artifacts: List[str] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None


# ─── Task Contract ──────────────────────────────────────────────────────────

class TaskContract(BaseModel):
    """
    The core contract for every autonomous task.
    The Supervisor operates exclusively on this structure.
    """
    # Identity
    task_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    parent_task_id: Optional[str] = None

    # Objective
    objective: str
    context: str = Field(default="", description="Additional context for the task.")
    constraints: List[str] = Field(default_factory=list, description="Constraints the solution must satisfy.")

    # Requirements
    required_artifacts: List[str] = Field(default_factory=list, description="Artifacts that must be produced.")
    success_criteria: List[str] = Field(default_factory=list, description="Conditions that define success.")
    allowed_capabilities: Set[TaskCapability] = Field(
        default_factory=lambda: {TaskCapability.FILE_READ},
        description="Capabilities this task is allowed to use."
    )

    # Risk & Budget
    risk_level: RiskLevel = RiskLevel.LOW
    budget: TaskBudget = Field(default_factory=TaskBudget)
    stop_conditions: StopConditions = Field(default_factory=StopConditions)

    # State (mutated by the Supervisor)
    current_state: str = "IDLE"
    steps: List[StepRecord] = Field(default_factory=list)

    # Counters (mutated by the Supervisor)
    iterations: int = 0
    agent_calls: int = 0
    tool_calls: int = 0
    retry_count: int = 0
    repeated_failure_count: int = 0
    last_failure_signature: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    # Metadata
    user_id: Optional[int] = None
    session_id: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # ─── Budget Checks ──────────────────────────────────────────────────

    def check_budget(self) -> Optional[str]:
        """Returns a reason string if any budget is exceeded, else None."""
        if self.iterations >= self.budget.max_iterations:
            return f"Max iterations reached ({self.budget.max_iterations})"
        if self.agent_calls >= self.budget.max_agent_calls:
            return f"Max agent calls reached ({self.budget.max_agent_calls})"
        if self.tool_calls >= self.budget.max_tool_calls:
            return f"Max tool calls reached ({self.budget.max_tool_calls})"
        if self.retry_count >= self.budget.max_retries:
            return f"Max retries reached ({self.budget.max_retries})"
        if self.repeated_failure_count >= self.budget.max_repeated_failures:
            return f"Max repeated failures reached ({self.budget.max_repeated_failures})"
        if self.started_at:
            elapsed = (datetime.now(timezone.utc) - self.started_at).total_seconds()
            if elapsed >= self.budget.max_runtime_seconds:
                return f"Max runtime exceeded ({self.budget.max_runtime_seconds}s)"
        return None

    def record_step(self, step: StepRecord) -> None:
        """Append a step and increment counters."""
        self.steps.append(step)
        if step.agent_id:
            self.agent_calls += 1
        if step.tool_name:
            self.tool_calls += 1

    def record_failure(self, signature: str) -> None:
        """Track failure and detect repeated identical failures."""
        self.retry_count += 1
        if signature == self.last_failure_signature:
            self.repeated_failure_count += 1
        else:
            self.repeated_failure_count = 1
            self.last_failure_signature = signature

    def record_success(self) -> None:
        """Reset failure tracking on verified success."""
        self.repeated_failure_count = 0
        self.last_failure_signature = None

    def finalize(self, success: bool) -> None:
        """Mark the contract as finished."""
        self.finished_at = datetime.now(timezone.utc)
        if success:
            self.stop_conditions.success = True
            self.current_state = "COMPLETED"
        else:
            self.current_state = "FAILED"
