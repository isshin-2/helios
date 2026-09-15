"""Tests for core.state_machine — TaskStateMachine and transition validation."""

import pytest

from core.state_machine import (
    InvalidTransitionError,
    TaskState,
    TaskStateMachine,
    TERMINAL_STATES,
    TRANSITION_MATRIX,
    TransitionRecord,
)


# ─── Basic Lifecycle ─────────────────────────────────────────────────────────

class TestStateMachineLifecycle:
    def test_initial_state(self):
        fsm = TaskStateMachine()
        assert fsm.state == TaskState.IDLE
        assert not fsm.is_terminal
        assert len(fsm.history) == 0

    def test_happy_path(self):
        """IDLE → ANALYZE → PLAN → EXECUTE → VERIFY → FINALIZE → COMPLETED"""
        fsm = TaskStateMachine()
        fsm.transition(TaskState.ANALYZE, "start")
        fsm.transition(TaskState.PLAN, "analyzed")
        fsm.transition(TaskState.EXECUTE, "planned")
        fsm.transition(TaskState.VERIFY, "executed")
        fsm.transition(TaskState.FINALIZE, "verified")
        fsm.transition(TaskState.COMPLETED, "finalized")

        assert fsm.state == TaskState.COMPLETED
        assert fsm.is_terminal
        assert len(fsm.history) == 6

    def test_simple_task_skips_plan(self):
        """IDLE → ANALYZE → EXECUTE (skip PLAN)."""
        fsm = TaskStateMachine()
        fsm.transition(TaskState.ANALYZE, "start")
        fsm.transition(TaskState.EXECUTE, "simple task, skip planning")
        assert fsm.state == TaskState.EXECUTE

    def test_repair_cycle(self):
        """EXECUTE → VERIFY → REPAIR → EXECUTE → VERIFY → FINALIZE → COMPLETED"""
        fsm = TaskStateMachine()
        fsm.transition(TaskState.ANALYZE, "start")
        fsm.transition(TaskState.EXECUTE, "go")
        fsm.transition(TaskState.VERIFY, "check")
        fsm.transition(TaskState.REPAIR, "failed verification")
        fsm.transition(TaskState.EXECUTE, "retry")
        fsm.transition(TaskState.VERIFY, "check again")
        fsm.transition(TaskState.FINALIZE, "passed")
        fsm.transition(TaskState.COMPLETED, "done")
        assert fsm.state == TaskState.COMPLETED

    def test_cancellation_from_idle(self):
        fsm = TaskStateMachine()
        fsm.transition(TaskState.CANCELLED, "user cancelled")
        assert fsm.state == TaskState.CANCELLED
        assert fsm.is_terminal

    def test_cancellation_from_execute(self):
        fsm = TaskStateMachine()
        fsm.transition(TaskState.ANALYZE, "start")
        fsm.transition(TaskState.EXECUTE, "go")
        fsm.transition(TaskState.CANCELLED, "abort")
        assert fsm.is_terminal


# ─── Invalid Transitions ─────────────────────────────────────────────────────

class TestInvalidTransitions:
    def test_idle_to_execute_blocked(self):
        """IDLE → EXECUTE is not allowed (must ANALYZE first)."""
        fsm = TaskStateMachine()
        with pytest.raises(InvalidTransitionError) as exc_info:
            fsm.transition(TaskState.EXECUTE, "skip everything")
        assert exc_info.value.from_state == TaskState.IDLE
        assert exc_info.value.to_state == TaskState.EXECUTE

    def test_completed_to_anything_blocked(self):
        """Terminal states have no outgoing transitions."""
        fsm = TaskStateMachine()
        fsm.transition(TaskState.ANALYZE, "start")
        fsm.transition(TaskState.EXECUTE, "go")
        fsm.transition(TaskState.VERIFY, "check")
        fsm.transition(TaskState.FINALIZE, "done")
        fsm.transition(TaskState.COMPLETED, "finished")

        for state in TaskState:
            with pytest.raises(InvalidTransitionError):
                fsm.transition(state, "try escape")

    def test_failed_to_anything_blocked(self):
        fsm = TaskStateMachine()
        fsm.transition(TaskState.ANALYZE, "start")
        fsm.transition(TaskState.FAILED, "crash")

        with pytest.raises(InvalidTransitionError):
            fsm.transition(TaskState.EXECUTE, "zombie")

    def test_cancelled_to_anything_blocked(self):
        fsm = TaskStateMachine()
        fsm.transition(TaskState.CANCELLED, "abort")

        with pytest.raises(InvalidTransitionError):
            fsm.transition(TaskState.IDLE, "reset")


