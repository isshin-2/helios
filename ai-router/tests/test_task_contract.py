"""Tests for core.task_contract — TaskContract, TaskBudget, StopConditions, StepRecord."""

import time
from datetime import datetime, timezone, timedelta

import pytest

from core.task_contract import (
    RiskLevel,
    StepRecord,
    TaskBudget,
    TaskCapability,
    TaskContract,
    StopConditions,
)


# ─── TaskBudget ──────────────────────────────────────────────────────────────

class TestTaskBudget:
    def test_defaults(self):
        b = TaskBudget()
        assert b.max_iterations == 10
        assert b.max_tool_calls == 50
        assert b.max_retries == 3

    def test_custom_values(self):
        b = TaskBudget(max_iterations=5, max_tool_calls=20)
        assert b.max_iterations == 5
        assert b.max_tool_calls == 20

    def test_min_iteration_enforced(self):
        with pytest.raises(Exception):
            TaskBudget(max_iterations=0)


# ─── StopConditions ──────────────────────────────────────────────────────────

class TestStopConditions:
    def test_no_conditions(self):
        sc = StopConditions()
        assert not sc.should_stop
        assert sc.reason == "No stop condition met"

    def test_single_condition(self):
        sc = StopConditions(success=True)
        assert sc.should_stop
        assert "succeeded" in sc.reason.lower()

    def test_multiple_conditions(self):
        sc = StopConditions(budget_exhausted=True, loop_detected=True)
        assert sc.should_stop
        assert "Budget" in sc.reason
        assert "Loop" in sc.reason


# ─── StepRecord ──────────────────────────────────────────────────────────────

class TestStepRecord:
    def test_defaults(self):
        s = StepRecord()
        assert s.step_id  # auto-generated
        assert s.agent_id is None
        assert s.artifacts == []

    def test_with_data(self):
        s = StepRecord(agent_id="agent_1", action="write_file", tool_name="terminal")
        assert s.agent_id == "agent_1"
        assert s.tool_name == "terminal"


# ─── TaskContract ────────────────────────────────────────────────────────────

class TestTaskContract:
    def test_create_minimal(self):
        tc = TaskContract(objective="Run tests")
        assert tc.task_id  # auto-generated
        assert tc.objective == "Run tests"
        assert tc.current_state == "IDLE"
        assert tc.iterations == 0

    def test_budget_check_passes(self):
        tc = TaskContract(objective="test")
        assert tc.check_budget() is None

    def test_budget_check_iterations(self):
        tc = TaskContract(
            objective="test",
            budget=TaskBudget(max_iterations=2),
            iterations=2,
        )
        reason = tc.check_budget()
        assert reason is not None
        assert "iterations" in reason.lower()

    def test_budget_check_tool_calls(self):
        tc = TaskContract(
            objective="test",
            budget=TaskBudget(max_tool_calls=3),
            tool_calls=3,
        )
        reason = tc.check_budget()
        assert reason is not None
        assert "tool calls" in reason.lower()

    def test_budget_check_runtime(self):
        tc = TaskContract(
            objective="test",
            budget=TaskBudget(max_runtime_seconds=0.001),
            started_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        reason = tc.check_budget()
        assert reason is not None
        assert "runtime" in reason.lower()

    def test_record_step(self):
        tc = TaskContract(objective="test")
        step = StepRecord(agent_id="a1", tool_name="terminal")
        tc.record_step(step)
        assert len(tc.steps) == 1
        assert tc.agent_calls == 1
        assert tc.tool_calls == 1

    def test_record_step_no_agent(self):
        tc = TaskContract(objective="test")
        step = StepRecord(tool_name="terminal")
        tc.record_step(step)
        assert tc.agent_calls == 0
        assert tc.tool_calls == 1

    def test_record_failure_tracking(self):
        tc = TaskContract(objective="test")
        tc.record_failure("sig_a")
        assert tc.retry_count == 1
        assert tc.repeated_failure_count == 1

        # Different signature resets repeated count
        tc.record_failure("sig_b")
        assert tc.retry_count == 2
        assert tc.repeated_failure_count == 1

        # Same signature increments repeated count
        tc.record_failure("sig_b")
        assert tc.retry_count == 3
        assert tc.repeated_failure_count == 2

    def test_record_success_resets_failures(self):
        tc = TaskContract(objective="test")
        tc.record_failure("sig")
        tc.record_success()
        assert tc.repeated_failure_count == 0
        assert tc.last_failure_signature is None

    def test_finalize_success(self):
        tc = TaskContract(objective="test")
        tc.finalize(success=True)
        assert tc.current_state == "COMPLETED"
        assert tc.stop_conditions.success
        assert tc.finished_at is not None

    def test_finalize_failure(self):
        tc = TaskContract(objective="test")
        tc.finalize(success=False)
        assert tc.current_state == "FAILED"
        assert not tc.stop_conditions.success

    def test_capabilities(self):
        tc = TaskContract(
            objective="test",
            allowed_capabilities={TaskCapability.FILE_READ, TaskCapability.TERMINAL_EXECUTE},
        )
        assert TaskCapability.FILE_READ in tc.allowed_capabilities
        assert TaskCapability.BROWSER_CONTROL not in tc.allowed_capabilities

    def test_parent_child(self):
        parent = TaskContract(objective="parent")
        child = TaskContract(objective="child", parent_task_id=parent.task_id)
        assert child.parent_task_id == parent.task_id

    def test_risk_levels(self):
        tc = TaskContract(objective="test", risk_level=RiskLevel.CRITICAL)
        assert tc.risk_level == RiskLevel.CRITICAL
