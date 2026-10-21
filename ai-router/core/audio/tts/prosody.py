"""
HELIOS Prosody Engine
Calculates dynamic prosodic parameters (speed, pause, energy) based on
character emotion, intensity, style, and sentence context.
"""
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple, Any

try:
    import yaml
except ImportError:
    yaml = None

import config

logger = logging.getLogger(__name__)

# Base Emotion prosody modifiers (speed factor, energy factor)
DEFAULT_EMOTION_PROSODY: Dict[str, Tuple[float, float]] = {
    "neutral": (1.00, 1.00),
    "natural": (1.00, 1.00),
    "happy": (1.03, 1.05),
    "curious": (0.98, 1.00),
    "excited": (1.06, 1.10),
    "serious": (0.92, 0.92),
    "concerned": (0.90, 0.90),
    "amused": (0.96, 1.02),
    "relaxed": (0.94, 0.92),
    "confused": (0.95, 0.95),
}

# Style prosody modifiers
DEFAULT_STYLE_PROSODY: Dict[str, Tuple[float, float]] = {
    "natural": (1.00, 1.00),
    "energetic": (1.04, 1.06),
    "confident": (1.02, 1.02),
    "relaxed": (0.94, 0.92),
    "shy": (0.92, 0.88),
    "dramatic": (0.91, 1.05),
}

# Sentence type modifiers: (speed_multiplier, pause_before_sec, pause_after_sec)
DEFAULT_SENTENCE_TYPE_MODIFIERS: Dict[str, Tuple[float, float, float]] = {
    "statement": (1.00, 0.0, 0.05),
    "question": (0.98, 0.0, 0.12),
    "exclamation": (1.04, 0.0, 0.08),
    "technical_explanation": (0.94, 0.04, 0.12),
    "warning": (0.88, 0.12, 0.20),
    "short_reaction": (1.05, 0.0, 0.05),
}


@dataclass
class ProsodyProfile:
    name: str = "helios"
    voice: str = "am_michael"
    base_speed: float = 1.0
    emotion_map: Dict[str, Tuple[float, float]] = field(
        default_factory=lambda: dict(DEFAULT_EMOTION_PROSODY)
    )
    style_map: Dict[str, Tuple[float, float]] = field(
        default_factory=lambda: dict(DEFAULT_STYLE_PROSODY)
    )


