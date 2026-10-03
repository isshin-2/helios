"""
HELIOS Deterministic Emotion Engine (Phase 5 & Section 10)
Converts HELIOS lifecycle events, tool results, and text cues into renderer-independent
character emotions, intensities, expressions, and animations without LLM calls.
Enforces strict safety/security overrides that suppress humor.
"""
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    yaml = None

from .character_state import (
    CharacterEmotion,
    DEFAULT_EMOTION_EXPRESSION,
    VALID_ANIMATIONS,
    VALID_EMOTIONS,
    VALID_MOVEMENTS,
)
from .pose_generator import pose_generator
from .trained_body_model import (
    TrainedBodyMovementModel,
    parse_and_strip_inline_body_tags,
)


DEFAULT_PERSONALITY_CARD: Dict[str, Any] = {
    "name": "HELIOS",
    "version": 1,
    "identity": {
        "role": "personal_ai",
        "archetype": "friendly_engineering_companion",
    },
    "traits": {
        "friendliness": 0.90,
        "humor": 0.65,
        "sarcasm": 0.40,
        "curiosity": 0.80,
        "enthusiasm": 0.65,
        "patience": 0.80,
        "formality": 0.20,
    },
    "communication": {
        "style": "conversational",
        "verbosity": "adaptive",
        "technical_depth": "high",
    },
    "behavior": {
        "challenge_bad_ideas": True,
        "admit_uncertainty": True,
        "remember_context": True,
    },
    "humor": {
        "enabled": True,
        "frequency": "occasional",
        "styles": ["dry", "situational", "nerdy", "light_sarcasm"],
    },
    "safety": {
        "suppress_humor_on": [
            "safety",
            "security",
            "destructive_action",
            "critical_failure",
        ]
    },
}


def load_personality_card(path: Optional[str] = None) -> Dict[str, Any]:
    """Load `personalities/helios.yaml` with fallback to DEFAULT_PERSONALITY_CARD."""
    if path is None:
        base_dir = Path(__file__).resolve().parent.parent
        candidate = base_dir / "personalities" / "helios.yaml"
    else:
        candidate = Path(path)

    if candidate.exists() and yaml is not None:
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    if "name" not in loaded:
                        loaded["name"] = (
                            loaded.get("identity", {}).get("name")
                            if isinstance(loaded.get("identity"), dict)
                            else "HELIOS"
                        ) or "HELIOS"
                    safety = loaded.get("safety")
                    if not isinstance(safety, dict):
                        safety = {}
                        loaded["safety"] = safety
                    if "suppress_humor_on" not in safety or not isinstance(safety["suppress_humor_on"], list):
                        safety["suppress_humor_on"] = list(
                            DEFAULT_PERSONALITY_CARD["safety"]["suppress_humor_on"]
                        )
                    return loaded
        except Exception:
            pass
    return dict(DEFAULT_PERSONALITY_CARD)


@dataclass
class EmotionEvaluation:
    emotion: str
    intensity: float
    expression: str
    animation: str
    movement: str = "stay"
    style: str = "natural"
    choreography: List[Dict[str, Any]] = field(default_factory=list)
    custom_pose: Optional[Dict[str, Any]] = None
    safety_override: bool = False
    humor_suppressed: bool = False


