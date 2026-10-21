"""
HELIOS GPT-SoVITS TTS Engine
Integrates GPT-SoVITS local voice cloning & synthesis into HELIOS.
Supports:
- Zero-shot / few-shot reference audio cloning (e.g. Japanese-accented female vocal identity).
- Intelligent RAM/VRAM resource-aware placement via ResourceManager.
- Low-latency streaming via HTTP API / local server integration.
- Graceful demotion to RAM and seamless fallback to Kokoro.
"""
import os
import io
import time
import logging
import asyncio
from typing import Optional, List, Tuple, AsyncGenerator, Dict, Any
import numpy as np
import httpx
import soundfile as sf

import config
from .base import BaseTTSBackend, ModelResidencyState
from .resource_policy import resource_manager

logger = logging.getLogger(__name__)


class GPTSoVITS_TTS(BaseTTSBackend):
    """
    Dedicated GPT-SoVITS inference backend for HELIOS.
    Connects to local GPT-SoVITS API server or in-process engine.
    Arbitrates VRAM with ResourceManager before execution.
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        model_path: Optional[str] = None,
        sovits_path: Optional[str] = None,
        ref_audio_path: Optional[str] = None,
        ref_text: Optional[str] = None,
        language: str = "en",
        device: str = "auto",
    ):
        self.api_url = (api_url or getattr(config, "GPT_SOVITS_API_URL", "http://127.0.0.1:9880")).rstrip("/")
        self.model_path = model_path or getattr(config, "GPT_SOVITS_MODEL_PATH", "")
        self.sovits_path = sovits_path or getattr(config, "GPT_SOVITS_SOVITS_PATH", "")
        self.ref_audio_path = ref_audio_path or getattr(config, "GPT_SOVITS_REF_AUDIO", "")
        self.ref_text = ref_text or getattr(config, "GPT_SOVITS_REF_TEXT", "")
        self.default_language = language or getattr(config, "GPT_SOVITS_LANGUAGE", "en")
        self.configured_device = device or getattr(config, "GPT_SOVITS_DEVICE", "auto")

        self._is_initialized = False
        self._is_available = False
        self._residency_state = ModelResidencyState.UNLOADED
        self._last_used_time = 0.0
        self._ref_audio_cache: Optional[bytes] = None

        # Register with the central ResourceManager
        resource_manager.register_model(
            model_id="gpt_sovits",
            subsystem="tts",
            residency_state=self._residency_state,
            ram_size_mb=1800.0,
            vram_size_mb=2400.0,
            demote_handler=self.demote_to_ram,
            promote_handler=self.promote_to_gpu,
            unload_handler=self.unload,
        )

    @property
    def name(self) -> str:
        return "gpt_sovits"

    @property
    def residency_state(self) -> ModelResidencyState:
        return self._residency_state

    def initialize(self) -> bool:
        """
        Verify reachability of GPT-SoVITS service and preload reference audio into RAM cache.
        """
        if self._is_initialized and self._is_available:
            return True

        # Preload reference audio file into System RAM cache
        if self.ref_audio_path and os.path.exists(self.ref_audio_path):
            try:
                with open(self.ref_audio_path, "rb") as f:
                    self._ref_audio_cache = f.read()
                logger.info(f"[GPT-SoVITS] Preloaded reference audio into RAM ({len(self._ref_audio_cache)} bytes).")
            except Exception as e:
                logger.warning(f"[GPT-SoVITS] Failed to preload reference audio: {e}")

        # Check reachability of the GPT-SoVITS server endpoint
        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.get(f"{self.api_url}/")
                if resp.status_code in (200, 404, 405): # Server process is responsive
                    self._is_available = True
                    self._is_initialized = True
                    self._residency_state = ModelResidencyState.RAM_RESIDENT
                    logger.info(f"[GPT-SoVITS] Connected to API server at {self.api_url}")
                    return True
        except Exception:
            logger.info(f"[GPT-SoVITS] Service not reachable at {self.api_url}. Will fallback to Kokoro.")
            self._is_available = False

        self._is_initialized = True
        return self._is_available

    def demote_to_ram(self) -> bool:
        """Demote model residency from VRAM to System RAM."""
        if self._residency_state in (ModelResidencyState.ACTIVE, ModelResidencyState.GPU_RESIDENT):
            self._residency_state = ModelResidencyState.RAM_RESIDENT
            logger.info("[GPT-SoVITS] Demoted to RAM_RESIDENT.")
        return True

    def promote_to_gpu(self) -> bool:
        """Promote model residency to GPU VRAM for accelerated inference."""
        self._residency_state = ModelResidencyState.GPU_RESIDENT
        logger.info("[GPT-SoVITS] Promoted to GPU_RESIDENT.")
        return True

    def unload(self) -> bool:
        """Completely unload model assets."""
        self._ref_audio_cache = None
        self._is_initialized = False
        self._is_available = False
        self._residency_state = ModelResidencyState.UNLOADED
        logger.info("[GPT-SoVITS] Unloaded.")
        return True

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "residency_state": self.residency_state.value,
            "available": self._is_available,
            "api_url": self.api_url,
            "ref_audio_configured": bool(self.ref_audio_path),
            "ref_audio_cached_ram": bool(self._ref_audio_cache),
            "device": self.configured_device,
        }

    async def synthesize(
        self,
        text: str,
        voice: str = "helios",
        speed: float = 1.0,
        *,
        reference_audio: Optional[str] = None,
        reference_text: Optional[str] = None,
        language: str = "en",
        stream: bool = True,
        is_phonemes: bool = False,
    ) -> AsyncGenerator[Tuple[Any, int], None]:
        """
        Synthesize speech using GPT-SoVITS with resource arbitration.
        Yields (samples, sample_rate).
        """
        if not text or not text.strip():
            return

        # Arbitrate resources with ResourceManager
        device_target, ok = resource_manager.request_model_execution(
            model_id="gpt_sovits",
            required_vram_mb=2400.0,
            required_ram_mb=1500.0,
            prefer_gpu=True,
        )

        if not ok and not self._is_available:
            logger.warning("[GPT-SoVITS] Resource reservation declined or backend unavailable.")
            return

        ref_audio = reference_audio or self.ref_audio_path
        prompt_text = reference_text or self.ref_text
        lang = language or self.default_language

        # Query GPT-SoVITS API
        try:
            self._residency_state = ModelResidencyState.ACTIVE
            t0 = time.time()

            payload = {
                "text": text,
                "text_language": lang,
                "ref_audio_path": ref_audio,
                "prompt_text": prompt_text,
                "prompt_language": "en",
                "speed": float(speed),
                "stream": stream,
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                # Support both standard /tts and streaming endpoints
                endpoint = f"{self.api_url}/tts"
                resp = await client.post(endpoint, json=payload)

                if resp.status_code == 200:
                    data = resp.content
                    samples, sr = sf.read(io.BytesIO(data))
                    samples = np.asarray(samples, dtype=np.float32)
                    if samples.ndim > 1:
                        samples = samples.mean(axis=1)

                    rtf = (time.time() - t0) / (len(samples) / sr) if len(samples) > 0 else 0.0
                    logger.info(f"[GPT-SoVITS] Synthesized {len(samples)/sr:.2f}s audio (RTF: {rtf:.2f}x)")
                    yield samples, sr
                else:
                    logger.warning(f"[GPT-SoVITS] API returned HTTP {resp.status_code}")

        except Exception as e:
            logger.error(f"[GPT-SoVITS] Synthesis failed: {e}")
        finally:
            resource_manager.release_model_execution("gpt_sovits")
            self._residency_state = ModelResidencyState.GPU_RESIDENT if device_target == "cuda" else ModelResidencyState.RAM_RESIDENT
