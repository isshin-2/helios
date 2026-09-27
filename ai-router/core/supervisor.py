"""
HELIOS — Supervisor
Deterministic loop controller that operates on a TaskContract.
The Supervisor does NOT call the LLM. It is a pure state machine driver.
Agents do the LLM work; the Supervisor manages their lifecycle.

The Supervisor:
    1. Accepts a TaskContract
    2. Drives it through the TaskStateMachine
    3. Delegates work to agents
    4. Enforces budgets, stop conditions, and recovery limits
    5. Produces a final summary when the task terminates
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from core.state_machine import (
    InvalidTransitionError,
    TaskState,
    TaskStateMachine,
    TERMINAL_STATES,
)
from core.task_contract import (
    RiskLevel,
    StepRecord,
    TaskContract,
)
from agents.base import AgentResult, AgentStatus

logger = logging.getLogger("helios.supervisor")


# ─── Supervisor Phase ────────────────────────────────────────────────────────

class SupervisorDecision:
    """What the Supervisor decides after inspecting an AgentResult."""

    def __init__(
        self,
        next_state: TaskState,
        reason: str,
        agent_id: Optional[str] = None,
        objective_override: Optional[str] = None,
    ):
        self.next_state = next_state
        self.reason = reason
        self.agent_id = agent_id
        self.objective_override = objective_override

    def __repr__(self) -> str:
        return f"Decision(→{self.next_state.value}, {self.reason})"


# ─── Supervisor ──────────────────────────────────────────────────────────────

class Supervisor:
    """
    Deterministic loop controller.

    Usage:
        supervisor = Supervisor()
        supervisor.start(contract)
        while not supervisor.is_done:
            # get current phase, delegate to an agent, feed result back
            decision = supervisor.evaluate(agent_result)
            supervisor.apply(decision)
        summary = supervisor.finalize()
    """

    def __init__(self):
        self._contract: Optional[TaskContract] = None
        self._fsm: Optional[TaskStateMachine] = None
        self._active = False

    # ─── Properties ──────────────────────────────────────────────────

    @property
    def contract(self) -> Optional[TaskContract]:
        return self._contract

    @property
    def state(self) -> Optional[TaskState]:
        return self._fsm.state if self._fsm else None

    @property
    def is_done(self) -> bool:
        if not self._fsm:
            return True
        return self._fsm.is_terminal

    @property
    def is_active(self) -> bool:
        return self._active and not self.is_done

    # ─── Lifecycle ───────────────────────────────────────────────────

    def start(self, contract: TaskContract) -> TaskState:
        """
        Bind a TaskContract and begin execution.
        Transitions: IDLE → ANALYZE
        """
        self._contract = contract
        self._fsm = TaskStateMachine(initial_state=TaskState(contract.current_state))
        self._active = True

        contract.started_at = datetime.now(timezone.utc)

        # Immediately transition to ANALYZE
        self._transition(TaskState.ANALYZE, "Supervisor started task")
        contract.iterations += 1
        return self._fsm.state

    def evaluate(self, result: AgentResult) -> SupervisorDecision:
        """
        Inspect an AgentResult and decide the next state transition.
        This is the core decision logic — entirely deterministic.
        """
        assert self._contract is not None
        assert self._fsm is not None

        contract = self._contract

        # Record the step
        step = StepRecord(
            agent_id=result.agent_id,
            action=f"{result.agent_type}:{result.status.value}",
            result_status=result.status.value,
            result_summary=result.summary,
            artifacts=result.artifacts,
            started_at=result.started_at,
            finished_at=result.finished_at or datetime.now(timezone.utc),
            error=result.error,
        )
        contract.record_step(step)

        # ── 1. Budget check ──────────────────────────────────────────
        budget_reason = contract.check_budget()
        if budget_reason:
            contract.stop_conditions.budget_exhausted = True
            return SupervisorDecision(
                next_state=TaskState.FAILED,
                reason=f"Budget exceeded: {budget_reason}",
            )

        # ── 2. Handle agent status ───────────────────────────────────
        current = self._fsm.state

        if result.status == AgentStatus.SUCCESS:
            # Only reset failure tracking on verified success (VERIFY stage)
            if current == TaskState.VERIFY:
                contract.record_success()
            return self._on_success(current, result)

        if result.status == AgentStatus.PARTIAL:
            return self._on_partial(current, result)

        if result.status == AgentStatus.FAILURE:
            return self._on_failure(current, result, contract)

        if result.status == AgentStatus.NEEDS_APPROVAL:
            return SupervisorDecision(
                next_state=TaskState.WAITING_APPROVAL,
                reason=f"Agent requires approval: {result.summary}",
            )

        if result.status == AgentStatus.NEEDS_INPUT:
            return SupervisorDecision(
                next_state=TaskState.WAITING_USER,
                reason=f"Agent requires user input: {result.summary}",
            )

        if result.status == AgentStatus.SKIPPED:
            return self._on_success(current, result)

        # Fallback
        return SupervisorDecision(
            next_state=TaskState.FAILED,
            reason=f"Unexpected agent status: {result.status.value}",
        )

    def apply(self, decision: SupervisorDecision) -> TaskState:
        """Apply a decision to the state machine and update the contract."""
        assert self._fsm is not None
        assert self._contract is not None

        record = self._transition(decision.next_state, decision.reason)
        self._contract.current_state = decision.next_state.value

        # Increment iteration when entering EXECUTE
        if decision.next_state == TaskState.EXECUTE:
            self._contract.iterations += 1

        return self._fsm.state

    def cancel(self, reason: str = "User cancelled") -> TaskState:
        """Cancel the running task."""
        assert self._fsm is not None
        assert self._contract is not None

        self._contract.stop_conditions.user_cancelled = True
        self._transition(TaskState.CANCELLED, reason)
        self._contract.current_state = TaskState.CANCELLED.value
        self._contract.finished_at = datetime.now(timezone.utc)
        self._active = False
        return TaskState.CANCELLED

    def pause(self, reason: str = "Paused") -> TaskState:
        """Pause the running task."""
        self._transition(TaskState.PAUSED, reason)
        self._contract.current_state = TaskState.PAUSED.value
        return TaskState.PAUSED

    def resume(self) -> TaskState:
        """Resume a paused task."""
        self._transition(TaskState.EXECUTE, "Resumed")
        self._contract.current_state = TaskState.EXECUTE.value
        return TaskState.EXECUTE

    def approve(self) -> TaskState:
        """Approve a waiting task to continue execution."""
        assert self._fsm is not None
        # From WAITING_APPROVAL, go to EXECUTE
        self._transition(TaskState.EXECUTE, "Approved by user")
        self._contract.current_state = TaskState.EXECUTE.value
        return TaskState.EXECUTE

    def provide_input(self) -> TaskState:
        """Provide user input to unblock a waiting task."""
        self._transition(TaskState.EXECUTE, "User provided input")
        self._contract.current_state = TaskState.EXECUTE.value
        return TaskState.EXECUTE

    def finalize_task(self) -> Dict[str, Any]:
        """
        Finalize the task and return a structured summary.
        This is called after the FSM reaches a terminal state.
        """
        assert self._contract is not None
        assert self._fsm is not None

        contract = self._contract
        success = self._fsm.state == TaskState.COMPLETED

        contract.finalize(success)
        self._active = False

        return {
            "task_id": contract.task_id,
            "objective": contract.objective,
            "status": self._fsm.state.value,
            "success": success,
            "steps_count": len(contract.steps),
            "iterations": contract.iterations,
            "tool_calls": contract.tool_calls,
            "agent_calls": contract.agent_calls,
            "retries": contract.retry_count,
            "duration_seconds": (
                (contract.finished_at - contract.started_at).total_seconds()
                if contract.started_at and contract.finished_at
                else None
            ),
            "stop_reason": contract.stop_conditions.reason,
            "artifacts": [
                s.artifacts for s in contract.steps if s.artifacts
            ],
        }

    # ─── Internal Decision Helpers ───────────────────────────────────

    def _on_success(self, current: TaskState, result: AgentResult) -> SupervisorDecision:
        """Decide next state after a successful agent result."""
        if current == TaskState.ANALYZE:
            return SupervisorDecision(
                next_state=TaskState.PLAN,
                reason="Analysis complete, moving to planning",
            )
        elif current == TaskState.PLAN:
            risk = self._contract.risk_level if self._contract else RiskLevel.LOW
            if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                return SupervisorDecision(
                    next_state=TaskState.WAITING_APPROVAL,
                    reason=f"High-risk plan requires approval (risk={risk.value})",
                )
            return SupervisorDecision(
                next_state=TaskState.EXECUTE,
                reason="Plan approved (auto), moving to execution",
            )
        elif current == TaskState.EXECUTE:
            return SupervisorDecision(
                next_state=TaskState.VERIFY,
                reason="Execution complete, moving to verification",
            )
        elif current == TaskState.VERIFY:
            return SupervisorDecision(
                next_state=TaskState.FINALIZE,
                reason="Verification passed, finalizing",
            )
        elif current == TaskState.REPAIR:
            return SupervisorDecision(
                next_state=TaskState.EXECUTE,
                reason="Repair succeeded, re-executing",
            )
        elif current == TaskState.FINALIZE:
            return SupervisorDecision(
                next_state=TaskState.COMPLETED,
                reason="Task completed successfully",
            )
        else:
            return SupervisorDecision(
                next_state=TaskState.VERIFY,
                reason=f"Success in {current.value}, verifying",
            )

    def _on_partial(self, current: TaskState, result: AgentResult) -> SupervisorDecision:
        """Decide next state after a partial result."""
        if current == TaskState.EXECUTE:
            # Continue executing
            return SupervisorDecision(
                next_state=TaskState.VERIFY,
                reason="Partial execution, verifying progress",
            )
        return SupervisorDecision(
            next_state=TaskState.EXECUTE,
            reason=f"Partial in {current.value}, continuing execution",
        )

    def _on_failure(
        self, current: TaskState, result: AgentResult, contract: TaskContract
    ) -> SupervisorDecision:
        """Decide next state after a failure."""
        failure_sig = f"{result.agent_type}:{result.error or result.summary}"
        contract.record_failure(failure_sig)

        # Check repeated-failure hard stop
        if contract.repeated_failure_count >= contract.budget.max_repeated_failures:
            contract.stop_conditions.loop_detected = True
            return SupervisorDecision(
                next_state=TaskState.FAILED,
                reason=f"Loop detected: {contract.repeated_failure_count} identical failures",
            )

        # Check retry budget (> not >=: the current failure gets one repair attempt)
        if contract.retry_count > contract.budget.max_retries:
            contract.stop_conditions.budget_exhausted = True
            return SupervisorDecision(
                next_state=TaskState.FAILED,
                reason=f"Retry budget exhausted ({contract.budget.max_retries} retries)",
            )

        # Try repair
        if self._fsm.can_transition(TaskState.REPAIR):
            return SupervisorDecision(
                next_state=TaskState.REPAIR,
                reason=f"Failure in {current.value}: {result.error or result.summary}",
            )

        return SupervisorDecision(
            next_state=TaskState.FAILED,
            reason=f"Unrecoverable failure in {current.value}: {result.error or result.summary}",
        )

    # ─── State Machine Wrapper ───────────────────────────────────────

    def _transition(self, to_state: TaskState, reason: str):
        """Wrapper around FSM transition with logging."""
        assert self._fsm is not None
        try:
            return self._fsm.transition(to_state, reason)
        except InvalidTransitionError:
            logger.error(f"Invalid transition from {self._fsm.state.value} to {to_state.value}: {reason}")
            raise
