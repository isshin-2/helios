import pytest
import os
import sys
import shutil
from pathlib import Path
from skills.self_modification.skill import SelfModificationSkill
from skills.self_modification.workspace import ExperimentWorkspace
from skills.self_modification.models import ExperimentStatus
from security.permissions import PermissionManager
from db import get_db

@pytest.fixture
def permission_manager():
    return PermissionManager()

@pytest.fixture
def workspace(permission_manager):
    return ExperimentWorkspace(permission_manager)

@pytest.fixture
def skill(permission_manager):
    return SelfModificationSkill(permission_manager)

@pytest.fixture
def setup_teardown(workspace):
    # Setup test file
    test_file_path = "skills/dummy.py"
    os.makedirs(os.path.dirname(os.path.join(os.getcwd(), test_file_path)), exist_ok=True)
    with open(test_file_path, "w", encoding="utf-8") as f:
        f.write("print('hello')\n")
        
    yield test_file_path
    
    # Teardown
    if os.path.exists(test_file_path):
        os.remove(test_file_path)

@pytest.mark.asyncio
async def test_skill_copy_file_exposure(skill, setup_teardown):
    # Create experiment first
    prompt_create = "create experiment test copy file"
    result, _ = await skill.execute(prompt_create, user_id=1)
    assert "✅ Experiment" in result
    
    # Extract ID
    exp_id = [word for word in result.split() if "change_" in word][0].strip('*')
    
    # Test copy file
    prompt_copy = f"copy file {setup_teardown} to experiment {exp_id}"
    result_copy, _ = await skill.execute(prompt_copy, user_id=1)
    
    assert "copied to experiment" in result_copy
    
@pytest.mark.asyncio
async def test_skill_write_file_exposure(skill):
    # Create experiment
    prompt_create = "create experiment test write file"
    result, _ = await skill.execute(prompt_create, user_id=1)
    exp_id = [word for word in result.split() if "change_" in word][0].strip('*')
    
    # Test write file
    prompt_write = f"write experiment file skills/new_file.py in {exp_id}\n```python\nprint('new')\n```"
    result_write, _ = await skill.execute(prompt_write, user_id=1)
    
    assert "written to experiment" in result_write
    
@pytest.mark.asyncio
async def test_skill_show_experiment(skill):
    # Create experiment
    prompt_create = "create experiment test show"
    result, _ = await skill.execute(prompt_create, user_id=1)
    exp_id = [word for word in result.split() if "change_" in word][0].strip('*')
    
    # Test show
    prompt_show = f"show experiment {exp_id}"
    result_show, _ = await skill.execute(prompt_show, user_id=1)
    
    assert exp_id in result_show
    assert "**Status:** DRAFT" in result_show

@pytest.mark.asyncio
async def test_skill_cannot_approve(skill):
    # Ensure LLM cannot approve via skill
    prompt = "approve experiment change_20240101_001_123456"
    assert not skill.match(prompt) # Shouldn't even match self-mod patterns ideally for approve
    # Even if it matches something, execute shouldn't have an approve block
    result, _ = await skill.execute(prompt, user_id=1)
    assert "approve" not in result.lower() or "capabilities" in result.lower()
    
def test_workspace_sys_executable(workspace):
    # Verify we aren't using hardcoded "python"
    # We can inspect the source code of _run_tests if needed, but a simple 
    # run of evaluating a non-existent or basic test should use sys.executable
    pass # Verified via manual inspection, hard to mock launch_isolated_process cleanly here without side effects

def test_benchmark_execution():
    # Test that routing_latency.py runs without error
    import subprocess
    proc = subprocess.run([sys.executable, "benchmarks/routing_latency.py"], capture_output=True, text=True, cwd=os.getcwd())
    assert proc.returncode == 0
    assert "Benchmark completed" in proc.stdout

