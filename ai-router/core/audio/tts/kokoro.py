"""
HELIOS Kokoro TTS Engine
Lightweight, fast ONNX-based speech synthesis using kokoro-onnx.
Focused strictly on model inference and raw audio generation.
"""
import os
import urllib.request
import logging
from typing import Optional, List, Tuple, AsyncGenerator, Dict, Any
from .base import BaseTTSBackend, ModelResidencyState

logger = logging.getLogger(__name__)


class KokoroTTS(BaseTTSBackend):
    """
    Dedicated Kokoro ONNX inference backend.
    Handles model verification, lazy initialization, voice resolution,
    and asynchronous chunked speech generation.
    """

    def __init__(self, model_dir: Optional[str] = None):
        self.model_dir = model_dir or os.environ.get("KOKORO_MODEL_DIR", ".models/kokoro")
        
        # Prefer v1.0 over legacy v0_19 for full 54-voice catalogue (af_heart, jf_alpha, etc.)
        v1_onnx = os.path.join(self.model_dir, "kokoro-v1.0.onnx")
        v0_onnx = os.path.join(self.model_dir, "kokoro-v0_19.onnx")
        self.onnx_path = v1_onnx if os.path.exists(v1_onnx) else (v0_onnx if os.path.exists(v0_onnx) else v1_onnx)
        
        v1_voices = os.path.join(self.model_dir, "voices-v1.0.bin")
        v0_voices = os.path.join(self.model_dir, "voices.bin")
        self.voices_path = v1_voices if os.path.exists(v1_voices) else (v0_voices if os.path.exists(v0_voices) else v1_voices)

        self._kokoro = None
        self._is_initialized = False
        self._available_voices: List[str] = []
        self._resolved_voice: Optional[str] = None
        self._resolved_voice_request: Optional[str] = None
        self._residency_state: ModelResidencyState = ModelResidencyState.UNLOADED

    @property
    def name(self) -> str:
        return "kokoro"

    @property
    def residency_state(self) -> ModelResidencyState:
        return self._residency_state

    def _ensure_models(self) -> bool:
        """Downloads the ONNX model and voices.bin if they don't exist."""
        os.makedirs(self.model_dir, exist_ok=True)

        onnx_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx"
        voices_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.bin"

        if not os.path.exists(self.onnx_path):
            logger.info(f"Downloading Kokoro ONNX model to {self.onnx_path}...")
            try:
                urllib.request.urlretrieve(onnx_url, self.onnx_path)
            except Exception as e:
                logger.error(f"Failed to download Kokoro ONNX model: {e}")
                return False

        if not os.path.exists(self.voices_path):
            logger.info(f"Downloading Kokoro voices.bin to {self.voices_path}...")
            try:
                urllib.request.urlretrieve(voices_url, self.voices_path)
            except Exception as e:
                logger.error(f"Failed to download Kokoro voices.bin: {e}")
                return False

        return True

    def initialize(self) -> bool:
        """Lazily initialize the ONNX session to avoid blocking the main thread initially."""
        if self._is_initialized:
            return True

        try:
            if not self._ensure_models():
                return False

            from kokoro_onnx import Kokoro
            self._kokoro = Kokoro(self.onnx_path, self.voices_path)
            try:
                self._available_voices = self._kokoro.get_voices()
            except Exception:
                self._available_voices = []

            self._is_initialized = True
            logger.info(f"Kokoro TTS initialized successfully. Available voices: {len(self._available_voices)}")
            return True
        except ImportError:
            logger.error("kokoro-onnx is not installed. Voice features will be disabled.")
            return False
        except Exception as e:
            logger.error(f"Error initializing Kokoro TTS: {e}")
            return False

    def get_available_voices(self) -> List[str]:
        """Returns list of available Kokoro voice names."""
        if not self._is_initialized:
            self.initialize()
        return list(self._available_voices)

    def phonemize(self, text: str) -> Optional[str]:
        """
        Convert text into IPA phonemes using Kokoro's underlying tokenizer.
        Returns phoneme string or None if unavailable.
        """
        if not self._is_initialized:
            if not self.initialize():
                return None
        try:
            if hasattr(self._kokoro, "tokenizer") and hasattr(self._kokoro.tokenizer, "phonemize"):
                return self._kokoro.tokenizer.phonemize(text)
        except Exception as e:
            logger.debug(f"Kokoro phonemize fallback: {e}")
        return None

    def resolve_voice(self, requested_voice: str) -> str:
        """Resolves requested voice against cached available voices."""
        if not self._is_initialized:
            self.initialize()

        if self._resolved_voice and self._resolved_voice_request == requested_voice:
            return self._resolved_voice

        available = self._available_voices or (self._kokoro.get_voices() if self._kokoro else [])
        if available:
            if requested_voice in available:
                self._resolved_voice = requested_voice
            else:
                logger.warning(f"Voice '{requested_voice}' not found in Kokoro. Falling back to '{available[0]}'.")
                self._resolved_voice = available[0]
        else:
            self._resolved_voice = requested_voice

        self._resolved_voice_request = requested_voice
        return self._resolved_voice

    def demote_to_ram(self) -> bool:
        """Kokoro runs via ONNX runtime on CPU/RAM, so it is already in system RAM."""
        if self._residency_state in (ModelResidencyState.ACTIVE, ModelResidencyState.GPU_RESIDENT):
            self._residency_state = ModelResidencyState.RAM_RESIDENT
        return True

    def promote_to_gpu(self) -> bool:
        """Kokoro is primarily CPU-optimized ONNX; keep marked as RAM_RESIDENT."""
        return True

    def unload(self) -> bool:
        """Release ONNX session and voice binaries from memory."""
        self._kokoro = None
        self._is_initialized = False
        self._residency_state = ModelResidencyState.UNLOADED
        logger.info("Kokoro TTS unloaded from memory.")
        return True

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "residency_state": self.residency_state.value,
            "initialized": self._is_initialized,
            "voices_count": len(self._available_voices),
            "backend": "onnx",
            "device": "cpu",
        }

    async def synthesize(
        self,
        text: str,
        voice: str = "am_michael",
        speed: float = 1.0,
        *,
        reference_audio: Optional[str] = None,
        reference_text: Optional[str] = None,
        language: str = "en",
        stream: bool = True,
        is_phonemes: bool = False,
    ) -> AsyncGenerator[Tuple[any, int], None]:
        """
        Synthesize text into raw PCM audio chunks.
        Returns an async generator of (samples, sample_rate).
        """
        if not text or not text.strip():
            return

        if not self._is_initialized:
            if not self.initialize():
                return

        # Parameter validation & bounds
        validated_speed = max(0.5, min(2.0, float(speed)))
        target_voice = self.resolve_voice(voice)
        prev_state = self._residency_state
        self._residency_state = ModelResidencyState.ACTIVE

        try:
            import asyncio
            loop = asyncio.get_running_loop()

            # Execute model inference in executor thread to prevent blocking event loop
            samples, sample_rate = await loop.run_in_executor(
                None,
                lambda: self._kokoro.create(
                    text,
                    voice=target_voice,
                    speed=validated_speed,
                    is_phonemes=is_phonemes,
                ),
            )

            if samples is not None and len(samples) > 0:
                yield samples, sample_rate

        except Exception as e:
            logger.error(f"Kokoro synthesis failed for voice='{target_voice}', speed={validated_speed}: {e}")
        finally:
            self._residency_state = ModelResidencyState.RAM_RESIDENT
