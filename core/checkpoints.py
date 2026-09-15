"""
HELIOS — Checkpoint Manager (Phase 2)
Persists TaskContracts to SQLite for crash recovery and state inspection.
"""

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from db import get_db
from core.task_contract import TaskContract
from core.state_machine import TERMINAL_STATES, TaskState

logger = logging.getLogger("helios.checkpoints")

class CheckpointManager:
    """Handles saving and loading of TaskContracts to SQLite."""

    def save_checkpoint(self, contract: TaskContract) -> bool:
        """Upsert the full contract state to the database."""
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            # Serialize the entire contract via Pydantic
            serialized = contract.model_dump_json()
            
            cursor.execute("""
                INSERT INTO task_checkpoints (task_id, objective, state, serialized_contract, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(task_id) DO UPDATE SET
                    objective=excluded.objective,
                    state=excluded.state,
                    serialized_contract=excluded.serialized_contract,
                    updated_at=CURRENT_TIMESTAMP
            """, (
                contract.task_id,
                contract.objective,
                contract.current_state,
                serialized
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to save checkpoint for {contract.task_id}: {e}")
            return False

    def load_checkpoint(self, task_id: str) -> Optional[TaskContract]:
        """Load a contract from the database by ID."""
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT serialized_contract FROM task_checkpoints WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
                
            return TaskContract.model_validate_json(row["serialized_contract"])
        except Exception as e:
            logger.error(f"Failed to load checkpoint {task_id}: {e}")
            return None

    def list_pending_tasks(self) -> List[TaskContract]:
        """Return all tasks that are not in a terminal state."""
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            # Get states that are not terminal
            terminal_values = [s.value for s in TERMINAL_STATES]
            placeholders = ",".join("?" for _ in terminal_values)
            
            cursor.execute(
                f"SELECT serialized_contract FROM task_checkpoints WHERE state NOT IN ({placeholders})",
                terminal_values
            )
            rows = cursor.fetchall()
            conn.close()
            
            tasks = []
            for row in rows:
                try:
                    tasks.append(TaskContract.model_validate_json(row["serialized_contract"]))
                except Exception as ex:
                    logger.warning(f"Skipping corrupted checkpoint: {ex}")
            return tasks
        except Exception as e:
            logger.error(f"Failed to list pending tasks: {e}")
            return []
