import os
import urllib.request
import logging
from typing import Optional, Generator, Iterator

logger = logging.getLogger(__name__)

class KokoroTTS:
    def __init__(self, model_dir: str = ".models/kokoro"):
        self.model_dir = model_dir
        self.onnx_path = os.path.join(self.model_dir, "kokoro-v0_19.onnx")
        self.voices_path = os.path.join(self.model_dir, "voices.bin")
        self._kokoro = None
        self._is_initialized = False
        
    def _ensure_models(self):
        """Downloads the ONNX model and voices.bin if they don't exist."""
        os.makedirs(self.model_dir, exist_ok=True)
        
        onnx_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx"
        voices_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.bin"
        
        if not os.path.exists(self.onnx_path):
            logger.info("Downloading Kokoro ONNX model (this may take a while)...")
            try:
                urllib.request.urlretrieve(onnx_url, self.onnx_path)
            except Exception as e:
                logger.error(f"Failed to download Kokoro ONNX model: {e}")
                return False
                
        if not os.path.exists(self.voices_path):
            logger.info("Downloading Kokoro voices.bin...")
            try:
                urllib.request.urlretrieve(voices_url, self.voices_path)
            except Exception as e:
                logger.error(f"Failed to download Kokoro voices.bin: {e}")
                return False
                
        return True

    def initialize(self):
        """Lazily initialize the ONNX session to avoid blocking the main thread initially."""
        if self._is_initialized:
            return True
            
        try:
            if not self._ensure_models():
                return False
                
            from kokoro_onnx import Kokoro
            # Initialize with ONNX
            self._kokoro = Kokoro(self.onnx_path, self.voices_path)
            self._is_initialized = True
            logger.info("Kokoro TTS initialized successfully.")
            return True
        except ImportError:
            logger.error("kokoro-onnx is not installed. Voice features will be disabled.")
            return False
        except Exception as e:
            logger.error(f"Error initializing Kokoro TTS: {e}")
            return False

    async def synthesize(self, text: str, voice: str = "af_heart", speed: float = 1.0):
        """
        Synthesize text into raw PCM audio chunks.
        Returns an async generator of (samples, sample_rate).
        """
        if not self._is_initialized:
            if not self.initialize():
                return

        try:
            # Resolve voice once and cache — avoids get_voices() on every sentence
            if not hasattr(self, '_resolved_voice') or self._resolved_voice_request != voice:
                available_voices = self._kokoro.get_voices()
                if voice not in available_voices:
                    logger.warning(f"Voice '{voice}' not found. Falling back to first available.")
                    self._resolved_voice = available_voices[0] if available_voices else voice
                else:
                    self._resolved_voice = voice
                self._resolved_voice_request = voice

            # Using the async create_stream
            stream = self._kokoro.create_stream(text, voice=self._resolved_voice, speed=speed)
            
            async for chunk in stream:
                # chunk contains samples (numpy array) and sample_rate
                samples, sample_rate = chunk
                yield samples, sample_rate
                
        except Exception as e:
            logger.error(f"Kokoro synthesis failed: {e}")