class ProsodyEngine:
    """
    Evaluates context, character state, and sentence morphology to produce
    natural conversational speech speed and pause metrics.
    """

    WARNING_KEYWORDS = re.compile(
        r"\b(warning|caution|danger|critical|emergency|overheating|overcurrent|"
        r"malicious|hazard|quarantined|alert|fatal)\b",
        re.IGNORECASE,
    )
    TECHNICAL_KEYWORDS = re.compile(
        r"\b(baud|registers|schematic|transistor|pinout|microcontroller|firmware|"
        r"compiler|latency|concurrency|voltage|current|capacitance|resistance|"
        r"frequency|interrupt|oscillator|architecture|algorithm)\b",
        re.IGNORECASE,
    )

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._default_config_path()
        self.profile = self._build_default_profile()
        self.reload()

    def _default_config_path(self) -> Path:
        base = Path(__file__).resolve().parent.parent.parent.parent
        return base / "config" / "voice_profiles.yaml"

    def _build_default_profile(self) -> ProsodyProfile:
        configured_voice = getattr(config, "VOICE_NAME", "am_michael")
        configured_speed = float(getattr(config, "VOICE_SPEED", 1.0))
        return ProsodyProfile(
            name="helios",
            voice=configured_voice,
            base_speed=configured_speed,
        )

    def reload(self):
        """Reload custom voice profiles from config file if available."""
        if self.config_path and Path(self.config_path).exists() and yaml is not None:
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    profile_name = getattr(config, "VOICE_PROSODY_PROFILE", "helios")
                    profiles = data.get("profiles", data) if isinstance(data, dict) else {}
                    if profile_name in profiles:
                        p_data = profiles[profile_name]
                        if isinstance(p_data, dict):
                            voice = p_data.get("voice", self.profile.voice)
                            base_spd = float(p_data.get("base_speed", self.profile.base_speed))
                            
                            # Prosody overrides
                            p_prosody = p_data.get("prosody", {})
                            e_map = dict(DEFAULT_EMOTION_PROSODY)
                            for emo, vals in p_prosody.items():
                                if isinstance(vals, dict):
                                    spd = float(vals.get("speed", 1.0))
                                    nrg = float(vals.get("energy", 1.0))
                                    e_map[emo.lower()] = (spd, nrg)

                            self.profile = ProsodyProfile(
                                name=profile_name,
                                voice=voice,
                                base_speed=base_spd,
                                emotion_map=e_map,
                            )
                            logger.info(f"Loaded voice profile '{profile_name}' from {self.config_path}")
            except Exception as e:
                logger.warning(f"Could not load voice profiles from {self.config_path}: {e}")

    def detect_sentence_type(self, text: str) -> str:
        """
        Classifies sentence morphology into one of:
        - warning
        - technical_explanation
        - question
        - exclamation
        - short_reaction
        - statement
        """
        s = text.strip()
        if not s:
            return "statement"

        # Check safety/warning first
        if self.WARNING_KEYWORDS.search(s):
            return "warning"

        # Check short reaction (1 to 3 words, e.g. 'Got it.', 'Understood.', 'On it!')
        words = s.split()
        if len(words) <= 3 and len(s) < 25:
            return "short_reaction"

        # Check question
        if s.endswith("?") or s.startswith(("Why ", "How ", "What ", "Is ", "Are ", "Can ")):
            return "question"

        # Check exclamation
        if s.endswith("!"):
            return "exclamation"

        # Check technical explanation
        if self.TECHNICAL_KEYWORDS.search(s):
            return "technical_explanation"

        return "statement"

    def compute_prosody(
        self,
        text: str,
        emotion: str = "neutral",
        intensity: float = 0.5,
        style: str = "natural",
        safety_locked: bool = False,
        base_speed_override: Optional[float] = None,
    ) -> Tuple[float, float, float, str]:
        """
        Calculates effective speech parameters.
        Returns:
            (effective_speed, pause_before, pause_after, sentence_type)
        """
        # Safety lock forces serious tone and overrides playful effects
        if safety_locked:
            emotion = "serious"
            style = "natural"
            intensity = max(0.8, intensity)

        # Base speed from config or profile
        base_speed = (
            base_speed_override
            if base_speed_override is not None
            else getattr(config, "VOICE_SPEED", self.profile.base_speed)
        )

        # Detect sentence type
        sentence_type = self.detect_sentence_type(text)

        # If safety locked and not already a warning, treat as warning timing
        if safety_locked and sentence_type == "statement":
            sentence_type = "warning"

        # Emotion modifier: interpolate between 1.0 and emotion_speed based on intensity
        emotion_key = emotion.lower()
        emo_speed, emo_energy = self.profile.emotion_map.get(
            emotion_key, DEFAULT_EMOTION_PROSODY.get("neutral", (1.0, 1.0))
        )
        norm_intensity = max(0.0, min(1.0, float(intensity)))
        effective_emo_speed = 1.0 + (emo_speed - 1.0) * norm_intensity

        # Style modifier
        style_key = style.lower()
        style_speed, style_energy = self.profile.style_map.get(
            style_key, DEFAULT_STYLE_PROSODY.get("natural", (1.0, 1.0))
        )

        # Sentence-type modifier
        st_speed_mult, pause_before, pause_after = DEFAULT_SENTENCE_TYPE_MODIFIERS.get(
            sentence_type, (1.0, 0.0, 0.05)
        )

        # Calculate compound effective speed
        # effective_speed = base * emotion * style * sentence_type
        effective_speed = base_speed * effective_emo_speed * style_speed * st_speed_mult

        # Clamp all generated speed parameters to safe, natural range [0.72, 1.35]
        clamped_speed = max(0.72, min(1.35, round(effective_speed, 3)))

        return clamped_speed, pause_before, pause_after, sentence_type
