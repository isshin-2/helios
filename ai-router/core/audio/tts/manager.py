"""
HELIOS Multi-Backend TTS Manager
Coordinates between GPT-SoVITS, KokoroTTS, LocalAI, and other speech engines.
Provides automatic fallback, hardware resource awareness, and diagnostics.
"""
import logging
from typing import AsyncGenerator, Tuple, Any, Optional, Dict, List
import config
from .base import BaseTTSBackend, ModelResidencyState
from .kokoro import KokoroTTS
from .gpt_sovits import GPTSoVITS_TTS
from .resource_policy import resource_manager

logger = logging.getLogger(__name__)


class TTSBackendManager(BaseTTSBackend):
    """
    Unified manager routing speech requests to the best available backend:
    Priority:
      1. GPT-SoVITS (if enabled, reachable, and resource-approved)
      2. KokoroTTS (high-quality local ONNX, guaranteed fallback)
      3. Silent / graceful degradation
    """

    def __init__(self):
        self.kokoro = KokoroTTS()
        self.gpt_sovits = GPTSoVITS_TTS()
        self.configured_backend = getattr(config, "VOICE_BACKEND", "kokoro").lower()
        self._active_backend_name = "kokoro"

    @property
    def name(self) -> str:
        return "manager"

    @property
    def residency_state(self) -> ModelResidencyState:
        if self._active_backend_name == "gpt_sovits":
            return self.gpt_sovits.residency_state
        return self.kokoro.residency_state

    def initialize(self) -> bool:
        """Initialize primary and fallback backends."""
        gpt_ready = False
        if getattr(config, "GPT_SOVITS_ENABLED", True) and self.configured_backend in ("gpt_sovits", "auto"):
            gpt_ready = self.gpt_sovits.initialize()

        kokoro_ready = self.kokoro.initialize()

        if gpt_ready and self.configured_backend in ("gpt_sovits", "auto"):
            self._active_backend_name = "gpt_sovits"
        else:
            self._active_backend_name = "kokoro"

        logger.info(f"[TTSManager] Active TTS Backend: '{self._active_backend_name}' (Kokoro available: {kokoro_ready})")
        return kokoro_ready or gpt_ready

    def demote_to_ram(self) -> bool:
        self.gpt_sovits.demote_to_ram()
        self.kokoro.demote_to_ram()
        return True

    def promote_to_gpu(self) -> bool:
        return self.gpt_sovits.promote_to_gpu()

    def unload(self) -> bool:
        self.gpt_sovits.unload()
        self.kokoro.unload()
        return True

    def get_status(self) -> Dict[str, Any]:
        return {
            "tts_backend": self._active_backend_name,
            "configured_backend": self.configured_backend,
            "residency_state": self.residency_state.value,
            "gpt_sovits": self.gpt_sovits.get_status(),
            "kokoro": self.kokoro.get_status(),
            "resource_manager": resource_manager.get_diagnostics(),
        }

    def phonemize(self, text: str) -> Optional[str]:
        """Delegate phonemize to Kokoro for lip-sync viseme generation."""
        return self.kokoro.phonemize(text)

    def resolve_voice(self, requested_voice: str) -> str:
        """Delegate voice resolution."""
        return self.kokoro.resolve_voice(requested_voice)

    async def synthesize(
        self,
        text: str,
        voice: str = "af_heart",
        speed: float = 1.0,
        *,
        reference_audio: Optional[str] = None,
        reference_text: Optional[str] = None,
        language: str = "en",
        stream: bool = True,
        is_phonemes: bool = False,
    ) -> AsyncGenerator[Tuple[Any, int], None]:
        """
        Synthesize speech with automatic fallback.
        Tries GPT-SoVITS first if configured and available; falls back to Kokoro.
        """
        use_gpt_sovits = (
            getattr(config, "GPT_SOVITS_ENABLED", True)
            and (self.configured_backend == "gpt_sovits" or voice in ("helios_cloned", "airi", "airi_cloned"))
            and self.gpt_sovits._is_available
        )

        if voice in ("airi", "airi_cloned") and not reference_audio:
            reference_audio = "voices/airi/reference.wav"
            reference_text = reference_text or "voices/airi/reference.txt"

        produced_audio = False
        if use_gpt_sovits:
            try:
                self._active_backend_name = "gpt_sovits"
                async for samples, sr in self.gpt_sovits.synthesize(
                    text,
                    voice=voice,
                    speed=speed,
                    reference_audio=reference_audio,
                    reference_text=reference_text,
                    language=language,
                    stream=stream,
                ):
                    produced_audio = True
                    yield samples, sr
            except Exception as e:
                logger.warning(f"[TTSManager] GPT-SoVITS synthesis error: {e}. Falling back to Kokoro...")

        if not produced_audio:
            # Kokoro fallback
            self._active_backend_name = "kokoro"
            async for samples, sr in self.kokoro.synthesize(
                text,
                voice=voice,
                speed=speed,
                is_phonemes=is_phonemes,
            ):
                yield samples, sr
