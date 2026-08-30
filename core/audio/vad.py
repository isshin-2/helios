import logging
import torch
import numpy as np

logger = logging.getLogger(__name__)

class SileroVAD:
    """
    Dedicated VAD layer using Silero VAD (via PyTorch Hub).
    Detects human speech onset and triggers a callback to interrupt HELIOS.
    """
    def __init__(self, threshold: float = 0.5, sampling_rate: int = 16000):
        self.threshold = threshold
        self.sampling_rate = sampling_rate
        self.model = None
        self.get_speech_timestamps = None
        self._is_initialized = False
        
    def initialize(self):
        if self._is_initialized:
            return True
        try:
            # Silero VAD requires torch
            self.model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False,
                trust_repo=True
            )
            (self.get_speech_timestamps, _, _, _, _) = utils
            self._is_initialized = True
            logger.info("Silero VAD initialized.")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Silero VAD: {e}")
            return False

    def is_speech(self, audio_chunk: bytes, frame_rate: int = 16000, sample_width: int = 2) -> bool:
        """
        Takes raw audio bytes, converts to a tensor, and runs VAD.
        Returns True if speech probability > threshold.
        """
        if not self._is_initialized:
            if not self.initialize():
                return False
                
        try:
            # Convert bytes to numpy array (int16) then to float32 tensor
            if sample_width == 2:
                audio_np = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0
            else:
                return False
                
            tensor = torch.from_numpy(audio_np)
            
            # The model expects a batch dimension or just 1D tensor
            # Return true if any segment in this chunk contains speech
            speech_prob = self.model(tensor, frame_rate).item()
            return speech_prob > self.threshold
        except Exception as e:
            logger.debug(f"VAD error (likely chunk size mismatch): {e}")
            return False
