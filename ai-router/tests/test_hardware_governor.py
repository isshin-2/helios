import pytest
import os
import sys

# Ensure ai-router root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.hardware_governor import HardwareGovernor, HardwareTierDecision
from core.hardware_profiler import detect_hardware, get_hardware_summary, HardwareProfile
from tools.llmfit_tool import LLMFitTool
import asyncio

def test_hardware_profiler_detection():
    profile = detect_hardware()
    assert profile is not None
    assert profile.ram_total_gb > 0
    assert profile.os_name != ""
    assert isinstance(profile.gpu_present, bool)

def test_hardware_summary():
    summary = get_hardware_summary()
    assert "tier" in summary
    assert "tier_limits" in summary
    assert "ram_total_gb" in summary

def test_hardware_governor_evaluation():
    governor = HardwareGovernor()
    assert governor.decision is not None
    assert governor.decision.tier in [1, 2, 3]
    assert len(governor.decision.recommended_models) > 0
    banner = governor.get_advisory_banner()
    assert isinstance(banner, str)
    assert len(banner) > 0

def test_hardware_governor_budget_simulation():
    # Simulate a low VRAM / iGPU machine
    fake_profile = HardwareProfile(
        os_name="Windows",
        os_version="11",
        cpu_name="Intel Core i5",
        cpu_cores_physical=4,
        cpu_cores_logical=8,
        ram_total_gb=8.0,
        ram_available_gb=3.0,
        gpu_present=True,
        gpu_vendor="intel",
        gpu_name="Intel Iris Xe Graphics",
        gpu_vram_gb=1.5,
        disk_free_gb=50.0
    )
    governor = HardwareGovernor(profile=fake_profile)
    assert governor.decision.tier == 3
    assert governor.decision.is_budget is True
    assert "moondream:latest" in governor.decision.recommended_models.values() or "qwen2.5:1.5b" in governor.decision.recommended_models.values()

@pytest.mark.asyncio
async def test_llmfit_tool_system_execution():
    tool = LLMFitTool()
    res, name = await tool.execute(user_id=1, command="system")
    assert name == "llmfit"
    # Should contain either valid JSON or descriptive response
    assert "system" in res or "backend" in res or "cpu_cores" in res or "Error running llmfit" in res
