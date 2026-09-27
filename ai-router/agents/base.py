"""
HELIOS — Base Agent
Abstract base class for all HELIOS agents and the AgentResult structured output.
Every agent (LLM-backed, tool-backed, or composite) extends BaseAgent.
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("helios.agents.base")


# ─── Agent Status ────────────────────────────────────────────────────────────

class AgentStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"         # Made progress but didn't fully complete
    NEEDS_INPUT = "needs_input" # Blocked — needs user clarification
    NEEDS_APPROVAL = "needs_approval"  # Blocked — needs human approval
    SKIPPED = "skipped"         # Agent decided action wasn't needed


# ─── Agent Result ────────────────────────────────────────────────────────────

class AgentResult(BaseModel):
    """
    Structured output of every agent execution.
    The Supervisor inspects this to decide the next state transition.
    """
    agent_id: str
    agent_type: str
    status: AgentStatus
    summary: str = Field(description="Human-readable summary of what happened.")
    detail: str = Field(default="", description="Extended detail / reasoning.")
    artifacts: List[str] = Field(
        default_factory=list,
        description="Paths or identifiers of produced artifacts."
    )
    evidence: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured evidence supporting the result."
    )
    next_action: Optional[str] = Field(
        default=None,
        description="Suggested next action for the Supervisor."
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Agent's self-assessed confidence in the result (0.0–1.0)."
    )
    error: Optional[str] = Field(default=None, description="Error message if failed.")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ─── Base Agent ──────────────────────────────────────────────────────────────

class BaseAgent(ABC):
    """
    Abstract base class for all HELIOS agents.

    Subclasses must implement:
        - execute(objective, context) → AgentResult
        - agent_type (property)

    The BaseAgent provides:
        - Unique agent_id
        - Logging
        - A standard result builder (_make_result)
    """

    def __init__(self, agent_id: Optional[str] = None):
        self.agent_id = agent_id or f"{self.agent_type}_{uuid.uuid4().hex[:8]}"
        self.logger = logging.getLogger(f"helios.agents.{self.agent_type}")

    @property
    @abstractmethod
    def agent_type(self) -> str:
        """Short, unique type name for this agent class (e.g. 'browser', 'coder')."""
        ...

    @abstractmethod
    async def execute(
        self,
        objective: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        """
        Execute the agent's task.

        Args:
            objective: What the agent should accomplish.
            context:   Dict of supporting context (conversation history,
                       relevant files, prior agent results, etc.)

        Returns:
            A structured AgentResult.
        """
        ...

    # ─── Helpers ─────────────────────────────────────────────────────

    def _make_result(
        self,
        status: AgentStatus,
        summary: str,
        *,
        detail: str = "",
        artifacts: Optional[List[str]] = None,
        evidence: Optional[Dict[str, Any]] = None,
        next_action: Optional[str] = None,
        confidence: float = 0.5,
        error: Optional[str] = None,
        started_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        """Convenience builder for AgentResult."""
        return AgentResult(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            status=status,
            summary=summary,
            detail=detail,
            artifacts=artifacts or [],
            evidence=evidence or {},
            next_action=next_action,
            confidence=confidence,
            error=error,
            started_at=started_at or datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            metadata=metadata or {},
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.agent_id}>"
