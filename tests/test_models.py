import pytest
from unittest.mock import AsyncMock, MagicMock
from models.manager import ModelManager
from health.monitor import SystemMonitor
from providers.base import BaseProvider

class DummyProvider(BaseProvider):
    async def chat(self, *args, **kwargs):
        pass
    async def generate(self, *args, **kwargs):
        pass
    async def get_embeddings(self, *args, **kwargs):
        pass
    async def list_models(self):
        return {"models": []}
    async def list_running(self):
        return {"models": []}
    async def unload_model(self, model: str):
        pass

@pytest.fixture
def mock_provider():
    provider = DummyProvider()
    provider.list_models = AsyncMock()
    provider.unload_model = AsyncMock()
    return provider

@pytest.fixture
def mock_monitor():
    monitor = MagicMock(spec=SystemMonitor)
    monitor.get_full_status = AsyncMock()
    return monitor

@pytest.fixture
def manager(mock_provider, mock_monitor):
    return ModelManager(provider=mock_provider, monitor=mock_monitor)

@pytest.mark.asyncio
async def test_ensure_model_loaded_already_loaded(manager, mock_provider, mock_monitor):
    # Setup
    mock_monitor.get_full_status.return_value = {
        "loaded_models": [{"name": "target-model", "size_vram": 1024, "size": 1024}],
        "available_ram_mb": 8000
    }
    
    # Execute
    result = await manager.ensure_model_loaded("target-model", 2048)
    
    # Assert
    assert result is True
    mock_provider.list_models.assert_not_called()
    mock_provider.unload_model.assert_not_called()

@pytest.mark.asyncio
async def test_ensure_model_loaded_enough_memory(manager, mock_provider, mock_monitor):
    # Setup
    mock_monitor.get_full_status.return_value = {
        "loaded_models": [{"name": "other-model", "size_vram": 1024, "size": 1024}],
        "available_ram_mb": 8000
    }
    mock_provider.list_models.return_value = {
        "models": [{"name": "target-model", "size": 2048 * 1024 * 1024}] # 2048 MB
    }
    
    # Execute
    result = await manager.ensure_model_loaded("target-model", 2048)
    
    # Assert
    assert result is True
    mock_provider.unload_model.assert_not_called()

@pytest.mark.asyncio
async def test_ensure_model_loaded_insufficient_memory(manager, mock_provider, mock_monitor):
    # Setup
    state = {
        "loaded_models": [{"name": "other-model", "size_vram": 2048 * 1024 * 1024}],
        "available_ram_mb": 4000
    }
    
    async def side_effect_get_status():
        return state.copy()
        
    async def side_effect_unload(model_name):
        state["loaded_models"] = [m for m in state["loaded_models"] if m["name"] != model_name]
        state["available_ram_mb"] += 2048
        
    mock_monitor.get_full_status.side_effect = side_effect_get_status
    mock_provider.unload_model.side_effect = side_effect_unload
    
    mock_provider.list_models.return_value = {
        "models": [{"name": "target-model", "size": 2048 * 1024 * 1024}]
    }
    
    # Execute
    result = await manager.ensure_model_loaded("target-model", 2048)
    
    # Assert
    assert result is True
    mock_provider.unload_model.assert_called_once_with("other-model")

@pytest.mark.asyncio
async def test_ensure_model_loaded_ordering(manager, mock_provider, mock_monitor):
    # Setup
    state = {
        "loaded_models": [
            {"name": "small", "size_vram": 100 * 1024 * 1024},
            {"name": "large", "size_vram": 300 * 1024 * 1024},
            {"name": "medium", "size_vram": 200 * 1024 * 1024}
        ],
        "available_ram_mb": 4700 # Short by 420 MB from the 5120 required.
    }
    
    async def side_effect_get_status():
        return state.copy()
        
    async def side_effect_unload(model_name):
        freed = next((m["size_vram"] for m in state["loaded_models"] if m["name"] == model_name), 0)
        state["loaded_models"] = [m for m in state["loaded_models"] if m["name"] != model_name]
        state["available_ram_mb"] += (freed / (1024*1024))
        
    mock_monitor.get_full_status.side_effect = side_effect_get_status
    mock_provider.unload_model.side_effect = side_effect_unload
    
    mock_provider.list_models.return_value = {
        "models": [{"name": "target-model", "size": 2048 * 1024 * 1024}]
    }
    
    # Execute
    await manager.ensure_model_loaded("target-model", 2048)
    
    # Assert
    assert mock_provider.unload_model.call_count == 2
    calls = mock_provider.unload_model.call_args_list
    assert calls[0][0][0] == "large"
    assert calls[1][0][0] == "medium"

