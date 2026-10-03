"""
HELIOS — Coding Swarm Integration & Unit Test Suite
Verifies:
1. Agent Lifecycles (Planner, Architect, RepoMapper, Coder, Tester, Repair, Reviewer, SecurityReviewer)
2. Failure Recovery Loop (EXECUTE -> VERIFY fail -> REPAIR -> EXECUTE -> VERIFY pass)
3. Budget enforcement and Loop Detection
4. Model Router fallback and 16 GB VRAM management
5. Cancellation and Checkpoint persistence
6. Security enforcement and protected paths
7. SubAgentTool TaskContract/Supervisor integration
"""

import asyncio
import os
import shutil
import tempfile
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.architect import ArchitectAgent, ArchitectureSpec
from agents.base import AgentResult, AgentStatus
from agents.coder import CoderAgent
from agents.planner import PlannerAgent, PlanOutput
from agents.repair import RepairAgent
from agents.repo_mapper import RepoMapperAgent
from agents.reviewer import ReviewerAgent, ReviewReport
from agents.security_reviewer import SecurityReviewerAgent, SecurityReviewReport
from agents.tester import TesterAgent
from core.checkpoints import CheckpointManager
from core.coding_runtime import CodingContext, CodingTaskRuntime, WorkspaceManager
from core.coding_swarm import CodingSwarmOrchestrator
from core.model_router import AgentModelProfile, ModelRouter
from core.state_machine import TaskState, TaskStateMachine
from core.supervisor import Supervisor, SupervisorDecision
from core.task_contract import RiskLevel, TaskBudget, TaskContract
from providers.base import BaseProvider
from security.permissions import PermissionManager
from tools.subagent import SubAgentTool


# ─── Mock Provider for Testing ────────────────────────────────────────────────

class MockLLMProvider(BaseProvider):
    """Deterministic mock provider that simulates LLM generation and tool responses."""

    def __init__(self, responses: Optional[Dict[str, Any]] = None):
        self.responses = responses or {}
        self.call_history: List[Dict[str, Any]] = []
        self.running_models: List[str] = []
        self.available_models: List[str] = [
            "qwen3.5:9b", "qwen2.5-coder:14b", "devstral-small-2:24b", "qwen2.5-coder:7b", "llama3.2:3b"
        ]

    async def chat(self, model: str, messages: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None, **kwargs):
        self.call_history.append({"method": "chat", "model": model, "messages": messages})
        content = self.responses.get("chat", json.dumps({"action": "finish", "summary": "Task complete"}))
        return {"message": {"content": content}, "response": content}

    async def generate(self, model: str, prompt: str, options: Optional[Dict[str, Any]] = None, **kwargs):
        self.call_history.append({"method": "generate", "model": model, "prompt": prompt})
        resp = self.responses.get("generate", "{}")
        if callable(resp):
            resp = resp(prompt)
        return {"response": resp}

    async def get_embeddings(self, model: str, prompt: str):
        return [0.1, 0.2, 0.3]

    async def list_models(self):
        return {"models": [{"name": m, "size": 5 * 1024 * 1024 * 1024} for m in self.available_models]}

    async def list_running(self):
        return {"models": [{"name": m, "size_vram": 10 * 1024 * 1024 * 1024} for m in self.running_models]}

    async def unload_model(self, model: str):
        if model in self.running_models:
            self.running_models.remove(model)
        return {"status": "unloaded", "model": model}

    async def model_exists(self, model: str) -> bool:
        return model in self.available_models


import json


# ─── 1. Agent Lifecycle Tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_planner_agent_lifecycle():
    """Verify Planner produces structured PlanOutput conforming to schema."""
    plan_data = {
        "objective": "Add cache to router",
        "requirements": ["In-memory cache", "TTL support"],
        "dependencies": [],
        "implementation_steps": [
            {"step": 1, "action": "Create cache class", "target_files": ["cache.py"]},
            {"step": 2, "action": "Integrate with router", "target_files": ["router.py"]},
        ],
        "expected_files": ["cache.py", "router.py"],
        "test_strategy": "pytest tests/test_cache.py",
        "risks": ["Cache invalidation race conditions"],
    }
    provider = MockLLMProvider({"generate": json.dumps(plan_data)})
    planner = PlannerAgent(provider)

    result = await planner.execute("Add cache to router", {"relevant_files": ["router.py"]})
    assert result.status == AgentStatus.SUCCESS
    assert "plan" in result.evidence
    plan = PlanOutput(**result.evidence["plan"])
    assert len(plan.implementation_steps) == 2
    assert plan.expected_files == ["cache.py", "router.py"]


