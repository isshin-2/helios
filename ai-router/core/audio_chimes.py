"""
HELIOS — Ambient Audio Chime Engine
Produces subtle, non-intrusive cybernetic audio feedback cues for state transitions.
Uses native Windows sound synthesis (winsound) with zero external audio dependencies.
"""

import sys
import logging
import threading
from typing import Optional

logger = logging.getLogger("helios.audio_chimes")

class AudioChimeEngine:
    """Provides non-blocking synthesized cybernetic frequency chimes."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._is_windows = sys.platform == "win32"

    def _play_tone(self, freq: int, duration_ms: int):
        if not self.enabled or not self._is_windows:
            return
        try:
            import winsound
            winsound.Beep(freq, duration_ms)
        except Exception as e:
            logger.debug(f"Audio tone playback failed: {e}")

    def play_chime(self, chime_type: str):
        """Asynchronously play a sound pattern to avoid blocking the main thread."""
        if not self.enabled:
            return

        def _runner():
            if chime_type == "thinking":
                # Subtle ascending dual-tone: 520Hz -> 650Hz
                self._play_tone(520, 60)
                self._play_tone(650, 70)
            elif chime_type == "complete":
                # Pleasant cyber resolve: 650Hz -> 880Hz -> 1040Hz
                self._play_tone(650, 50)
                self._play_tone(880, 60)
                self._play_tone(1040, 80)
            elif chime_type == "abort":
                # Low warning tone: 440Hz -> 330Hz
                self._play_tone(440, 90)
                self._play_tone(330, 110)
            elif chime_type == "cluster_switch":
                # Quick double-click blip: 800Hz
                self._play_tone(800, 40)
                self._play_tone(900, 50)

        threading.Thread(target=_runner, daemon=True).start()

# Global default instance
chime_engine = AudioChimeEngine()
