"""
HELIOS — Task State Machine
Formal, validated state machine for task lifecycle transitions.
Every transition is validated against an explicit allow-list matrix.
Invalid transitions are rejected with a clear error.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger("helios.state_machine")


# ─── States ─────────────────────────────────────────────────────────────────

class TaskState(str, Enum):
    """
    The twelve formal states of a HELIOS task.
    Mirrors the specification's lifecycle diagram.
    """
    IDLE = "IDLE"                       # Contract created, not yet started
    ANALYZE = "ANALYZE"                 # Breaking down the objective
    PLAN = "PLAN"                       # Building an execution plan
    EXECUTE = "EXECUTE"                 # Running agents/tools
    VERIFY = "VERIFY"                   # Checking results
    REPAIR = "REPAIR"                   # Recovering from verified failure
    WAITING_APPROVAL = "WAITING_APPROVAL"  # Blocked on human approval
    WAITING_USER = "WAITING_USER"       # Blocked on user input
    PAUSED = "PAUSED"                   # Manually paused
    FAILED = "FAILED"                   # Terminal: unrecoverable failure
    FINALIZE = "FINALIZE"              # Cleanup and summary
    COMPLETED = "COMPLETED"            # Terminal: success
    CANCELLED = "CANCELLED"            # Terminal: user-cancelled


# ─── Terminal States ────────────────────────────────────────────────────────

TERMINAL_STATES: Set[TaskState] = {
    TaskState.FAILED,
    TaskState.COMPLETED,
    TaskState.CANCELLED,
}


# ─── Transition Matrix ──────────────────────────────────────────────────────

# Explicit allow-list: key=from_state, value=set of allowed to_states.
# Any transition not in this matrix is REJECTED.
TRANSITION_MATRIX: Dict[TaskState, Set[TaskState]] = {
    TaskState.IDLE: {
        TaskState.ANALYZE,
        TaskState.CANCELLED,
    },
    TaskState.ANALYZE: {
        TaskState.PLAN,
        TaskState.EXECUTE,      # Simple tasks skip planning
        TaskState.FAILED,
        TaskState.CANCELLED,
    },
    TaskState.PLAN: {
        TaskState.EXECUTE,
        TaskState.WAITING_APPROVAL,
        TaskState.FAILED,
        TaskState.CANCELLED,
    },
    TaskState.EXECUTE: {
        TaskState.VERIFY,
        TaskState.WAITING_APPROVAL,
        TaskState.WAITING_USER,
        TaskState.PAUSED,
        TaskState.REPAIR,
        TaskState.FAILED,
        TaskState.CANCELLED,
    },
    TaskState.VERIFY: {
        TaskState.FINALIZE,     # Success → finalize
        TaskState.REPAIR,       # Failure → repair
        TaskState.EXECUTE,      # Re-execute with changes
        TaskState.FAILED,
        TaskState.CANCELLED,
    },
    TaskState.REPAIR: {
        TaskState.EXECUTE,      # Retry after repair
        TaskState.ANALYZE,      # Re-analyze after repair
        TaskState.FAILED,       # Unrecoverable
        TaskState.CANCELLED,
    },
    TaskState.WAITING_APPROVAL: {
        TaskState.EXECUTE,      # Approved
        TaskState.PLAN,         # Approved, continue planning
        TaskState.CANCELLED,    # Rejected
        TaskState.FAILED,
    },
    TaskState.WAITING_USER: {
        TaskState.EXECUTE,      # User provided input
        TaskState.CANCELLED,
    },
    TaskState.PAUSED: {
        TaskState.EXECUTE,      # Resumed
        TaskState.CANCELLED,
    },
    TaskState.FINALIZE: {
        TaskState.COMPLETED,
        TaskState.FAILED,       # Finalization itself failed
    },
    # Terminal states: no outgoing transitions
    TaskState.FAILED: set(),
    TaskState.COMPLETED: set(),
    TaskState.CANCELLED: set(),
}


# ─── Transition Record ──────────────────────────────────────────────────────

class TransitionRecord(BaseModel):
    """Immutable record of a state transition."""
    from_state: TaskState
    to_state: TaskState
    reason: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ─── Transition Error ───────────────────────────────────────────────────────

class InvalidTransitionError(Exception):
    """Raised when a state transition violates the transition matrix."""

    def __init__(self, from_state: TaskState, to_state: TaskState, reason: str = ""):
        self.from_state = from_state
        self.to_state = to_state
        msg = f"Invalid transition: {from_state.value} → {to_state.value}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)


# ─── State Machine ──────────────────────────────────────────────────────────

class TaskStateMachine:
    """
    Strict, validated state machine for a single task's lifecycle.

    Features:
    - Explicit transition validation against TRANSITION_MATRIX
    - Full transition history (audit trail)
    - Hook system for on_enter / on_exit callbacks
    - Terminal state detection
    """

    def __init__(self, initial_state: TaskState = TaskState.IDLE):
        self._state = initial_state
        self._history: List[TransitionRecord] = []
        self._on_enter: Dict[TaskState, List[Callable]] = {}
        self._on_exit: Dict[TaskState, List[Callable]] = {}

    # ─── Properties ──────────────────────────────────────────────────

    @property
    def state(self) -> TaskState:
        return self._state

    @property
    def is_terminal(self) -> bool:
        return self._state in TERMINAL_STATES

    @property
    def history(self) -> List[TransitionRecord]:
        return list(self._history)

    # ─── Core Transition ─────────────────────────────────────────────

    def transition(self, to_state: TaskState, reason: str = "") -> TransitionRecord:
        """
        Attempt a state transition. Raises InvalidTransitionError if the
        transition is not allowed by the matrix.
        """
        from_state = self._state

        # Block transitions out of terminal states
        if from_state in TERMINAL_STATES:
            raise InvalidTransitionError(
                from_state, to_state,
                f"Cannot transition out of terminal state {from_state.value}"
            )

        # Validate against the matrix
        allowed = TRANSITION_MATRIX.get(from_state, set())
        if to_state not in allowed:
            raise InvalidTransitionError(
                from_state, to_state,
                f"Allowed transitions from {from_state.value}: "
                f"{[s.value for s in sorted(allowed, key=lambda s: s.value)]}"
            )

        # Fire on_exit hooks
        for hook in self._on_exit.get(from_state, []):
            try:
                hook(from_state, to_state, reason)
            except Exception as exc:
                logger.warning(f"on_exit hook error ({from_state}→{to_state}): {exc}")

        # Perform transition
        record = TransitionRecord(
            from_state=from_state,
            to_state=to_state,
            reason=reason,
        )
        self._state = to_state
        self._history.append(record)

        logger.info(f"State transition: {from_state.value} → {to_state.value} | {reason}")

        # Fire on_enter hooks
        for hook in self._on_enter.get(to_state, []):
            try:
                hook(from_state, to_state, reason)
            except Exception as exc:
                logger.warning(f"on_enter hook error ({from_state}→{to_state}): {exc}")

        return record

    def can_transition(self, to_state: TaskState) -> bool:
        """Check whether a transition is valid without performing it."""
        if self._state in TERMINAL_STATES:
            return False
        return to_state in TRANSITION_MATRIX.get(self._state, set())

    # ─── Hook Registration ───────────────────────────────────────────

    def on_enter(self, state: TaskState, callback: Callable) -> None:
        """Register a callback to fire when entering the given state."""
        self._on_enter.setdefault(state, []).append(callback)

    def on_exit(self, state: TaskState, callback: Callable) -> None:
        """Register a callback to fire when leaving the given state."""
        self._on_exit.setdefault(state, []).append(callback)

    # ─── Utilities ───────────────────────────────────────────────────

    def allowed_transitions(self) -> Set[TaskState]:
        """Return the set of states reachable from the current state."""
        if self._state in TERMINAL_STATES:
            return set()
        return TRANSITION_MATRIX.get(self._state, set())

    def __repr__(self) -> str:
        return f"TaskStateMachine(state={self._state.value}, steps={len(self._history)})"
