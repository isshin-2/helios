"""
HELIOS Core Autonomous Test Suite
Validates the entire HELIOS system end-to-end:
1. Hardware Limits & 64GB RAM Multi-Model Retention (model_router)
2. AI PC Network Reachability & Auto-Wake (ai_pc_manager)
3. Remote GPU Node Inference (PairProvider -> 192.168.100.254)
4. Codebase Knowledge RAG (SQLite Vector Memory)
5. Zero-Trust Sandbox Security (permissions engine)
6. Swarm State Machine & Lifecycle Transitions
"""
import pytest
import asyncio
import os
import sqlite3
from pathlib import Path

from config import AI_PC_IP, OLLAMA_HOST, PAIR_HOST
from core.ai_pc_manager import is_ai_pc_reachable
from core.model_router import ModelRouter, HardwareLimits
from providers.pair import PairProvider
from security.permissions import (
    PermissionManager,
    validate_path,
    is_blocked_system_path,
    BLOCKED_COMMANDS,
)
from core.state_machine import TaskStateMachine, TaskState



@pytest.mark.asyncio
async def test_hardware_limits_and_64gb_ram_pool():
    """Verify HELIOS hardware profile correctly recognizes 64GB RAM and multi-model retention."""
    router = ModelRouter()
    assert router.hardware.system_ram_gb >= 64.0, "Hardware must reflect 64GB DDR5 host RAM"
    assert router.hardware.max_vram_gb == 16.0, "Hardware must reflect 16GB RTX 5060 Ti VRAM"
    assert router.hardware.max_concurrent_large_models == 3, "Multi-model RAM pool must support 3 concurrent models"
    assert router.hardware.default_context_tokens == 16384, "Context window must be at least 16,384 tokens"

    # Verify options injection
    provider = PairProvider(host=PAIR_HOST)
    model, options = await router.prepare_model_for_agent("planner", provider)
    assert options.get("num_ctx") == 16384, "Swarm options must inject 16k context window"
    assert model in ["qwen2.5-coder:14b", "qwen2.5-coder:7b", "hermes3:8b"]


def test_ai_pc_reachability():
    """Verify AI PC connection across management and GPU inference ports."""
    reachable = is_ai_pc_reachable(timeout=3.0)
    assert reachable is True, f"AI PC at {AI_PC_IP} must be reachable over LAN"


@pytest.mark.asyncio
async def test_remote_ai_pc_inference():
    """Verify live inference directly through the AI PC node."""
    provider = PairProvider(host=PAIR_HOST)
    res = await provider.generate(
        model="qwen2.5-coder:7b",
        prompt="Respond with only the text: HELIOS_CORE_ONLINE",
        options={"temperature": 0.0}
    )
    assert "response" in res, "AI PC must return a valid JSON response"
    assert "HELIOS" in res["response"].upper(), f"Unexpected inference response: {res['response']}"


def test_codebase_knowledge_in_vector_memory():
    """Verify SQLite memory correctly stored the Desktop codebases knowledge."""
    db_path = Path(__file__).resolve().parent.parent / "helios.db"
    assert db_path.exists(), "helios.db must exist with initialized knowledge"

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Verify core_memory table has project architecture summaries
    cursor.execute("SELECT section, content FROM core_memory")
    core_mem = dict(cursor.fetchall())
    assert "AGRITECH_ROVER_SPEC" in core_mem, "Agritech Rover architecture must be present in core memory"
    assert "AQUAPULSE_SPEC" in core_mem, "AquaPulse architecture must be present in core memory"
    assert "TEMPSENSE_SPEC" in core_mem, "TEMPSENSE architecture must be present in core memory"
    assert "TEMPSENSE_OTA_SPEC" in core_mem, "TEMPSENSE-OTA architecture must be present in core memory"

    # Check key architectural facts
    assert "RC-only" in core_mem["AGRITECH_ROVER_SPEC"] or "BTS7960" in core_mem["AGRITECH_ROVER_SPEC"]
    assert "DYP-A02YYTW" in core_mem["AQUAPULSE_SPEC"] or "ST7789" in core_mem["AQUAPULSE_SPEC"]
    assert "1024" in core_mem["TEMPSENSE_SPEC"] or "PostgreSQL" in core_mem["TEMPSENSE_SPEC"]

    conn.close()



def test_zero_trust_security_sandbox():
    """Verify safety sandbox blocks destructive commands and system paths."""
    # 1. Dangerous command blocking
    assert "rmdir" in BLOCKED_COMMANDS, "rmdir must be in BLOCKED_COMMANDS"
    assert "del" in BLOCKED_COMMANDS, "del must be in BLOCKED_COMMANDS"
    assert "powershell" in BLOCKED_COMMANDS, "raw powershell invocation must be in BLOCKED_COMMANDS"

    # 2. Blocked system paths
    assert is_blocked_system_path("C:\\Windows\\System32") is True, "C:\\Windows must be blocked"
    assert is_blocked_system_path("C:\\Program Files") is True, "C:\\Program Files must be blocked"

    # 3. Path validation logic
    project_root = str(Path(__file__).resolve().parent.parent)
    valid_res = validate_path(project_root, [project_root])
    assert valid_res.allowed is True, "Project directory must be allowed"

    invalid_res = validate_path("C:\\Windows\\System32\\drivers", [project_root])
    assert invalid_res.allowed is False, "Paths outside allowed paths must be rejected"


from core.state_machine import TaskStateMachine, TaskState


def test_swarm_state_machine():
    """Verify autonomous swarm transitions execute sequentially."""
    sm = TaskStateMachine()
    assert sm.state == TaskState.IDLE

    sm.transition(TaskState.ANALYZE, "Task started")
    sm.transition(TaskState.PLAN, "Analysis finished")
    sm.transition(TaskState.ARCHITECT, "Plan created")
    sm.transition(TaskState.EXECUTE, "Specs approved")
    sm.transition(TaskState.VERIFY, "Execution finished")
    sm.transition(TaskState.REVIEW, "Tests verified")
    sm.transition(TaskState.SECURITY_REVIEW, "Code review passed")
    sm.transition(TaskState.FINALIZE, "Security verified")
    sm.transition(TaskState.COMPLETED, "Task complete")
    assert sm.is_terminal is True


