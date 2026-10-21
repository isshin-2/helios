"""
HELIOS Speech Planner
Coordinates text normalization, pronunciation resolution, sentence context,
and prosody planning into a unified, actionable SpeechPlan.
"""
import re
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

import config
from .text_normalizer import TextNormalizer, StreamingFilterState
from .pronunciation import EngineeringPronunciationResolver
from .prosody import ProsodyEngine

logger = logging.getLogger(__name__)


@dataclass
class SpeechPlan:
    """Actionable speech synthesis plan produced by SpeechPlanner."""
    text: str                     # Original user/UI display text
    tts_text: str                 # Phonetically normalized text for synthesis
    voice: str                    # Resolved voice identifier
    speed: float                  # Computed effective speech speed
    pause_before: float           # Desired pause before speaking (seconds)
    pause_after: float            # Desired pause after speaking (seconds)
    emotion: str                  # Emotional tone
    intensity: float              # Emotion intensity [0.0, 1.0]
    style: str                    # Posture / speaking style
    sentence_type: str = "statement"
    phonemes: Optional[str] = None
    is_phonemes: bool = False
    safety_locked: bool = False
    turn_id: int = 0

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            other_clean = other.rstrip(".?! \t\n")
            return (
                self.text == other
                or self.tts_text == other
                or self.text.rstrip(".?! \t\n") == other_clean
                or self.tts_text.rstrip(".?! \t\n") == other_clean
            )
        if isinstance(other, SpeechPlan):
            return (
                self.text == other.text
                and self.tts_text == other.tts_text
                and self.voice == other.voice
                and abs(self.speed - other.speed) < 1e-4
            )
        return False


class SpeechPlanner:
    """
    Central speech planning coordinator.
    Transforms raw streaming text and character emotional state into
    an optimized, character-consistent SpeechPlan without modifying display text.
    """

    def __init__(
        self,
        normalizer: Optional[TextNormalizer] = None,
        pronunciation_resolver: Optional[EngineeringPronunciationResolver] = None,
        prosody_engine: Optional[ProsodyEngine] = None,
    ):
        self.normalizer = normalizer or TextNormalizer()
        self.pronunciation_resolver = pronunciation_resolver or EngineeringPronunciationResolver()
        self.prosody_engine = prosody_engine or ProsodyEngine()

        # Sentence segmentation pattern for streaming buffers: lookahead for space/newline
        self.sentence_pattern = re.compile(r'([.?!]+(?=[\s\n])|\n\n+)')

    def plan(
        self,
        text: str,
        emotion: str = "neutral",
        intensity: float = 0.5,
        style: str = "natural",
        safety_locked: bool = False,
        voice: Optional[str] = None,
        base_speed: Optional[float] = None,
        extra_user_dict: Optional[Dict[str, str]] = None,
    ) -> Optional[SpeechPlan]:
        """
        Creates a SpeechPlan for the given sentence.
        Returns None if the sentence should be muted (e.g. system tag or empty).
        """
        if not text or not text.strip():
            return None

        # 1. Text Normalization
        tts_text = self.normalizer.normalize(text)
        if not tts_text or not tts_text.strip():
            return None

        # 2. Engineering Pronunciation Resolution
        tts_text = self.pronunciation_resolver.resolve(tts_text, extra_user_dict=extra_user_dict)

        # 3. Prosody & Speed Calculation
        speed, pause_before, pause_after, sentence_type = self.prosody_engine.compute_prosody(
            text=tts_text,
            emotion=emotion,
            intensity=intensity,
            style=style,
            safety_locked=safety_locked,
            base_speed_override=base_speed,
        )

        # 4. Resolve Voice Identifier
        resolved_voice = voice or getattr(config, "VOICE_NAME", self.prosody_engine.profile.voice)

        return SpeechPlan(
            text=text.strip(),
            tts_text=tts_text.strip(),
            voice=resolved_voice,
            speed=speed,
            pause_before=pause_before,
            pause_after=pause_after,
            emotion="serious" if safety_locked else emotion,
            intensity=round(intensity, 3),
            style="natural" if safety_locked else style,
            sentence_type=sentence_type,
            safety_locked=safety_locked,
        )

    def extract_sentences(self, buffer: str, force: bool = False) -> Tuple[List[str], str]:
        """
        Extracts complete sentences from a streaming text buffer.
        Returns (list_of_extracted_sentences, remaining_buffer).
        Preserves streaming latency with sentence boundaries.
        """
        sentences = []
        curr_buffer = buffer
        while True:
            match = self.sentence_pattern.search(curr_buffer)
            if match:
                end_pos = match.end()
                sentence = curr_buffer[:end_pos].strip()
                curr_buffer = curr_buffer[end_pos:]
                if sentence:
                    sentences.append(sentence)
            else:
                break

        if force and curr_buffer.strip():
            sentences.append(curr_buffer.strip())
            curr_buffer = ""

        return sentences, curr_buffer