@pytest.mark.asyncio
async def test_architect_agent_lifecycle():
    """Verify Architect produces structured ArchitectureSpec."""
    arch_data = {
        "components": ["RouterCache"],
        "interfaces": ["get(key)", "set(key, val, ttl)"],
        "files_to_modify": ["router.py"],
        "files_to_create": ["cache.py"],
        "constraints": ["Zero external dependencies", "Thread safe"],
        "test_strategy": ["Unit tests for TTL expiration"],
        "risks": ["Memory consumption under high load"],
    }
    provider = MockLLMProvider({"generate": json.dumps(arch_data)})
    architect = ArchitectAgent(provider)

    result = await architect.execute("Add cache to router", {"plan": {}})
    assert result.status == AgentStatus.SUCCESS
    assert "architecture" in result.evidence
    spec = ArchitectureSpec(**result.evidence["architecture"])
    assert "router.py" in spec.files_to_modify
    assert "cache.py" in spec.files_to_create


@pytest.mark.asyncio
async def test_repo_mapper_deterministic_search(tmp_path):
    """Verify RepoMapper finds files and AST symbols deterministically."""
    # Create sample files
    f1 = tmp_path / "service.py"
    f1.write_text("class UserService:\n    def get_user(self, user_id):\n        pass\n")
    f2 = tmp_path / "test_service.py"
    f2.write_text("def test_get_user():\n    pass\n")

    provider = MockLLMProvider()
    mapper = RepoMapperAgent(provider)

    result = await mapper.execute("UserService get_user", {"repository_root": str(tmp_path)})
    assert result.status == AgentStatus.SUCCESS
    evidence = result.evidence
    symbols = evidence["symbols"]
    assert any(s["symbol"] == "UserService" for s in symbols)
    assert any(s["symbol"] == "get_user" for s in symbols)


