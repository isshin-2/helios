"""Tests for core.checkpoints — Task persistence and recovery."""

import os
import sqlite3
import pytest
from datetime import datetime, timezone

from core.task_contract import TaskContract, StepRecord
from core.checkpoints import CheckpointManager
from core.state_machine import TaskState

# We need to use an in-memory db or a temporary test db for isolated testing.
# For simplicity, we'll monkeypatch the db path in the db module.

@pytest.fixture
def test_db(monkeypatch, tmp_path):
    import db
    db_path = str(tmp_path / "test_helios.db")
    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()
    yield db_path
    if os.path.exists(db_path):
        os.remove(db_path)

class TestCheckpointManager:
    def test_save_and_load_checkpoint(self, test_db):
        manager = CheckpointManager()
        
        # Create a contract with some state
        contract = TaskContract(objective="test persistence")
        contract.current_state = TaskState.EXECUTE.value
        contract.record_step(StepRecord(action="do_work", result_summary="done"))
        
        # Save it
        success = manager.save_checkpoint(contract)
        assert success is True
        
        # Load it back
        loaded = manager.load_checkpoint(contract.task_id)
        assert loaded is not None
        assert loaded.task_id == contract.task_id
        assert loaded.objective == "test persistence"
        assert loaded.current_state == TaskState.EXECUTE.value
        assert len(loaded.steps) == 1
        assert loaded.steps[0].action == "do_work"

    def test_update_existing_checkpoint(self, test_db):
        manager = CheckpointManager()
        contract = TaskContract(objective="initial")
        manager.save_checkpoint(contract)
        
        # Modify and save again
        contract.current_state = TaskState.COMPLETED.value
        contract.objective = "updated"
        manager.save_checkpoint(contract)
        
        # Verify update
        loaded = manager.load_checkpoint(contract.task_id)
        assert loaded.current_state == TaskState.COMPLETED.value
        assert loaded.objective == "updated"

    def test_load_nonexistent_checkpoint(self, test_db):
        manager = CheckpointManager()
        loaded = manager.load_checkpoint("does_not_exist")
        assert loaded is None

    def test_list_pending_tasks(self, test_db):
        manager = CheckpointManager()
        
        # Create some tasks in various states
        t1 = TaskContract(objective="pending 1")
        t1.current_state = TaskState.EXECUTE.value
        manager.save_checkpoint(t1)
        
        t2 = TaskContract(objective="completed 1")
        t2.current_state = TaskState.COMPLETED.value
        manager.save_checkpoint(t2)
        
        t3 = TaskContract(objective="pending 2")
        t3.current_state = TaskState.WAITING_APPROVAL.value
        manager.save_checkpoint(t3)
        
        t4 = TaskContract(objective="failed 1")
        t4.current_state = TaskState.FAILED.value
        manager.save_checkpoint(t4)
        
        # Check pending list
        pending = manager.list_pending_tasks()
        assert len(pending) == 2
        pending_ids = {p.task_id for p in pending}
        assert t1.task_id in pending_ids
        assert t3.task_id in pending_ids
        assert t2.task_id not in pending_ids
        assert t4.task_id not in pending_ids
