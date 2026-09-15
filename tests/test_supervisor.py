"""Tests for core.supervisor — Supervisor lifecycle, budget enforcement, loop detection."""

from datetime import datetime, timezone, timedelta

import pytest

from agents.base import AgentResult, AgentStatus
from core.state_machine import InvalidTransitionError, TaskState
from core.supervisor import Supervisor, SupervisorDecision
from core.task_contract import TaskBudget, TaskContract, RiskLevel


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_result(
    status: AgentStatus = AgentStatus.SUCCESS,
    summary: str = "ok",
    error: str = None,
    agent_type: str = "test_agent",
) -> AgentResult:
    return AgentResult(
        agent_id="test_1",
        agent_type=agent_type,
        status=status,
        summary=summary,
        error=error,
    )


def _run_to_execute(supervisor: Supervisor, contract: TaskContract) -> None:
    """Helper: advance supervisor to EXECUTE state."""
    supervisor.start(contract)  # IDLE → ANALYZE
    decision = supervisor.evaluate(_make_result(AgentStatus.SUCCESS, "analyzed"))
    supervisor.apply(decision)  # ANALYZE → PLAN
    decision = supervisor.evaluate(_make_result(AgentStatus.SUCCESS, "planned"))
    supervisor.apply(decision)  # PLAN → EXECUTE


# ─── Lifecycle ───────────────────────────────────────────────────────────────

class TestSupervisorLifecycle:
    def test_start(self):
        sv = Supervisor()
        contract = TaskContract(objective="test")
        sv.start(contract)
        assert sv.state == TaskState.ANALYZE
        assert sv.is_active
        assert not sv.is_done

    def test_happy_path(self):
        """Full lifecycle: start → analyze → plan → execute → verify → finalize → complete."""
        sv = Supervisor()
        contract = TaskContract(objective="test")
        sv.start(contract)

        # ANALYZE → success → PLAN
        d = sv.evaluate(_make_result(AgentStatus.SUCCESS, "analyzed"))
        assert d.next_state == TaskState.PLAN
        sv.apply(d)

        # PLAN → success → EXECUTE
        d = sv.evaluate(_make_result(AgentStatus.SUCCESS, "planned"))
        assert d.next_state == TaskState.EXECUTE
        sv.apply(d)

        # EXECUTE → success → VERIFY
        d = sv.evaluate(_make_result(AgentStatus.SUCCESS, "executed"))
        assert d.next_state == TaskState.VERIFY
        sv.apply(d)

        # VERIFY → success → FINALIZE
        d = sv.evaluate(_make_result(AgentStatus.SUCCESS, "verified"))
        assert d.next_state == TaskState.FINALIZE
        sv.apply(d)

        # FINALIZE → success → COMPLETED
        d = sv.evaluate(_make_result(AgentStatus.SUCCESS, "finalized"))
        assert d.next_state == TaskState.COMPLETED
        sv.apply(d)

        assert sv.is_done
        assert sv.state == TaskState.COMPLETED

    def test_cancel(self):
        sv = Supervisor()
        contract = TaskContract(objective="test")
        sv.start(contract)
        sv.cancel("changed mind")
        assert sv.state == TaskState.CANCELLED
        assert sv.is_done
        assert contract.stop_conditions.user_cancelled

    def test_pause_resume(self):
        sv = Supervisor()
        contract = TaskContract(objective="test")
        _run_to_execute(sv, contract)

        sv.pause("lunch break")
        assert sv.state == TaskState.PAUSED

        sv.resume()
        assert sv.state == TaskState.EXECUTE

    def test_finalize_task_returns_summary(self):
        sv = Supervisor()
        contract = TaskContract(objective="test task")
        sv.start(contract)

        # Run through to completion
        d = sv.evaluate(_make_result(AgentStatus.SUCCESS, "a"))
        sv.apply(d)
        d = sv.evaluate(_make_result(AgentStatus.SUCCESS, "p"))
        sv.apply(d)
        d = sv.evaluate(_make_result(AgentStatus.SUCCESS, "e"))
        sv.apply(d)
        d = sv.evaluate(_make_result(AgentStatus.SUCCESS, "v"))
        sv.apply(d)
        d = sv.evaluate(_make_result(AgentStatus.SUCCESS, "f"))
        sv.apply(d)

        summary = sv.finalize_task()
        assert summary["task_id"] == contract.task_id
        assert summary["success"] is True
        assert summary["status"] == "COMPLETED"
        assert summary["steps_count"] == 5


# ─── Budget Enforcement ─────────────────────────────────────────────────────

class TestBudgetEnforcement:
    def test_iteration_budget(self):
        sv = Supervisor()
        contract = TaskContract(
            objective="test",
            budget=TaskBudget(max_iterations=2),
            iterations=2,  # Already at limit
        )
        sv.start(contract)  # This adds 1 iteration, now at 3 ≥ 2

        d = sv.evaluate(_make_result(AgentStatus.SUCCESS, "ok"))
        assert d.next_state == TaskState.FAILED
        assert "budget" in d.reason.lower() or "iterations" in d.reason.lower()

    def test_tool_call_budget(self):
        sv = Supervisor()
        contract = TaskContract(
            objective="test",
            budget=TaskBudget(max_tool_calls=1),
            tool_calls=1,  # At limit
        )
        sv.start(contract)

        d = sv.evaluate(_make_result(AgentStatus.SUCCESS, "ok"))
        assert d.next_state == TaskState.FAILED

    def test_retry_budget(self):
        sv = Supervisor()
        contract = TaskContract(
            objective="test",
            budget=TaskBudget(max_retries=1),
        )
        _run_to_execute(sv, contract)

        # First failure → REPAIR
        d = sv.evaluate(_make_result(AgentStatus.FAILURE, "oops", error="err"))
        assert d.next_state == TaskState.REPAIR
        sv.apply(d)

        # Repair succeeds → EXECUTE
        d = sv.evaluate(_make_result(AgentStatus.SUCCESS, "fixed"))
        sv.apply(d)

        # Second failure → FAILED (retry budget exhausted)
        d = sv.evaluate(_make_result(AgentStatus.FAILURE, "oops again", error="err2"))
        assert d.next_state == TaskState.FAILED
        assert contract.stop_conditions.budget_exhausted


