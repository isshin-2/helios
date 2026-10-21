import pytest
import os
import sys

# Ensure ai-router root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from providers.airllm_provider import AirLLMProvider

def test_airllm_provider_initialization():
    provider = AirLLMProvider(device="cpu")
    assert provider is not None
    assert provider.device == "cpu"
    assert isinstance(provider.active_models, dict)

@pytest.mark.asyncio
async def test_airllm_provider_list_models():
    provider = AirLLMProvider(device="cpu")
    models = await provider.list_models()
    assert "models" in models
    assert isinstance(models["models"], list)

@pytest.mark.asyncio
async def test_airllm_provider_embeddings():
    provider = AirLLMProvider(device="cpu")
    emb = await provider.get_embeddings("test-model", "Hello world")
    assert isinstance(emb, list)
    assert len(emb) == 384

@pytest.mark.asyncio
async def test_airllm_provider_unload():
    provider = AirLLMProvider(device="cpu")
    res = await provider.unload_model("non_existent_model")
    assert res.get("status") == "not_loaded"