@pytest.mark.asyncio
async def test_ensure_model_loaded_target_protection(manager, mock_provider, mock_monitor):
    # Setup
    state = {
        "loaded_models": [{"name": "target-model", "size_vram": 999999}],
        "available_ram_mb": 1000 # Insufficient, but only candidate is target-model
    }
    
    async def side_effect_get_status():
        return state.copy()
            
    mock_monitor.get_full_status.side_effect = side_effect_get_status
    
    # This shouldn't be reached because of Step 1 early return!
    # Let's bypass Step 1 by making it not loaded initially, then loaded during loop.
    
    call_count = 0
    async def side_effect_get_status_dynamic():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"loaded_models": [], "available_ram_mb": 1000}
        else:
            return {"loaded_models": [{"name": "target-model", "size_vram": 999999}], "available_ram_mb": 1000}
            
    mock_monitor.get_full_status.side_effect = side_effect_get_status_dynamic
    
    mock_provider.list_models.return_value = {
        "models": [{"name": "target-model", "size": 2048 * 1024 * 1024}]
    }
    
    # Execute
    with pytest.raises(MemoryError) as exc_info:
        await manager.ensure_model_loaded("target-model", 2048)
        
    assert "No safe unload candidates remain" in str(exc_info.value)
    mock_provider.unload_model.assert_not_called()

@pytest.mark.asyncio
async def test_ensure_model_loaded_persistent_insufficiency(manager, mock_provider, mock_monitor):
    # Setup
    state = {
        "loaded_models": [{"name": "other-model", "size_vram": 1024}],
        "available_ram_mb": 1000
    }
    
    async def side_effect_get_status():
        return state.copy()
        
    async def side_effect_unload(model_name):
        state["loaded_models"] = []
    
    mock_monitor.get_full_status.side_effect = side_effect_get_status
    mock_provider.unload_model.side_effect = side_effect_unload
    
    mock_provider.list_models.return_value = {
        "models": [{"name": "target-model", "size": 9000 * 1024 * 1024}]
    }
    
    with pytest.raises(MemoryError):
        await manager.ensure_model_loaded("target-model", 2048)
    
@pytest.mark.asyncio
async def test_ensure_model_loaded_edge_cases(manager, mock_provider, mock_monitor):
    # Zero loaded models, insufficient memory
    mock_monitor.get_full_status.return_value = {
        "loaded_models": [],
        "available_ram_mb": 1000
    }
    mock_provider.list_models.return_value = {
        "models": [{"name": "target-model", "size": 9000 * 1024 * 1024}]
    }
    
    with pytest.raises(MemoryError):
        await manager.ensure_model_loaded("target-model", 2048)
        
    # Missing size from Ollama
    mock_monitor.get_full_status.return_value = {
        "loaded_models": [],
        "available_ram_mb": 8000
    }
    mock_provider.list_models.return_value = {
        "models": [{"name": "target-model"}]
    }
    
    result = await manager.ensure_model_loaded("target-model", 2048)
    assert result is True
    
    # Malformed loaded_models from older monitor
    state = {
        "loaded_models": ["other-model-1", "other-model-2"],
        "available_ram_mb": 1000
    }
    
    async def side_effect_get_status():
        return state.copy()
        
    async def side_effect_unload(model_name):
        state["loaded_models"] = [m for m in state["loaded_models"] if m != model_name]
        
    mock_monitor.get_full_status.side_effect = side_effect_get_status
    mock_provider.unload_model.side_effect = side_effect_unload
    
    mock_provider.list_models.return_value = {
        "models": [{"name": "target-model", "size": 2000 * 1024 * 1024}]
    }
    
    with pytest.raises(MemoryError):
        await manager.ensure_model_loaded("target-model", 2048)
    assert mock_provider.unload_model.call_count == 2