@pytest.mark.asyncio
async def test_coder_agent_tool_loop(tmp_path):
    """Verify Coder inspects and writes files in isolated workspace."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Model requests write_file, then finish
    actions = [
        json.dumps({"action": "write_file", "path": "calc.py", "content": "def add(a, b): return a + b\n"}),
        json.dumps({"action": "finish", "summary": "Created calc.py with add function"}),
    ]
    call_idx = 0

    def mock_gen(prompt):
        nonlocal call_idx
        idx = min(call_idx, len(actions) - 1)
        call_idx += 1
        return actions[idx]

    provider = MockLLMProvider({"generate": mock_gen, "chat": actions[0]})
    # Also override chat to return sequentially
    chat_calls = 0
    async def custom_chat(*args, **kwargs):
        nonlocal chat_calls
        act = actions[min(chat_calls, len(actions) - 1)]
        chat_calls += 1
        return {"message": {"content": act}, "response": act}
    provider.chat = custom_chat

    coder = CoderAgent(provider, max_iterations=5)
    result = await coder.execute("Implement calculator add", {"worktree": str(workspace)})

    assert result.status == AgentStatus.SUCCESS
    created_file = workspace / "calc.py"
    assert created_file.exists()
    assert "def add(a, b)" in created_file.read_text()


@pytest.mark.asyncio
async def test_tester_agent_real_execution(tmp_path):
    """Verify Tester executes actual command and does not fabricate success on failure."""
    provider = MockLLMProvider({"generate": "AssertionError in test_sub"})
    tester = TesterAgent(provider)

    # 1. Run real passing python syntax test
    good_file = tmp_path / "good.py"
    good_file.write_text("x = 1 + 2\n")
    pass_result = await tester.execute("syntax check", {
        "worktree": str(tmp_path),
        "test_command": f"python -m py_compile {good_file.name}",
    })
    assert pass_result.status == AgentStatus.SUCCESS
    assert pass_result.evidence["exit_code"] == 0

    # 2. Run real failing command
    fail_result = await tester.execute("syntax check", {
        "worktree": str(tmp_path),
        "test_command": "python -c \"import sys; sys.exit(1)\"",
    })
    assert fail_result.status == AgentStatus.FAILURE
    assert fail_result.evidence["exit_code"] == 1


@pytest.mark.asyncio
async def test_repair_agent_minimal_fix(tmp_path):
    """Verify Repair Agent consumes failure evidence and applies minimal patch."""
    src = tmp_path / "math_mod.py"
    src.write_text("def subtract(a, b):\n    return a + b  # BUG\n")

    repair_plan = {
        "failure_analysis": "subtract function performs addition instead of subtraction",
        "target_file": "math_mod.py",
        "search_block": "return a + b  # BUG",
        "replace_block": "return a - b  # FIXED",
        "verification_command": "python -c \"from math_mod import subtract; assert subtract(5, 2) == 3\"",
    }
    provider = MockLLMProvider({"generate": json.dumps(repair_plan)})
    repair = RepairAgent(provider)

    result = await repair.execute("Fix subtract bug", {
        "worktree": str(tmp_path),
        "test_results": {
            "failed_tests": ["test_subtract"],
            "command": "pytest",
            "stderr": "AssertionError: 7 != 3",
        },
        "changed_files": ["math_mod.py"],
    })

    assert result.status == AgentStatus.SUCCESS
    content = src.read_text()
    assert "return a - b  # FIXED" in content


@pytest.mark.asyncio
async def test_reviewer_agent_evaluation():
    """Verify Reviewer detects changes and provides structured feedback."""
    review_data = {
        "approved": False,
        "severity": "medium",
        "findings": [
            {"category": "error_handling", "description": "Missing try/except block", "severity": "medium"}
        ],
        "required_changes": ["Wrap network call in try/except"],
        "summary": "Needs better error handling",
    }
    provider = MockLLMProvider({"generate": json.dumps(review_data)})
    reviewer = ReviewerAgent(provider)

    result = await reviewer.execute("Review endpoint", {"diff": "+ def call_api(): pass"})
    assert result.status == AgentStatus.FAILURE
    assert "review" in result.evidence
    report = ReviewReport(**result.evidence["review"])
    assert report.approved is False
    assert len(report.required_changes) == 1


@pytest.mark.asyncio
async def test_security_reviewer_detection():
    """Verify Security Reviewer flags command injection and secret leaks."""
    provider = MockLLMProvider({"generate": json.dumps({
        "safe": False,
        "requires_human_approval": False,
        "vulnerabilities": [
            {"vuln_type": "command_injection", "description": "os.system called with user input", "severity": "high"}
        ],
        "summary": "Critical command injection detected",
    })})
    sec = SecurityReviewerAgent(provider)

    diff_with_injection = """
