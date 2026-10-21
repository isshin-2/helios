"""
Integration tests for Coding Swarm with LLM Council and Acceptance Gates.
Ensures supervisor remains deterministic authority and all gates are evidence-verified.
"""

import os
import tempfile
import pytest
from core.coding_runtime import CodingContext
from core.coding_swarm import CodingSwarmOrchestrator
from core.quality_contracts import AcceptanceGate, VerificationResult
from core.task_contract import RiskLevel, TaskBudget, TaskContract
from providers.base import BaseProvider


class SwarmMockProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "mock_swarm"

    async def list_models(self):
        return ["qwen-coder-32b", "devstral-24b"]

    async def list_running(self):
        return {}

    async def unload_model(self, model: str):
        return {}

    async def chat(self, model: str, messages, **kwargs):
        return {}

    async def get_embeddings(self, model: str, prompt: str):
        return []

    async def generate(self, model: str, prompt: str, **kwargs):
        # Handle Chairman synthesis
        if "Chairman of the Technical Council" in prompt:
            return {
                "response": '{"status": "consensus", "decision": "Proceed with clean decoupled service.", "confidence": 0.95}'
            }
        # Handle anonymous review
        elif "You are reviewing technical proposals anonymously" in prompt:
            return {
                "response": '{"ranked_order": ["Proposal_1"], "rationales": {"Proposal_1": "Solid"}}'
            }
        # Handle security auditor
        elif "Hunter Agent" in prompt:
            return {"response": "[]"}
        elif "Adversarial Security Verifier" in prompt:
            return {"response": '{"verdict": "confirmed", "confidence": 0.9}'}
        # Generic response
        return {
            "response": '{"safe": true, "requires_human_approval": false, "vulnerabilities": [], "summary": "Clean", "steps": []}'
        }


def test_swarm_initialization_with_council():
    provider = SwarmMockProvider()
    orchestrator = CodingSwarmOrchestrator(provider)
    assert orchestrator.council is not None
    assert orchestrator.security_reviewer is not None


def test_acceptance_gate_blocks_incomplete_finalization():
    ctx = CodingContext(
        task_id="task-xyz",
        objective="Implement feature",
        repository_root=".",
    )
    gate = AcceptanceGate(
        task_id="task-xyz",
        required_tests=["pytest"],
        results=[
            VerificationResult(check_name="pytest", exit_code=1, passed=False)
        ]
    )
    ctx.acceptance_gate = gate
    assert not ctx.acceptance_gate.is_satisfied()
