"""
HELIOS Audio Processor
Post-processing audio chain for Kokoro TTS PCM output:
1. DC removal
2. Gentle high-pass filter (~60-80 Hz, default 70 Hz)
3. Light dynamic range compression (~2:1 ratio)
4. Peak limiter / soft clipper (-1 dB ceiling)
"""
import numpy as np
import logging
from typing import Optional, Union

import config

logger = logging.getLogger(__name__)


class AudioProcessor:
    """
    Sub-millisecond audio conditioning chain operating on 24 kHz float32 PCM.
    Polishes TTS output to remove low-frequency rumble, tame dynamics, and prevent clipping.
    """

    def __init__(
        self,
        sample_rate: int = 24000,
        highpass_cutoff: Optional[float] = None,
        compression_ratio: Optional[float] = None,
        limiter_ceiling_db: Optional[float] = None,
        enabled: Optional[bool] = None,
    ):
        self.sample_rate = int(sample_rate or 24000)
        self.enabled = (
            enabled
            if enabled is not None
            else getattr(config, "VOICE_AUDIO_PROCESSING_ENABLED", True)
        )
        self.highpass_cutoff = float(
            highpass_cutoff
            if highpass_cutoff is not None
            else getattr(config, "VOICE_AUDIO_HIGHPASS_CUTOFF", 70.0)
        )
        self.compression_enabled = getattr(config, "VOICE_AUDIO_COMPRESSION_ENABLED", True)
        self.compression_ratio = float(
            compression_ratio
            if compression_ratio is not None
            else getattr(config, "VOICE_AUDIO_COMPRESSION_RATIO", 2.0)
        )
        self.limiter_ceiling_db = float(
            limiter_ceiling_db
            if limiter_ceiling_db is not None
            else getattr(config, "VOICE_AUDIO_LIMITER_CEILING_DB", -1.0)
        )

        # Precompute FIR High-pass filter kernel
        self._fir_kernel = self._design_fir_highpass(self.sample_rate, self.highpass_cutoff, taps=31)

        # Precalculate limiter linear ceiling
        # ceiling_linear = 10^(ceiling_db / 20)
        self._ceiling_linear = float(10.0 ** (self.limiter_ceiling_db / 20.0))

    def _design_fir_highpass(self, sample_rate: int, cutoff: float, taps: int = 31) -> np.ndarray:
        """Design a low-latency windowed-sinc FIR high-pass filter kernel."""
        if taps % 2 == 0:
            taps += 1
        fc = max(10.0, min(float(cutoff), sample_rate * 0.45)) / float(sample_rate)
        n = np.arange(taps) - (taps - 1) / 2.0

        # Sinc for lowpass prototype
        h_lp = 2.0 * fc * np.sinc(2.0 * fc * n)
        # Blackman window to suppress sidelobes
        h_lp *= np.blackman(taps)
        sum_lp = np.sum(h_lp)
        if sum_lp != 0:
            h_lp /= sum_lp

        # Spectral inversion to turn lowpass into highpass
        h_hp = -h_lp
        h_hp[(taps - 1) // 2] += 1.0
        return h_hp.astype(np.float32)

    def process(self, samples: Union[np.ndarray, list], sample_rate: Optional[int] = None) -> np.ndarray:
        """
        Process audio chunk through DC removal, high-pass filter, compression, and limiter.
        Returns float32 1D numpy array in range [-1.0, 1.0].
        """
        if not self.enabled:
            return np.asarray(samples, dtype=np.float32).flatten()

        arr = np.asarray(samples, dtype=np.float32).flatten()
        if len(arr) == 0:
            return arr

        sr = int(sample_rate or self.sample_rate)
        if sr != self.sample_rate:
            # Recalculate kernel if sample rate changed
            self.sample_rate = sr
            self._fir_kernel = self._design_fir_highpass(self.sample_rate, self.highpass_cutoff, taps=31)

        # 1. DC Removal
        # Subtract mean offset across chunk
        mean_dc = float(np.mean(arr))
        if abs(mean_dc) > 1e-5:
            arr = arr - mean_dc

        # 2. Gentle High-Pass Filter (~60-80 Hz)
        if len(arr) >= len(self._fir_kernel):
            arr = np.convolve(arr, self._fir_kernel, mode="same")

        # 3. Dynamic Range Compression (optional light compression)
        if self.compression_enabled and len(arr) > 120 and self.compression_ratio > 1.0:
            # 5ms blocks (120 samples at 24kHz)
            block_size = max(16, int(sr * 0.005))
            num_blocks = len(arr) // block_size
            if num_blocks > 0:
                core = arr[: num_blocks * block_size].reshape(num_blocks, block_size)
                # RMS in dBFS
                rms = np.sqrt(np.mean(core * core, axis=1) + 1e-9)
                rms_db = 20.0 * np.log10(rms + 1e-6)
                thresh_db = -16.0
                ratio = self.compression_ratio
                
                # Gain reduction in dB
                gr_db = np.where(rms_db > thresh_db, (rms_db - thresh_db) * (1.0 - 1.0 / ratio), 0.0)
                gain = 10.0 ** (-gr_db / 20.0)
                gain_envelope = np.repeat(gain, block_size)

                # Smooth envelope slightly with moving average to avoid clicks
                if len(gain_envelope) > 16:
                    pad = np.pad(gain_envelope, (8, 8), mode="edge")
                    gain_envelope = np.convolve(pad, np.ones(16) / 16.0, mode="valid")[:len(gain_envelope)]

                arr[: len(gain_envelope)] *= gain_envelope

        # 4. Soft Peak Limiter
        # Ceiling: -1 dB (0.89125 linear)
        peak = float(np.max(np.abs(arr)))
        ceiling = self._ceiling_linear
        if peak > ceiling:
            # Smooth soft-knee saturation prevents hard clipping artifacts
            arr = np.tanh(arr / ceiling) * ceiling

        # Guarantee final output is within [-1.0, 1.0] float32
        return np.clip(arr, -1.0, 1.0).astype(np.float32)