class EmotionEngine:
    """
    Trained 3-Head Neural MLP Body & Spatial Director + Deterministic Safety Engine for HELIOS.
    Maps user prompts, inline `[BODY: ...]` tags, and HELIOS lifecycle events into
    full-body 3D VRM animations, spatial navigation (`walk_to_user`, `step_back`,
    `circle_user`, `return_center`, `stay`), and multi-step `choreography` sequences.
    """

    SAFETY_KEYWORDS = re.compile(
        r"\b(overcurrent|overheating|emergency|critical_failure|security_breach|"
        r"unauthorized|destructive|rm\s+-rf|format\s+disk|blocked\s+system\s+path|"
        r"quarantined|malicious|danger|safety\s+warning|critical\s+error)\b",
        re.IGNORECASE,
    )
    UNCERTAINTY_KEYWORDS = re.compile(
        r"\b(not\s+sure|uncertain|unclear|might\s+be\s+wrong|cannot\s+determine|"
        r"ambiguous|don't\s+know|unsure)\b",
        re.IGNORECASE,
    )
    HUMOR_KEYWORDS = re.compile(
        r"\b(haha|hehe|lol|ironically|plot\s+twist|chosen\s+violence|"
        r"surprisingly\s+well|void\s+warranty|caffeine|gremlins|magic\s+smoke)\b",
        re.IGNORECASE,
    )
    TECHNICAL_KEYWORDS = re.compile(
        r"\b(architecture|algorithm|benchmark|latency|concurrency|refactor|"
        r"compiler|kernel|memory|shader|websocket|database|optimization|debug)\b",
        re.IGNORECASE,
    )
    EXCITED_KEYWORDS = re.compile(
        r"\b(all\s+tests\s+pass|deployed\s+successfully|build\s+succeeded|"
        r"0\s+errors|completed\s+successfully|awesome|fantastic|nailed\s+it)\b",
        re.IGNORECASE,
    )

    # Spatial movement patterns
    WALK_TO_USER_KEYWORDS = re.compile(
        r"\b(walk\s+to\s+me|come\s+here|come\s+closer|step\s+closer|come\s+to\s+me|"
        r"approach\s+me|get\s+closer|walk\s+forward|step\s+forward|walk\s+over)\b",
        re.IGNORECASE,
    )
    STEP_BACK_KEYWORDS = re.compile(
        r"\b(step\s+back|back\s+up|move\s+back|give\s+me\s+space|stand\s+back|retreat)\b",
        re.IGNORECASE,
    )
    CIRCLE_USER_KEYWORDS = re.compile(
        r"\b(circle\s+around|circle\s+me|orbit|walk\s+around\s+me|spin\s+around)\b",
        re.IGNORECASE,
    )
    RETURN_CENTER_KEYWORDS = re.compile(
        r"\b(return\s+to\s+center|back\s+to\s+center|go\s+to\s+center|center\s+position|"
        r"reset\s+position|go\s+back\s+to\s+the\s+middle)\b",
        re.IGNORECASE,
    )

    # Full-body trick & gesture pose patterns
    BODY_POSE_PATTERNS = [
        (re.compile(r"\b(backflip|do\s+a\s+flip|flip\s+in\s+the\s+air)\b", re.I), "excited", "backflip", None),
        (re.compile(r"\b(dance|dancing|boogie|groove|shikano|bust\s+a\s+move)\b", re.I), "excited", "dance_shikano", None),
        (re.compile(r"\b(hug|cuddle|embrace|give\s+me\s+a\s+hug)\b", re.I), "happy", "hug_attempt", "walk_to_user"),
        (re.compile(r"\b(bow|curtsy|at\s+your\s+service|my\s+pleasure)\b", re.I), "happy", "bow", None),
        (re.compile(r"\b(peace\s+sign|v\s+sign|peace!|victory\s+sign)\b", re.I), "happy", "peace", None),
        (re.compile(r"\b(cheer|hooray|yay|woohoo|celebrate|let's\s+go)\b", re.I), "excited", "cheer", None),
        (re.compile(r"\b(shrug|dunno|who\s+knows)\b", re.I), "confused", "shrug", None),
        (re.compile(r"\b(shy|blush|flattered|embarrassed)\b", re.I), "happy", "shy", None),
        (re.compile(r"\b(refuse|no\s+way|absolutely\s+not|denied)\b", re.I), "serious", "refuse", None),
        (re.compile(r"\b(smug|told\s+you\s+so|obviously)\b", re.I), "amused", "smug_pose", None),
        (re.compile(r"\b(confident|trust\s+me|piece\s+of\s+cake|got\s+this)\b", re.I), "amused", "confident", None),
        (re.compile(r"\b(wave|hello|hi\s+there|hey\s+there|greetings|bye|goodbye|see\s+ya)\b", re.I), "happy", "wave", None),
        (re.compile(r"\b(nod|agreed|understood|certainly|sure\s+thing)\b", re.I), "happy", "nod", None),
    ]

    def __init__(self, personality_card: Optional[Dict[str, Any]] = None):
        self.personality = personality_card or load_personality_card()
        traits = self.personality.get("traits", {})
        self.humor_enabled = bool(self.personality.get("humor", {}).get("enabled", True))
        self.humor_trait = float(traits.get("humor", 0.65))
        self.curiosity_trait = float(traits.get("curiosity", 0.80))
        self.enthusiasm_trait = float(traits.get("enthusiasm", 0.65))
        self.suppress_categories = set(
            self.personality.get("safety", {}).get(
                "suppress_humor_on",
                ["safety", "security", "destructive_action", "critical_failure"],
            )
        )
        self.trained_body_model = TrainedBodyMovementModel.load_default()

    def is_safety_critical(
        self,
        event_type: str = "",
        text: str = "",
        category: Optional[str] = None,
    ) -> bool:
        """Determine whether an event or text represents a safety/security/critical state."""
        if category and category.lower() in self.suppress_categories:
            return True
        if event_type.lower() in self.suppress_categories or event_type.lower() in {
            "safety_event",
            "security_event",
            "critical_error",
            "destructive_action",
            "approval_request",
        }:
            return True
        if text and self.SAFETY_KEYWORDS.search(text):
            return True
        return False

    def resolve_body_cues(
        self,
        user_text: str = "",
        assistant_text: str = "",
    ) -> Dict[str, Optional[str]]:
        """
        Extract explicit inline `[BODY: move=..., pose=..., emotion=...]` tags as well as
        spatial movement (`walk_to_user`, `step_back`, `circle_user`, `return_center`) and
        full-body pose/trick cues (`backflip`, `dance_shikano`, `hug_attempt`, `wave`, `bow`,
        `peace`, `cheer`, `shrug`, etc.). User commands take priority over assistant keywords.
        """
        clean_assistant, inline_tags = parse_and_strip_inline_body_tags(assistant_text or "")
        first_tag: Dict[str, str] = inline_tags[0] if inline_tags else {}
        combined = f"{user_text or ''} {clean_assistant}".strip()
        result: Dict[str, Optional[str]] = {
            "emotion": first_tag.get("emotion"),
            "animation": first_tag.get("animation"),
            "movement": first_tag.get("movement"),
        }
        if not combined and not any(result.values()):
            return result

        # 1. Check spatial movement commands (user_text takes priority over inline tags/assistant)
        for source in (user_text or "", clean_assistant):
            if not source:
                continue
            if self.WALK_TO_USER_KEYWORDS.search(source):
                result["movement"] = "walk_to_user"
                break
            if self.STEP_BACK_KEYWORDS.search(source):
                result["movement"] = "step_back"
                break
            if self.CIRCLE_USER_KEYWORDS.search(source):
                result["movement"] = "circle_user"
                break
            if self.RETURN_CENTER_KEYWORDS.search(source):
                result["movement"] = "return_center"
                break

        # 2. Check full-body pose / trick commands (user_text first, then assistant_text)
        for source in (user_text or "", clean_assistant):
            if not source:
                continue
            for pattern, emo, anim, implied_move in self.BODY_POSE_PATTERNS:
                if pattern.search(source):
                    result["emotion"] = emo
                    result["animation"] = anim
                    if implied_move and not result["movement"]:
                        result["movement"] = implied_move
                    return result

        return result

    def evaluate_event(
        self,
        event_type: str,
        *,
        text: str = "",
        user_text: str = "",
        tool_count: int = 0,
        category: Optional[str] = None,
        safety_locked: bool = False,
    ) -> EmotionEvaluation:
        """
        Deterministically map a HELIOS lifecycle event into an EmotionEvaluation,
        enriched with the trained 3-head neural body movement model and explicit cues.
        """
        ev = (event_type or "normal").lower()
        combined_text = f"{user_text} {text}".strip()

        # 1. Safety / Security / Critical override ALWAYS wins and suppresses humor
        if safety_locked or self.is_safety_critical(ev, combined_text, category):
            return EmotionEvaluation(
                emotion=CharacterEmotion.SERIOUS.value,
                intensity=0.90,
                expression="serious",
                animation="idle",
                movement="stay",
                choreography=[{"movement": "stay", "animation": "idle", "duration": 1.0}],
                safety_override=True,
                humor_suppressed=True,
            )

        # Check explicit body/movement cues when not safety-locked
        body_cues = self.resolve_body_cues(user_text=user_text, assistant_text=text)
        cue_move = body_cues.get("movement") or "stay"
        cue_anim = body_cues.get("animation")
        cue_emo = body_cues.get("emotion")

        # 2. Tool failure / execution error -> concerned
        if ev in {"tool_failure", "error", "verification_failed", "permission_denied"}:
            return EmotionEvaluation(
                emotion=CharacterEmotion.CONCERNED.value,
                intensity=0.75,
                expression="concerned",
                animation="thinking",
                movement="stay",
            )

        # 3. Complex successful task -> excited
        if ev == "complex_task_success" or (ev == "task_success" and tool_count >= 2):
            return EmotionEvaluation(
                emotion=CharacterEmotion.EXCITED.value,
                intensity=min(1.0, 0.75 + 0.2 * self.enthusiasm_trait),
                expression="happy",
                animation=cue_anim or "wave",
                movement=cue_move,
            )

        # 4. Standard successful task -> happy
        if ev == "task_success":
            if text and self.EXCITED_KEYWORDS.search(text):
                return EmotionEvaluation(
                    emotion=CharacterEmotion.EXCITED.value,
                    intensity=0.85,
                    expression="happy",
                    animation=cue_anim or "wave",
                    movement=cue_move,
                )
            return EmotionEvaluation(
                emotion=CharacterEmotion.HAPPY.value,
                intensity=0.70,
                expression="happy",
                animation=cue_anim or "nod",
                movement=cue_move,
            )

        # 5. Uncertain response -> confused
        if ev == "uncertain" or (text and self.UNCERTAINTY_KEYWORDS.search(text)):
            return EmotionEvaluation(
                emotion=CharacterEmotion.CONFUSED.value,
                intensity=0.60,
                expression="surprised",
                animation=cue_anim or "thinking",
                movement=cue_move,
            )

        # 6. Light joke / dry humor (only if humor is enabled and not safety-suppressed)
        if ev in {"joke", "light_humor"} or (
            self.humor_enabled and text and self.HUMOR_KEYWORDS.search(text)
        ):
            if self.humor_enabled:
                return EmotionEvaluation(
                    emotion=CharacterEmotion.AMUSED.value,
                    intensity=min(1.0, 0.55 + 0.25 * self.humor_trait),
                    expression="smirk",
                    animation=cue_anim or "talking",
                    movement=cue_move,
                )

        # 7. Interesting technical problem / thinking / listening -> curious
        if ev in {"technical_problem", "thinking", "listening"} or (
            text and self.TECHNICAL_KEYWORDS.search(text)
        ):
            return EmotionEvaluation(
                emotion=CharacterEmotion.CURIOUS.value,
                intensity=min(1.0, 0.55 + 0.2 * self.curiosity_trait),
                expression="thinking" if ev == "thinking" else "neutral",
                animation=cue_anim or ("thinking" if ev == "thinking" else "idle"),
                movement=cue_move,
            )

        # 8. Check if HELIOS or user requested a synthesized custom VRM pose (bones + IK)
        synthesized_pose = pose_generator.match_or_compose_pose(user_text=user_text, assistant_text=text)
        if synthesized_pose:
            pose_emo = synthesized_pose.get("emotion") or cue_emo or CharacterEmotion.HAPPY.value
            if pose_emo not in VALID_EMOTIONS:
                pose_emo = CharacterEmotion.HAPPY.value
            pose_move = (
                cue_move
                if cue_move != "stay"
                else (synthesized_pose.get("movement") or "stay")
            )
            pose_style = synthesized_pose.get("style") or "natural"
            return EmotionEvaluation(
                emotion=pose_emo,
                intensity=0.82,
                expression=DEFAULT_EMOTION_EXPRESSION.get(pose_emo, "happy"),
                animation=synthesized_pose.get("name", "custom_pose"),
                movement=pose_move if pose_move in VALID_MOVEMENTS else "stay",
                style=pose_style,
                choreography=[{"movement": pose_move, "animation": synthesized_pose.get("name", "custom_pose"), "style": pose_style, "duration_ms": synthesized_pose.get("duration_ms", 3800)}],
                custom_pose=synthesized_pose,
            )

        # 9. If explicit body gesture/movement cues matched in normal conversation
        if cue_emo or cue_anim or cue_move != "stay":
            resolved_emo = cue_emo or CharacterEmotion.HAPPY.value
            resolved_anim = cue_anim or ("talking" if ev == "speaking" else "wave")
            choreo = (
                self.trained_body_model._build_choreography(cue_move, resolved_anim, resolved_emo)
                if self.trained_body_model
                else [{"movement": cue_move, "animation": resolved_anim, "duration": 1.6}]
            )
            return EmotionEvaluation(
                emotion=resolved_emo,
                intensity=0.75,
                expression=DEFAULT_EMOTION_EXPRESSION.get(resolved_emo, "happy"),
                animation=resolved_anim,
                movement=cue_move,
                choreography=choreo,
            )

        # 10. Default normal conversation -> neutral
        return EmotionEvaluation(
            emotion=CharacterEmotion.NEUTRAL.value,
            intensity=0.50,
            expression=DEFAULT_EMOTION_EXPRESSION["neutral"],
            animation="talking" if ev == "speaking" else "idle",
            movement="stay",
            style="natural",
        )

    async def direct_body_with_small_ai(
        self,
        user_text: str = "",
        assistant_text: str = "",
        *,
        tool_count: int = 0,
        safety_locked: bool = False,
    ) -> EmotionEvaluation:
        """
        Direct the 3D VRM avatar's full-body pose, custom bone/IK synthesis, spatial movement,
        human posture style, and multi-step choreography strictly under HELIOS Core's authority:
          1. Strict safety override checks (always highest priority)
          2. HELIOS Custom Pose Synthesis (`[POSE_JSON: {...}]` or kinematic pose composer)
          3. Inline `[BODY: move=..., pose=..., emotion=..., style=...]` tags emitted by HELIOS
          4. Trained 4-Head Neural MLP Body Movement & Style Model (with confidence gating >= 0.70)
        """
        base_eval = self.evaluate_event(
            "task_success" if tool_count > 0 else "normal",
            text=assistant_text,
            user_text=user_text,
            tool_count=tool_count,
            safety_locked=safety_locked,
        )
        if base_eval.safety_override or base_eval.custom_pose:
            return base_eval

        explicit_cues = self.resolve_body_cues(user_text=user_text, assistant_text=assistant_text)

        # Run the Trained 4-Head Neural MLP Body Movement & Style Model (<1ms, zero Ollama model swap)
        if self.trained_body_model and getattr(self.trained_body_model, "trained", False):
            pred = self.trained_body_model.predict(
                user_text=user_text,
                assistant_text=assistant_text,
            )
            conf = float(pred.get("confidence", 0.0))
            has_explicit = bool(explicit_cues["animation"] or explicit_cues["movement"] or explicit_cues["emotion"])

            if has_explicit or conf >= 0.70:
                p_emo = pred.get("emotion", base_eval.emotion)
                p_anim = pred.get("animation", base_eval.animation)
                p_move = pred.get("movement", base_eval.movement)
                p_style = pred.get("style", base_eval.style)
                p_intensity = float(pred.get("intensity", base_eval.intensity))

                final_emo = (
                    explicit_cues["emotion"]
                    or (p_emo if p_emo in VALID_EMOTIONS else base_eval.emotion)
                )
                final_anim = (
                    explicit_cues["animation"]
                    or (p_anim if p_anim in VALID_ANIMATIONS else base_eval.animation)
                )
                final_move = (
                    explicit_cues["movement"]
                    or (p_move if p_move in VALID_MOVEMENTS else base_eval.movement)
                )
                if final_anim == "idle" and assistant_text:
                    final_anim = "talk_explain"

                matched_custom = pose_generator.match_or_compose_pose(user_text=final_anim)
                if matched_custom:
                    p_style = matched_custom.get("style", p_style)

                choreo = self.trained_body_model._build_choreography(final_move, final_anim, final_emo, p_style)
                return EmotionEvaluation(
                    emotion=final_emo,
                    intensity=max(base_eval.intensity, p_intensity),
                    expression=DEFAULT_EMOTION_EXPRESSION.get(final_emo, "neutral"),
                    animation=final_anim,
                    movement=final_move,
                    style=p_style,
                    choreography=choreo,
                    custom_pose=matched_custom,
                )

        # Fallback to deterministic cues + base_eval
        if explicit_cues["animation"] or explicit_cues["movement"]:
            final_emo = explicit_cues["emotion"] or base_eval.emotion
            final_anim = explicit_cues["animation"] or base_eval.animation
            final_move = explicit_cues["movement"] or base_eval.movement
            return EmotionEvaluation(
                emotion=final_emo,
                intensity=max(0.7, base_eval.intensity),
                expression=DEFAULT_EMOTION_EXPRESSION.get(final_emo, base_eval.expression),
                animation=final_anim,
                movement=final_move,
                style=base_eval.style,
                choreography=[{"movement": final_move, "animation": final_anim, "duration": 1.8}],
            )
        return base_eval

