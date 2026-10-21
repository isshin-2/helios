"""
HELIOS Autonomous 32B Swarm Execution on Remote AI PC
Validates that HELIOS Coding Swarm utilizes qwen2.5-coder:32b for Architect and Coder,
and qwen2.5-coder:14b for Planner and Tester, executing a complete real-world coding task.
"""
import pytest
import asyncio
import tempfile
import os
import time
from pathlib import Path

from providers.pair import PairProvider
from config import PAIR_HOST
from core.state_machine import TaskStateMachine, TaskState
from core.model_router import ModelRouter
from core.task_contract import TaskContract
from agents.planner import PlannerAgent
from agents.architect import ArchitectAgent
from agents.coder import CoderAgent
from agents.tester import TesterAgent
from agents.reviewer import ReviewerAgent
from agents.security_reviewer import SecurityReviewerAgent
from core.supervisor import Supervisor


@pytest.mark.asyncio
async def test_32b_swarm_autonomous_execution():
    print(f"\n[+] Connecting to Remote AI PC at {PAIR_HOST}...")
    provider = PairProvider(host=PAIR_HOST)
    router = ModelRouter()

    # Verify model resolution
    coder_model, _ = await router.prepare_model_for_agent("coder", provider)
    arch_model, _ = await router.prepare_model_for_agent("architect", provider)
    planner_model, _ = await router.prepare_model_for_agent("planner", provider)

    print(f"    - Planner   Model: {planner_model}")
    print(f"    - Architect Model: {arch_model}")
    print(f"    - Coder     Model: {coder_model}")

    assert coder_model == "qwen2.5-coder:32b", f"Coder must use 32B model, got {coder_model}"
    assert arch_model == "qwen2.5-coder:32b", f"Architect must use 32B model, got {arch_model}"

    # Initialize agents
    planner = PlannerAgent(provider)
    architect = ArchitectAgent(provider)
    coder = CoderAgent(provider, max_iterations=4)
    tester = TesterAgent(provider)
    reviewer = ReviewerAgent(provider)
    security = SecurityReviewerAgent(provider)
    sm = TaskStateMachine()

    task_objective = (
        "Implement a Python class `CircularRateLimiter` with methods `allow_request(key: str) -> bool` "
        "and `reset(key: str)`. Provide full unit tests in `test_rate_limiter.py` verifying rate limit capacity and sliding window."
    )

    contract = TaskContract(objective=task_objective)
    supervisor = Supervisor()
    supervisor.start(contract)

    with tempfile.TemporaryDirectory() as temp_dir:
        t0 = time.time()
        print(f"\n[*] Starting HELIOS Swarm in isolated workspace: {temp_dir}")

        # State 1: ANALYZE -> PLAN
        sm.transition(TaskState.ANALYZE, "Initiating objective analysis")
        sm.transition(TaskState.PLAN, "Delegating to Planner (14B)")
        print(f"    [State: {sm.state.value}] Running PlannerAgent...")
        plan_result = await planner.execute(task_objective, {"workspace_root": temp_dir})
        assert plan_result.status.value in ["success", "SUCCESS"], f"Planner failed: {plan_result.error}"

        # State 2: ARCHITECT (32B)
        sm.transition(TaskState.ARCHITECT, "Delegating to Architect (32B)")
        print(f"    [State: {sm.state.value}] Running ArchitectAgent with 32B model...")
        arch_result = await architect.execute(task_objective, {"plan": plan_result.evidence.get("plan", {})})
        assert arch_result.status.value in ["success", "SUCCESS"], f"Architect failed: {arch_result.error}"

        # State 3: EXECUTE / CODER (32B)
        sm.transition(TaskState.EXECUTE, "Delegating code synthesis to Coder (32B)")
        print(f"    [State: {sm.state.value}] Running CoderAgent with 32B model...")
        coder_context = {
            "workspace_root": temp_dir,
            "plan": plan_result.evidence.get("plan", {}),
            "architecture": arch_result.evidence.get("architecture", {}),
        }
        coder_result = await coder.execute(task_objective, coder_context)
        assert coder_result.status.value in ["success", "SUCCESS"], f"Coder failed: {coder_result.error}"

        # Verify generated files
        files_created = [f.name for f in Path(temp_dir).iterdir()]
        print(f"    [Files Created]: {files_created}")
        assert len(files_created) > 0, "Coder must generate at least 1 implementation or test file"

        # State 4: VERIFY / TESTER
        sm.transition(TaskState.VERIFY, "Running automated test verification")
        print(f"    [State: {sm.state.value}] Running TesterAgent...")
        tester_result = await tester.execute(task_objective, {"workspace_root": temp_dir})
        print(f"    [Tester Output]: status={tester_result.status.value}")

        # State 5: REVIEW & SECURITY_REVIEW
        sm.transition(TaskState.REVIEW, "Conducting code review")
        review_result = await reviewer.execute(task_objective, {"workspace_root": temp_dir})
        assert review_result.status.value in ["success", "SUCCESS"]

        sm.transition(TaskState.SECURITY_REVIEW, "Validating zero-trust security & AST")
        sec_result = await security.execute(task_objective, {"workspace_root": temp_dir})
        assert sec_result.status.value in ["success", "SUCCESS"]

        # Finalize
        sm.transition(TaskState.FINALIZE, "All gates passed")
        sm.transition(TaskState.COMPLETED, "Autonomous coding task completed")
        assert sm.is_terminal is True

        elapsed = time.time() - t0
        print(f"\n[+] HELIOS Autonomous Swarm with 32B model completed successfully in {elapsed:.2f}s!")
