import io
import wave
import tempfile
import urllib.request
import logging
import os

logger = logging.getLogger(__name__)

# Import guard for pywhispercpp
try:
    from pywhispercpp.model import Model as WhisperModel
    _WHISPER_AVAILABLE = True
except ImportError:
    _WHISPER_AVAILABLE = False
    logger.warning("pywhispercpp not installed. Run `pip install pywhispercpp`. Falling back to Google STT.")


class WhisperLocalSTT:
    """Fully offline Speech-to-Text engine using whisper.cpp via pywhispercpp.

    Lazy-loads the GGML model on first use. Auto-downloads from HuggingFace
    if no model file exists locally. Designed for 8GB RAM systems (~140MB
    for ggml-base.en).
    """

    def __init__(
        self,
        model_path: str = ".models/whisper/ggml-base.en.bin",
        fallback_path: str = ".models/whisper/ggml-tiny.en.bin",
    ):
        self.model_path = model_path
        self.fallback_path = fallback_path
        self._model: "WhisperModel | None" = None

    def initialize(self) -> bool:
        """Explicitly load the whisper model. Returns True on success."""
        if not _WHISPER_AVAILABLE:
            return False
        if self._model is not None:
            return True

        target_path = self._resolve_model_path()
        if target_path is None:
            return False

        try:
            # pywhispercpp.Model expects the path WITHOUT extension in some builds,
            # but passing the full .bin path works with recent versions.
            self._model = WhisperModel(target_path, n_threads=max(1, os.cpu_count() - 1))
            logger.info(f"Whisper model loaded from {target_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            return False

    def _resolve_model_path(self) -> str | None:
        """Find or download the model file. Returns the resolved path or None."""
        if os.path.exists(self.model_path):
            return self.model_path
        if os.path.exists(self.fallback_path):
            logger.info(f"Base model not found, using fallback: {self.fallback_path}")
            return self.fallback_path

        # Neither exists — download the base model
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        url = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin"
        logger.info(f"Downloading Whisper base.en model from {url} ...")

        def _progress(block_num, block_size, total_size):
            if total_size > 0:
                pct = int(block_num * block_size * 100 / total_size)
                if pct % 20 == 0:
                    logger.info(f"  Download progress: {pct}%")

        try:
            urllib.request.urlretrieve(url, self.model_path, _progress)
            logger.info("Whisper model download complete.")
            return self.model_path
        except Exception as e:
            logger.error(f"Failed to download Whisper model: {e}")
            return None

    def is_loaded(self) -> bool:
        """Returns whether the model is ready for inference."""
        if self._model is None and _WHISPER_AVAILABLE:
            self.initialize()
        return self._model is not None

    def transcribe(self, audio_data) -> str:
        """Transcribe a speech_recognition.AudioData object to text.

        Converts the PCM audio to a temporary WAV file (16kHz mono 16-bit),
        runs whisper inference, and returns the transcribed string.
        Returns empty string on any failure.
        """
        if not self.is_loaded():
            return ""

        try:
            # Write AudioData to a temporary WAV file (pywhispercpp needs a file path)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
                with wave.open(tmp, "wb") as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(audio_data.sample_width)
                    wav_file.setframerate(audio_data.sample_rate)
                    wav_file.writeframes(audio_data.get_raw_data())

            # pywhispercpp transcribe returns a list of Segment objects
            segments = self._model.transcribe(tmp_path)
            text = " ".join(seg.text for seg in segments).strip()

            # Cleanup temp file
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

            return text

        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return ""



