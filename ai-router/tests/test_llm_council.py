"""
Tests for core/llm_council.py.
Validates 3-stage deliberation workflow with deterministic mocked providers.
"""

from typing import Any, Dict, List, Optional
import pytest
from core.llm_council import LLMCouncilEngine
from core.quality_contracts import CouncilStatus
from providers.base import BaseProvider


class MockProvider(BaseProvider):
    def __init__(self, name="mock_provider", models=None):
        self._name = name
        self._models = models or ["mock-model-1", "mock-model-2"]

    @property
    def name(self) -> str:
        return self._name

    async def list_models(self) -> List[str]:
        return self._models

    async def list_running(self) -> Dict[str, Any]:
        return {"models": []}

    async def unload_model(self, model: str) -> Dict[str, Any]:
        return {"status": "success"}

    async def chat(self, model: str, messages: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None, stream: bool = False, **kwargs):
        return {"message": {"role": "assistant", "content": "mock chat"}}

    async def get_embeddings(self, model: str, prompt: str) -> List[float]:
        return [0.0] * 128

    async def generate(self, model: str, prompt: str, options: Optional[Dict[str, Any]] = None, stream: bool = False, **kwargs):
        if "Chairman of the Technical Council" in prompt:
            return {
                "response": '{"status": "consensus", "decision": "Adopt architecture X with Redis queue.", "alternatives": ["Use Kafka"], "disagreements": [], "confidence": 0.95, "limitations": ["Requires Redis server"]}'
            }
        elif "You are reviewing technical proposals anonymously" in prompt:
            return {
                "response": '{"ranked_order": ["Proposal_1", "Proposal_2"], "rationales": {"Proposal_1": "Clean architecture"}, "trade_offs": {}}'
            }
        else:
            return {
                "response": f"Opinion from {model}: Use modular microservices with structured contracts."
            }


@pytest.mark.asyncio
async def test_council_deliberation_happy_path():
    provider = MockProvider()
    engine = LLMCouncilEngine(primary_provider=provider)

    res = await engine.run_deliberation("task-001", "Design a high-throughput event processor.")

    assert res.status == CouncilStatus.CONSENSUS
    assert "Adopt architecture X" in res.decision
    assert res.candidate_count == 2
    assert len(res.candidates) == 2
    assert len(res.rankings) == 2
    assert res.confidence == 0.95


@pytest.mark.asyncio
async def test_council_single_model_disclosure():
    single_model_provider = MockProvider(models=["single-qwen-coder"])
    engine = LLMCouncilEngine(primary_provider=single_model_provider)

    res = await engine.run_deliberation("task-002", "How to secure websocket endpoints?")

    assert res.same_model_disclosure is not None
    assert "shared model weights" in res.same_model_disclosure
    assert res.candidate_count == 3