# ─── can_transition ──────────────────────────────────────────────────────────

class TestCanTransition:
    def test_valid(self):
        fsm = TaskStateMachine()
        assert fsm.can_transition(TaskState.ANALYZE)
        assert not fsm.can_transition(TaskState.EXECUTE)

    def test_terminal(self):
        fsm = TaskStateMachine()
        fsm.transition(TaskState.CANCELLED, "done")
        assert not fsm.can_transition(TaskState.IDLE)
        assert not fsm.can_transition(TaskState.CANCELLED)


# ─── Hooks ───────────────────────────────────────────────────────────────────

class TestHooks:
    def test_on_enter_fires(self):
        events = []
        fsm = TaskStateMachine()
        fsm.on_enter(TaskState.ANALYZE, lambda f, t, r: events.append(("enter", t.value)))
        fsm.transition(TaskState.ANALYZE, "start")
        assert ("enter", "ANALYZE") in events

    def test_on_exit_fires(self):
        events = []
        fsm = TaskStateMachine()
        fsm.on_exit(TaskState.IDLE, lambda f, t, r: events.append(("exit", f.value)))
        fsm.transition(TaskState.ANALYZE, "start")
        assert ("exit", "IDLE") in events

    def test_hook_error_does_not_block_transition(self):
        def bad_hook(f, t, r):
            raise RuntimeError("boom")

        fsm = TaskStateMachine()
        fsm.on_enter(TaskState.ANALYZE, bad_hook)
        # Should not raise
        fsm.transition(TaskState.ANALYZE, "start")
        assert fsm.state == TaskState.ANALYZE


# ─── History ─────────────────────────────────────────────────────────────────

class TestHistory:
    def test_history_records(self):
        fsm = TaskStateMachine()
        fsm.transition(TaskState.ANALYZE, "step1")
        fsm.transition(TaskState.PLAN, "step2")

        assert len(fsm.history) == 2
        assert fsm.history[0].from_state == TaskState.IDLE
        assert fsm.history[0].to_state == TaskState.ANALYZE
        assert fsm.history[0].reason == "step1"
        assert fsm.history[1].from_state == TaskState.ANALYZE
        assert fsm.history[1].to_state == TaskState.PLAN

    def test_history_is_copy(self):
        fsm = TaskStateMachine()
        fsm.transition(TaskState.ANALYZE, "x")
        h = fsm.history
        h.clear()
        assert len(fsm.history) == 1  # original unmodified


# ─── Allowed Transitions ────────────────────────────────────────────────────

class TestAllowedTransitions:
    def test_from_idle(self):
        fsm = TaskStateMachine()
        allowed = fsm.allowed_transitions()
        assert TaskState.ANALYZE in allowed
        assert TaskState.CANCELLED in allowed
        assert TaskState.EXECUTE not in allowed

    def test_from_terminal(self):
        fsm = TaskStateMachine()
        fsm.transition(TaskState.CANCELLED, "done")
        assert fsm.allowed_transitions() == set()


# ─── Matrix Completeness ────────────────────────────────────────────────────

class TestTransitionMatrix:
    def test_all_states_present(self):
        """Every TaskState must appear as a key in the transition matrix."""
        for state in TaskState:
            assert state in TRANSITION_MATRIX, f"Missing state: {state.value}"

    def test_terminal_states_have_no_outgoing(self):
        for state in TERMINAL_STATES:
            assert TRANSITION_MATRIX[state] == set(), f"{state.value} should have no outgoing"
