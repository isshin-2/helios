"""
HELIOS Character State System (Phase 1)
Renderer-independent state contract and Character Protocol message builders.
"""
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CharacterMode(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    EXECUTING = "executing"
    SPEAKING = "speaking"
    ERROR = "error"


class CharacterEmotion(str, Enum):
    NEUTRAL = "neutral"
    HAPPY = "happy"
    AMUSED = "amused"
    CURIOUS = "curious"
    EXCITED = "excited"
    CONCERNED = "concerned"
    SERIOUS = "serious"
    CONFUSED = "confused"
    RELAXED = "relaxed"


class CharacterStyle(str, Enum):
    NATURAL = "natural"
    ENERGETIC = "energetic"
    CONFIDENT = "confident"
    RELAXED = "relaxed"
    SHY = "shy"
    DRAMATIC = "dramatic"


VALID_MODES = {m.value for m in CharacterMode}
VALID_EMOTIONS = {e.value for e in CharacterEmotion}
VALID_STYLES = {s.value for s in CharacterStyle}

VALID_MOVEMENTS = {
    "stay",
    "idle",
    "walk_to_user",
    "step_back",
    "circle_user",
    "return_center",
}

VALID_ANIMATIONS = {
    "idle",
    "listening",
    "listen_pose",
    "thinking",
    "think_pose",
    "talking",
    "talk_explain",
    "talk_excited",
    "talk_smug",
    "talk_angry",
    "talk_sad",
    "talk_surprised",
    "wave",
    "nod",
    "peace",
    "cheer",
    "shrug",
    "bow",
    "confident",
    "shy",
    "smug_pose",
    "refuse",
    "hug_attempt",
    "dance_shikano",
    "backflip",
    "walk",
    "cyber_salute",
    "superhero_landing",
    "martial_arts_guard",
    "double_biceps_flex",
    "facepalm",
    "zen_meditation",
    "point_forward",
    "hands_up_surrender",
    "cyber_dab",
    "rock_on_pose",
    "crouch_fist_raise",
    "crossed_arms_think",
    "hands_on_hips_power",
    "thumbs_up_approval",
    "heart_hands_love",
    "polite_namaste_bow",
    "excited_victory_jump",
    "shy_bashful_tuck",
    "sassy_hip_pop",
    "tired_stretch_yawn",
    "hand_to_heart_sincere",
    "thinking_chin_rest",
    "wave_greeting_friendly",
    "shrug_confused_expressive",
    "idle_popup_curious",
    "idle_orb_curious",
    "idle_screen_curious",
    "idle_waiting_patient",
    "idle_waiting_look",
    "idle_waiting_stretch",
    # Seamless Interaction Dyadic Conversational Dynamics
    "active_listening_nod",
    "thoughtful_gaze_aversion",
    "turn_yield_inquiry",
    "barge_in_alert",
    "tactical_composure",
}

# Default renderer-independent expression & animation per mode/emotion
DEFAULT_EMOTION_EXPRESSION = {
    "neutral": "neutral",
    "happy": "happy",
    "amused": "smirk",
    "curious": "thinking",
    "excited": "happy",
    "concerned": "concerned",
    "serious": "serious",
    "confused": "surprised",
    "relaxed": "relaxed",
}

DEFAULT_MODE_ANIMATION = {
    "idle": "idle",
    "listening": "listening",
    "thinking": "thinking",
    "executing": "thinking",
    "speaking": "talking",
    "error": "idle",
}


@dataclass
class CharacterState:
    """
    Renderer-independent representation of HELIOS's visual/emotional state.
    Core knows WHAT the character feels and is doing, never HOW a renderer draws it.
    """
    mode: str = CharacterMode.IDLE.value
    emotion: str = CharacterEmotion.NEUTRAL.value
    intensity: float = 0.5
    expression: str = "neutral"
    animation: str = "idle"
    movement: str = "stay"
    style: str = CharacterStyle.NATURAL.value
    choreography: List[Dict[str, Any]] = field(default_factory=list)
    custom_pose: Optional[Dict[str, Any]] = None
    speaking: bool = False
    activity: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    @property
    def emotion_intensity(self) -> float:
        return self.intensity

    @emotion_intensity.setter
    def emotion_intensity(self, value: float) -> None:
        self.intensity = max(0.0, min(1.0, float(value)))

    def copy(self) -> "CharacterState":
        return CharacterState(
            mode=self.mode,
            emotion=self.emotion,
            intensity=self.intensity,
            expression=self.expression,
            animation=self.animation,
            movement=self.movement,
            style=self.style,
            choreography=list(self.choreography),
            custom_pose=dict(self.custom_pose) if isinstance(self.custom_pose, dict) else None,
            speaking=self.speaking,
            activity=self.activity,
            timestamp=self.timestamp,
        )

    def to_protocol_dict(self) -> Dict[str, Any]:
        """Serialize into a `character_state` WebSocket protocol message."""
        return {
            "type": "character_state",
            "mode": self.mode,
            "emotion": self.emotion,
            "intensity": round(float(self.intensity), 3),
            "emotion_intensity": round(float(self.intensity), 3),
            "expression": self.expression,
            "animation": self.animation,
            "movement": self.movement,
            "style": self.style,
            "choreography": list(self.choreography),
            "custom_pose": self.custom_pose,
            "speaking": bool(self.speaking),
            "activity": self.activity,
            "timestamp": self.timestamp,
        }


def build_activity_message(activity: Optional[str]) -> Dict[str, Any]:
    """Build a renderer-independent `character_activity` protocol message."""
    return {
        "type": "character_activity",
        "activity": activity,
        "timestamp": time.time(),
    }


def build_speech_message(
    speaking: bool,
    *,
    event: Optional[str] = None,
    text: Optional[str] = None,
    audio_b64: Optional[str] = None,
    mime_type: str = "audio/wav",
    sample_rate: Optional[int] = None,
    duration: Optional[float] = None,
    rms: Optional[List[float]] = None,
    visemes: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build a renderer-independent `character_speech` protocol message."""
    msg: Dict[str, Any] = {
        "type": "character_speech",
        "speaking": bool(speaking),
        "timestamp": time.time(),
    }
    if event is not None:
        msg["event"] = event
    if text is not None:
        msg["text"] = text
    if audio_b64 is not None:
        msg["audio_b64"] = audio_b64
        msg["mime_type"] = mime_type
    if sample_rate is not None:
        msg["sample_rate"] = sample_rate
    if duration is not None:
        msg["duration"] = duration
    if rms is not None:
        msg["rms"] = rms
    if visemes is not None:
        msg["visemes"] = visemes
    return msg


def build_stop_message(reason: str = "interrupted") -> Dict[str, Any]:
    """Build a renderer-independent `character_stop` protocol message."""
    return {
        "type": "character_stop",
        "reason": reason,
        "timestamp": time.time(),
    }