# ─── Loop Detection ─────────────────────────────────────────────────────────

class TestLoopDetection:
    def test_repeated_failures_trigger_loop_detection(self):
        sv = Supervisor()
        contract = TaskContract(
            objective="test",
            budget=TaskBudget(max_retries=10, max_repeated_failures=3),
        )
        _run_to_execute(sv, contract)

        for i in range(2):
            d = sv.evaluate(_make_result(
                AgentStatus.FAILURE, "same error", error="same_err"
            ))
            # Should go to REPAIR
            assert d.next_state == TaskState.REPAIR
            sv.apply(d)
            d = sv.evaluate(_make_result(AgentStatus.SUCCESS, "repaired"))
            sv.apply(d)  # → EXECUTE

        # Third identical failure → loop detected
        d = sv.evaluate(_make_result(
            AgentStatus.FAILURE, "same error", error="same_err"
        ))
        assert d.next_state == TaskState.FAILED
        assert contract.stop_conditions.loop_detected

    def test_different_failures_dont_trigger_loop(self):
        sv = Supervisor()
        contract = TaskContract(
            objective="test",
            budget=TaskBudget(max_retries=10, max_repeated_failures=3),
        )
        _run_to_execute(sv, contract)

        for i in range(3):
            d = sv.evaluate(_make_result(
                AgentStatus.FAILURE, f"error_{i}", error=f"err_{i}"
            ))
            # Different error each time — should NOT trigger loop
            assert d.next_state == TaskState.REPAIR
            sv.apply(d)
            d = sv.evaluate(_make_result(AgentStatus.SUCCESS, "fixed"))
            sv.apply(d)


# ─── Approval Flow ───────────────────────────────────────────────────────────

class TestApprovalFlow:
    def test_needs_approval(self):
        sv = Supervisor()
        contract = TaskContract(objective="test")
        _run_to_execute(sv, contract)

        d = sv.evaluate(_make_result(AgentStatus.NEEDS_APPROVAL, "risky action"))
        assert d.next_state == TaskState.WAITING_APPROVAL
        sv.apply(d)

        sv.approve()
        assert sv.state == TaskState.EXECUTE

    def test_needs_input(self):
        sv = Supervisor()
        contract = TaskContract(objective="test")
        _run_to_execute(sv, contract)

        d = sv.evaluate(_make_result(AgentStatus.NEEDS_INPUT, "which file?"))
        assert d.next_state == TaskState.WAITING_USER
        sv.apply(d)

        sv.provide_input()
        assert sv.state == TaskState.EXECUTE

    def test_high_risk_plan_requires_approval(self):
        sv = Supervisor()
        contract = TaskContract(
            objective="test",
            risk_level=RiskLevel.HIGH,
        )
        sv.start(contract)

        # Analyze succeeds → PLAN
        d = sv.evaluate(_make_result(AgentStatus.SUCCESS, "analyzed"))
        sv.apply(d)

        # Plan succeeds → WAITING_APPROVAL (high risk)
        d = sv.evaluate(_make_result(AgentStatus.SUCCESS, "planned"))
        assert d.next_state == TaskState.WAITING_APPROVAL


# ─── Repair Path ────────────────────────────────────────────────────────────

class TestRepairPath:
    def test_failure_triggers_repair(self):
        sv = Supervisor()
        contract = TaskContract(objective="test")
        _run_to_execute(sv, contract)

        d = sv.evaluate(_make_result(AgentStatus.FAILURE, "broke", error="err"))
        assert d.next_state == TaskState.REPAIR
        sv.apply(d)

        # Repair → EXECUTE
        d = sv.evaluate(_make_result(AgentStatus.SUCCESS, "fixed"))
        assert d.next_state == TaskState.EXECUTE

    def test_verify_failure_triggers_repair(self):
        sv = Supervisor()
        contract = TaskContract(objective="test")
        _run_to_execute(sv, contract)

        # Execute succeeds → VERIFY
        d = sv.evaluate(_make_result(AgentStatus.SUCCESS, "ran"))
        sv.apply(d)

        # Verify fails → REPAIR
        d = sv.evaluate(_make_result(AgentStatus.FAILURE, "tests failed", error="assert"))
        assert d.next_state == TaskState.REPAIR


# ─── Step Recording ─────────────────────────────────────────────────────────

class TestStepRecording:
    def test_steps_are_recorded(self):
        sv = Supervisor()
        contract = TaskContract(objective="test")
        sv.start(contract)

        sv.evaluate(_make_result(AgentStatus.SUCCESS, "step1"))
        assert len(contract.steps) == 1
        assert contract.steps[0].result_summary == "step1"
        assert contract.agent_calls == 1
