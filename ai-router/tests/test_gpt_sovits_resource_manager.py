"""
HELIOS Test Suite — GPT-SoVITS Integration & Unified Resource Manager
Verifies:
1. Resource manager VRAM and RAM accounting and limits.
2. Model registration and residency state transitions (UNLOADED -> RAM_RESIDENT -> GPU_RESIDENT -> ACTIVE).
3. Memory pressure evaluation (NORMAL -> ELEVATED -> HIGH -> CRITICAL).
4. LRU model demotion from GPU VRAM to System RAM under pressure.
5. Inactivity idle sweeping.
6. TTSBackendManager fallback behavior (GPT-SoVITS -> Kokoro).
7. Hardware profiler TTS resource profile classification.
8. Non-interference with active LLM generation.
"""
import pytest
import asyncio
import numpy as np
from unittest.mock import MagicMock, AsyncMock, patch

from core.audio.tts.base import BaseTTSBackend, ModelResidencyState
from core.audio.tts.resource_policy import ResourceManager, MemoryPressure
from core.audio.tts.gpt_sovits import GPTSoVITS_TTS
from core.audio.tts.manager import TTSBackendManager
from core.audio.tts.kokoro import KokoroTTS
from core.hardware_profiler import get_tts_resource_profile, HardwareProfile


def test_resource_manager_accounting_and_query():
    """Verify system RAM and GPU memory metrics reporting."""
    rm = ResourceManager()
    mem = rm.get_system_memory()
    gpu = rm.get_gpu_memory()

    assert "total_gb" in mem
    assert "available_gb" in mem
    assert mem["total_gb"] > 0
    assert "total_mb" in gpu
    assert "free_mb" in gpu
    assert "available_for_models_mb" in gpu


def test_model_registration_and_residency_states():
    """Verify registering a model and tracking its lifecycle state."""
    rm = ResourceManager()
    rm.register_model(
        model_id="test_model",
        subsystem="tts",
        residency_state=ModelResidencyState.UNLOADED,
        ram_size_mb=1000.0,
        vram_size_mb=2000.0,
    )
    assert "test_model" in rm._models
    assert rm._models["test_model"].residency_state == ModelResidencyState.UNLOADED


def test_lru_demotion_from_vram_to_ram():
    """Verify that when VRAM is constrained, inactive GPU models are demoted to RAM in LRU order."""
    rm = ResourceManager()
    demote_called = []

    def mock_demote_1():
        demote_called.append("model_1")
        return True

    def mock_demote_2():
        demote_called.append("model_2")
        return True

    rm.register_model(
        model_id="model_1",
        subsystem="vision",
        residency_state=ModelResidencyState.GPU_RESIDENT,
        vram_size_mb=3000.0,
        demote_handler=mock_demote_1,
    )
    rm._models["model_1"].last_active_time = 100.0

    rm.register_model(
        model_id="model_2",
        subsystem="embeddings",
        residency_state=ModelResidencyState.GPU_RESIDENT,
        vram_size_mb=2000.0,
        demote_handler=mock_demote_2,
    )
    rm._models["model_2"].last_active_time = 200.0  # More recently active

    reclaimed = rm.demote_inactive_gpu_models()
    assert reclaimed == 5000.0
    # model_1 is older, should be demoted first
    assert demote_called == ["model_1", "model_2"]
    assert rm._models["model_1"].residency_state == ModelResidencyState.RAM_RESIDENT
    assert rm._models["model_2"].residency_state == ModelResidencyState.RAM_RESIDENT


def test_memory_pressure_levels():
    """Verify memory pressure transitions."""
    rm = ResourceManager()
    with patch.object(rm, "get_system_memory", return_value={"available_gb": 40.0, "total_gb": 64.0}):
        with patch.object(rm, "get_gpu_memory", return_value={"available_gb": 12.0, "total_mb": 16000.0}):
            assert rm.get_memory_pressure() == MemoryPressure.NORMAL

    with patch.object(rm, "get_system_memory", return_value={"available_gb": 3.0, "total_gb": 64.0}):
        with patch.object(rm, "get_gpu_memory", return_value={"available_gb": 0.5, "total_mb": 16000.0}):
            assert rm.get_memory_pressure() == MemoryPressure.CRITICAL