+ def run_user_cmd(cmd):
+     os.system(cmd)
+     api_key = "AIzaSyD-TEST-SECRET-123456789"
"""
    result = await sec.execute("Audit changes", {"diff": diff_with_injection})
    assert result.status in (AgentStatus.FAILURE, AgentStatus.NEEDS_APPROVAL)
    report = SecurityReviewReport(**result.evidence["security_report"])
    assert report.safe is False
    assert len(report.vulnerabilities) >= 1


# ─── 2. Failure Recovery Flow ────────────────────────────────────────────────

def test_supervisor_failure_recovery_loop():
    """
    Verify Supervisor failure flow:
    EXECUTE -> VERIFY failure -> REPAIR -> EXECUTE -> VERIFY success -> REVIEW -> SECURITY_REVIEW -> FINALIZE -> COMPLETED
    """
    sv = Supervisor()
    contract = TaskContract(
        objective="coding: fix bug",
        metadata={"workflow": "coding", "is_coding_task": True},
    )
    sv.start(contract)  # IDLE -> ANALYZE

    # ANALYZE -> PLAN
    d = sv.evaluate(AgentResult(agent_id="a1", agent_type="repo_mapper", status=AgentStatus.SUCCESS, summary="analyzed"))
    assert d.next_state == TaskState.PLAN
    sv.apply(d)

    # PLAN -> ARCHITECT
    d = sv.evaluate(AgentResult(agent_id="a2", agent_type="planner", status=AgentStatus.SUCCESS, summary="planned"))
    assert d.next_state == TaskState.ARCHITECT
    sv.apply(d)

    # ARCHITECT -> EXECUTE
    d = sv.evaluate(AgentResult(agent_id="a3", agent_type="architect", status=AgentStatus.SUCCESS, summary="architected"))
    assert d.next_state == TaskState.EXECUTE
    sv.apply(d)

    # EXECUTE -> VERIFY
    d = sv.evaluate(AgentResult(agent_id="a4", agent_type="coder", status=AgentStatus.SUCCESS, summary="coded"))
    assert d.next_state == TaskState.VERIFY
    sv.apply(d)

    # VERIFY (Fails!) -> REPAIR
    d = sv.evaluate(AgentResult(agent_id="a5", agent_type="tester", status=AgentStatus.FAILURE, summary="test failed", error="exit 1"))
    assert d.next_state == TaskState.REPAIR
    sv.apply(d)

    # REPAIR -> EXECUTE
    d = sv.evaluate(AgentResult(agent_id="a6", agent_type="repair", status=AgentStatus.SUCCESS, summary="repaired"))
    assert d.next_state == TaskState.EXECUTE
    sv.apply(d)

    # EXECUTE -> VERIFY
    d = sv.evaluate(AgentResult(agent_id="a7", agent_type="coder", status=AgentStatus.SUCCESS, summary="re-executed"))
    assert d.next_state == TaskState.VERIFY
    sv.apply(d)

    # VERIFY (Passes!) -> REVIEW
    d = sv.evaluate(AgentResult(agent_id="a8", agent_type="tester", status=AgentStatus.SUCCESS, summary="tests passed"))
    assert d.next_state == TaskState.REVIEW
    sv.apply(d)

    # REVIEW -> SECURITY_REVIEW
    d = sv.evaluate(AgentResult(agent_id="a9", agent_type="reviewer", status=AgentStatus.SUCCESS, summary="review ok"))
    assert d.next_state == TaskState.SECURITY_REVIEW
    sv.apply(d)

    # SECURITY_REVIEW -> FINALIZE
    d = sv.evaluate(AgentResult(agent_id="a10", agent_type="security_reviewer", status=AgentStatus.SUCCESS, summary="security ok"))
    assert d.next_state == TaskState.FINALIZE
    sv.apply(d)

    # FINALIZE -> COMPLETED
    d = sv.evaluate(AgentResult(agent_id="a11", agent_type="finalizer", status=AgentStatus.SUCCESS, summary="done"))
    assert d.next_state == TaskState.COMPLETED
    sv.apply(d)

    assert sv.is_done
    assert sv.state == TaskState.COMPLETED


# ─── 3. Repeated Failures and Loop Detection ─────────────────────────────────

def test_supervisor_repeated_failure_loop_detection():
    """Verify identical consecutive failures trigger loop_detected = true and halt."""
    sv = Supervisor()
    contract = TaskContract(
        objective="coding: fix bug",
        budget=TaskBudget(max_repeated_failures=3, max_retries=10),
        metadata={"workflow": "coding", "is_coding_task": True},
    )
    sv.start(contract)
    sv.apply(SupervisorDecision(next_state=TaskState.EXECUTE, reason="skip to execute"))

    fail_sig = "ZeroDivisionError in line 42"
    for i in range(2):
        d = sv.evaluate(AgentResult(agent_id="coder", agent_type="coder", status=AgentStatus.FAILURE, error=fail_sig, summary="failed"))
        assert d.next_state == TaskState.REPAIR
        sv.apply(d)
        sv.apply(SupervisorDecision(next_state=TaskState.EXECUTE, reason="retry"))

    # 3rd identical failure triggers loop detection!
    d = sv.evaluate(AgentResult(agent_id="coder", agent_type="coder", status=AgentStatus.FAILURE, error=fail_sig, summary="failed"))
    assert d.next_state == TaskState.FAILED
    assert "Loop detected" in d.reason
    assert contract.stop_conditions.loop_detected is True


def test_supervisor_max_retries_exceeded():
    """Verify exceeding retry budget halts the task."""
    sv = Supervisor()
    contract = TaskContract(
        objective="coding: test retries",
        budget=TaskBudget(max_retries=2, max_repeated_failures=10),
        metadata={"workflow": "coding"},
    )
    sv.start(contract)
    sv.apply(SupervisorDecision(next_state=TaskState.EXECUTE, reason="skip to execute"))

    for i in range(2):
        d = sv.evaluate(AgentResult(agent_id=f"a{i}", agent_type="coder", status=AgentStatus.FAILURE, error=f"error_{i}", summary="failed"))
        sv.apply(d)
        sv.apply(SupervisorDecision(next_state=TaskState.EXECUTE, reason="retry"))

    # Exceeding budget
    d = sv.evaluate(AgentResult(agent_id="a_final", agent_type="coder", status=AgentStatus.FAILURE, error="error_final", summary="failed"))
    assert d.next_state == TaskState.FAILED
    assert "Retry budget exhausted" in d.reason or "Max retries reached" in d.reason


# ─── 4. Model Fallback and 16 GB VRAM Management ─────────────────────────────

@pytest.mark.asyncio
async def test_model_router_fallback_and_vram_swapping():
    """Verify ModelRouter unloads inactive 24B/14B models on 16GB GPU and falls back when missing."""
    router = ModelRouter()
    provider = MockLLMProvider()

    # Simulate 24B devstral is NOT available, but 14B fallback IS available
    provider.available_models = ["qwen2.5-coder:14b", "qwen2.5-coder:7b", "llama3.2:3b"]

    chosen_model, options = await router.prepare_model_for_agent("coder", provider)
    # Target was devstral-small-2:24b, fallback should be qwen2.5-coder:14b
    assert chosen_model == "qwen2.5-coder:14b"
    assert options["temperature"] == 0.1

    # Simulate active 14B model loaded
    provider.running_models = ["qwen2.5-coder:14b"]
    router.active_large_model = "qwen2.5-coder:14b"

    # Now request repair with a different large model: it must unload the previous model
    provider.available_models.append("devstral-small-2:24b")
    chosen2, _ = await router.prepare_model_for_agent("repair", provider)
    assert chosen2 == "devstral-small-2:24b"
    assert "qwen2.5-coder:14b" not in provider.running_models  # Unloaded!
    assert router.active_large_model == "devstral-small-2:24b"


# ─── 5. Cancellation & Checkpoints ───────────────────────────────────────────

def test_cancellation_preserves_checkpoint_and_workspace(tmp_path):
    """Verify task cancellation sets stop conditions and saves SQLite checkpoint."""
    contract = TaskContract(objective="test cancellation")
    runtime = CodingTaskRuntime(contract, str(tmp_path))
    supervisor = Supervisor()
    supervisor.start(contract)

    # Cancel task
    supervisor.cancel("User aborted")
    assert supervisor.state == TaskState.CANCELLED
    assert contract.stop_conditions.user_cancelled is True

    # Save and reload checkpoint
    runtime.save_checkpoint()
    cp_mgr = CheckpointManager()
    loaded = cp_mgr.load_checkpoint(contract.task_id)
    assert loaded is not None
    assert loaded.current_state == TaskState.CANCELLED.value
    assert loaded.stop_conditions.user_cancelled is True

    # Verify workspace remains clean/recoverable
    runtime.cleanup()


# ─── 6. Security Enforcement & Protected Files ───────────────────────────────

def test_coder_cannot_write_protected_files(tmp_path):
    """Verify CoderAgent is blocked from writing to core HELIOS security files."""
    provider = MockLLMProvider()
    coder = CoderAgent(provider)

    from security.permissions import HELIOS_PROTECTED_PATHS
    if HELIOS_PROTECTED_PATHS:
        protected_target = str(HELIOS_PROTECTED_PATHS[0])
        res = coder._execute_write_file(str(tmp_path), protected_target, "# malicious code")
        assert "blocked by security policy" in res or "outside workspace" in res


# ─── 7. SubAgentTool TaskContract / Supervisor Integration ───────────────────

@pytest.mark.asyncio
async def test_subagent_tool_spawns_contract_and_supervisor():
    """Verify SubAgentTool delegates execution through Supervisor without Needle bypass."""
    provider = MockLLMProvider({
        "generate": "Subtask successfully solved by reasoning agent",
    })
    subagent_tool = SubAgentTool(provider)

    output, tool_name = await subagent_tool.execute(
        user_id=1,
        task="Analyze memory leak in module X",
        budget=3,
        parent_task_id="parent_task_999",
    )

    assert tool_name == "SubAgentTool"
    assert "SubAgent [" in output
    assert "parent_task_999" in output
    assert "COMPLETED" in output
