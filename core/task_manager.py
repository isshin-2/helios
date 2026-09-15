import asyncio
import logging
from enum import Enum, auto
from typing import Dict, Any, Optional
from datetime import datetime
from core.telemetry import telemetry

logger = logging.getLogger(__name__)

class TaskState(Enum):
    CREATED = auto()
    RUNNING = auto()
    WAITING_APPROVAL = auto()
    PAUSED = auto()
    CANCELLED = auto()
    COMPLETED = auto()
    FAILED = auto()

class Task:
    def __init__(self, task_id: str, objective: str, user_id: int):
        self.task_id = task_id
        self.objective = objective
        self.user_id = user_id
        self.state: TaskState = TaskState.CREATED
        self.history: list = []
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.metadata: Dict[str, Any] = {}
        
    def transition(self, new_state: TaskState, reason: str = ""):
        old_state = self.state
        self.state = new_state
        self.updated_at = datetime.utcnow()
        self.history.append({
            "timestamp": self.updated_at.isoformat(),
            "from": old_state.name,
            "to": new_state.name,
            "reason": reason
        })
        logger.info(f"Task {self.task_id} transitioned {old_state.name} -> {new_state.name}: {reason}")
        telemetry.record_event("task_transition", self.task_id, {"from": old_state.name, "to": new_state.name, "reason": reason})

class TaskManager:
    """
    Phase 4: TASK_MANAGER Implementation
    Enforces LLM != Task State Authority.
    Tracks all long-running tasks independently of the LLM generation loop.
    """
    def __init__(self):
        self.tasks: Dict[str, Task] = {}

    def create_task(self, task_id: str, objective: str, user_id: int) -> Task:
        task = Task(task_id, objective, user_id)
        self.tasks[task_id] = task
        logger.info(f"Task {task_id} created: {objective}")
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def update_task_state(self, task_id: str, new_state: TaskState, reason: str = ""):
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        task.transition(new_state, reason)

    def is_active(self, task_id: str) -> bool:
        task = self.get_task(task_id)
        if not task:
            return False
        return task.state in (TaskState.CREATED, TaskState.RUNNING, TaskState.WAITING_APPROVAL)

# Global Task Manager
task_manager = TaskManager()