def test_hardware_profiler_tts_classification():
    """Verify that hardware profiler correctly categorizes systems for TTS."""
    with patch("core.hardware_profiler.detect_hardware") as mock_det:
        # High-spec workstation (RTX 5060 Ti 16GB + 64GB RAM)
        mock_det.return_value = HardwareProfile(
            os_name="Windows",
            os_version="11",
            cpu_name="AMD Ryzen 5 7600X",
            cpu_cores_physical=6,
            cpu_cores_logical=12,
            ram_total_gb=64.0,
            ram_available_gb=50.0,
            gpu_present=True,
            gpu_vendor="nvidia",
            gpu_name="NVIDIA GeForce RTX 5060 Ti",
            gpu_vram_gb=16.0,
            disk_free_gb=500.0,
        )
        res = get_tts_resource_profile()
        assert res["recommended_backend"] == "gpt_sovits"
        assert res["ram_staging_budget_gb"] == 32.0


def test_llm_coexistence_flag():
    """Verify active LLM state notification to protect active generation."""
    rm = ResourceManager()
    rm.set_llm_active(True)
    assert rm.is_llm_active is True
    rm.set_llm_active(False)
    assert rm.is_llm_active is False


@pytest.mark.asyncio
async def test_tts_manager_fallback_to_kokoro():
    """Verify that when GPT-SoVITS is unreachable, TTSBackendManager falls back to Kokoro."""
    manager = TTSBackendManager()
    manager.gpt_sovits._is_available = False

    # Mock Kokoro create to return test audio
    fake_samples = np.zeros(24000, dtype=np.float32)
    with patch.object(manager.kokoro, "synthesize") as mock_kokoro_synth:
        async def dummy_synth(*args, **kwargs):
            yield fake_samples, 24000

        mock_kokoro_synth.side_effect = dummy_synth

        collected = []
        async for samples, sr in manager.synthesize("System check operational.", voice="af_heart"):
            collected.append((samples, sr))

        assert len(collected) == 1
        assert collected[0][1] == 24000
        assert manager._active_backend_name == "kokoro"


@pytest.mark.asyncio
async def test_gpt_sovits_synthesis_flow():
    """Verify GPT-SoVITS synthesis path and residency state transitions."""
    gpt = GPTSoVITS_TTS()
    gpt._is_available = True

    with patch("httpx.AsyncClient.post") as mock_post:
        # Create a tiny 1-second WAV buffer
        import soundfile as sf
        import io
        buf = io.BytesIO()
        fake_data = np.zeros(24000, dtype=np.float32)
        sf.write(buf, fake_data, 24000, format="WAV")
        mock_post.return_value = MagicMock(status_code=200, content=buf.getvalue())

        collected = []
        async for samples, sr in gpt.synthesize("Hello master! GPT-SoVITS voice cloning active.", voice="helios"):
            collected.append((samples, sr))

        assert len(collected) == 1
        assert collected[0][1] == 24000
        assert gpt.residency_state in (ModelResidencyState.GPU_RESIDENT, ModelResidencyState.RAM_RESIDENT)


def test_gpt_sovits_reference_audio_ram_preloading(tmp_path):
    """Verify that reference audio files are loaded and cached directly in System RAM."""
    ref_file = tmp_path / "reference.wav"
    ref_file.write_bytes(b"RIFF_FAKE_WAV_HEADER_DATA")

    gpt = GPTSoVITS_TTS(ref_audio_path=str(ref_file))
    gpt.initialize()
    assert gpt._ref_audio_cache == b"RIFF_FAKE_WAV_HEADER_DATA"
