"""
HELIOS TTS Base Abstract Interface
Defines the common asynchronous contract for all speech synthesis backends (Kokoro, GPT-SoVITS, etc.).
"""
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Tuple, Any, Optional, Dict, List
from enum import Enum


class ModelResidencyState(str, Enum):
    """Lifecycle states for models managed across RAM and GPU VRAM."""
    UNLOADED = "UNLOADED"
    RAM_RESIDENT = "RAM_RESIDENT"
    GPU_RESIDENT = "GPU_RESIDENT"
    ACTIVE = "ACTIVE"
    EVICTING = "EVICTING"


class BaseTTSBackend(ABC):
    """
    Abstract Base Class for all HELIOS Text-to-Speech engines.
    Ensures unified synthesis signature, residency management, and diagnostics.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the TTS backend (e.g. 'kokoro', 'gpt_sovits')."""
        pass

    @property
    @abstractmethod
    def residency_state(self) -> ModelResidencyState:
        """Current model residency state (UNLOADED, RAM_RESIDENT, GPU_RESIDENT, ACTIVE)."""
        pass

    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the model backend (lazy or eager). Returns True on success."""
        pass

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: str = "default",
        speed: float = 1.0,
        *,
        reference_audio: Optional[str] = None,
        reference_text: Optional[str] = None,
        language: str = "en",
        stream: bool = True,
        is_phonemes: bool = False,
    ) -> AsyncGenerator[Tuple[Any, int], None]:
        """
        Synthesize speech from text.
        Yields (audio_samples, sample_rate) tuples where audio_samples is a 1D float32 or int16 numpy array.
        """
        pass

    @abstractmethod
    def demote_to_ram(self) -> bool:
        """Move GPU weights/tensors to system RAM to free VRAM for other services."""
        pass

    @abstractmethod
    def promote_to_gpu(self) -> bool:
        """Promote RAM-resident weights to GPU VRAM for active inference."""
        pass

    @abstractmethod
    def unload(self) -> bool:
        """Completely unload model from memory."""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Return diagnostic dictionary for status and telemetry."""
        pass
