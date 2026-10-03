"""
HELIOS Character Manager & Null Adapter (Phases 2, 3, 7, 8, 10)
Bridges HELIOS EventBus, ConversationOrchestrator, and VoiceManager into the
renderer-independent Character Protocol without coupling HELIOS core intelligence
to any specific avatar renderer.
"""
import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Optional, Set

import config
from .character_models import CharacterModelRegistry
from .character_state import (
    CharacterEmotion,
    CharacterMode,
    CharacterState,
    DEFAULT_EMOTION_EXPRESSION,
    DEFAULT_MODE_ANIMATION,
    VALID_ANIMATIONS,
    VALID_EMOTIONS,
    VALID_MODES,
    VALID_MOVEMENTS,
    VALID_STYLES,
    build_activity_message,
    build_speech_message,
    build_stop_message,
)
from .emotion_engine import EmotionEngine, load_personality_card
from .events import EventBus, global_bus

logger = logging.getLogger(__name__)

# Friendly user-facing descriptions for tools (never exposes internal args/secrets)
TOOL_ACTIVITY_LABELS: Dict[str, str] = {
    "file_reader": "Reading project files",
    "FileReaderTool": "Reading project files",
    "file_writer": "Writing project files",
    "FileWriterTool": "Writing project files",
    "file_patch": "Applying code patch",
    "directory_lister": "Analyzing project files",
    "DirectoryListerTool": "Analyzing project files",
    "repo_map": "Mapping repository structure",
    "terminal": "Running terminal command",
    "stateful_shell": "Executing shell command",
    "repl": "Running Python REPL",
    "web_search": "Searching the web",
    "browser_tool": "Browsing web page",
    "screen_vision": "Analyzing screen layout",
    "computer_control": "Controlling desktop UI",
    "som_overlay": "Highlighting UI elements",
    "github_tool": "Querying GitHub repository",
    "google_drive_tool": "Accessing Google Drive",
    "llmfit": "Checking hardware model compatibility",
    "self_modification": "Testing sandboxed code experiment",
}


def sanitize_activity_text(raw_text: Optional[str]) -> Optional[str]:
    """
    Strip chain-of-thought (<think>...</think>), JSON blobs, and internal tags
    so only clean, user-facing activity labels are sent to the character protocol.
    """
    if not raw_text:
        return None
    text = str(raw_text)
    # Never expose <think> blocks or chain-of-thought
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    if "<think>" in text.lower():
        text = text.split("<think>")[0]
    # Never expose raw JSON structures
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"\{.*\}", "", text, flags=re.DOTALL)
    # Convert "[System] Running tool X..." into clean user-facing activity
    m = re.search(r"Running tool\s+([A-Za-z0-9_:-]+)", text, re.IGNORECASE)
    if m:
        tool_name = m.group(1)
        if "__" in tool_name:
            _, short_name = tool_name.split("__", 1)
            return f"Running MCP tool: {short_name.replace('_', ' ')}"
        return TOOL_ACTIVITY_LABELS.get(
            tool_name, f"Running {tool_name.replace('_', ' ')}"
        )
    # Strip leading emoji / brackets
    text = re.sub(r"^\[System\]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^[^\w\s]+\s*", "", text).strip()
    if not text or len(text) > 120:
        return None
    return text


class NullCharacterAdapter:
    """
    No-op adapter used when CHARACTER_ENABLED=false or character is disabled.
    Guarantees zero character overhead and zero external process dependency.
    """

    enabled: bool = False

    def enable(self) -> None:
        pass

    def disable(self) -> None:
        pass

    async def set_state(self, *args, **kwargs) -> Optional[Dict[str, Any]]:
        return None

    async def set_emotion(self, *args, **kwargs) -> Optional[Dict[str, Any]]:
        return None

    async def set_expression(self, *args, **kwargs) -> Optional[Dict[str, Any]]:
        return None

    async def set_animation(self, *args, **kwargs) -> Optional[Dict[str, Any]]:
        return None

    async def set_movement(self, *args, **kwargs) -> Optional[Dict[str, Any]]:
        return None

    async def direct_turn_body(self, *args, **kwargs) -> Optional[Dict[str, Any]]:
        return None

    async def start_speaking(self, *args, **kwargs) -> Optional[Dict[str, Any]]:
        return None

    async def stop_speaking(self, *args, **kwargs) -> Optional[Dict[str, Any]]:
        return None

    async def publish_protocol(self, payload: Dict[str, Any]) -> None:
        return None

    async def shutdown(self) -> None:
        pass


class ActiveCharacterAdapter:
    """
    Active adapter that publishes Character Protocol messages to the EventBus
    and any connected WebSocket character renderers.
    """

    enabled: bool = True

    def __init__(self, manager: "CharacterManager"):
        self.manager = manager

    async def publish_protocol(self, payload: Dict[str, Any]) -> None:
        await self.manager._dispatch_protocol_message(payload)


class CharacterManager:
    """
    Central coordinator for the optional HELIOS Character presentation layer.
    Owns the authoritative `CharacterState`, delegates emotion resolution to
    `EmotionEngine`, and broadcasts renderer-independent protocol events.
    """

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        enabled: Optional[bool] = None,
        renderer: Optional[str] = None,
        model_id: Optional[str] = None,
    ):
        self.bus = event_bus or global_bus
        self.null_adapter = NullCharacterAdapter()
        self.active_adapter = ActiveCharacterAdapter(self)

        is_enabled = (
            enabled
            if enabled is not None
            else bool(getattr(config, "CHARACTER_ENABLED", True))
        )
        self.renderer = renderer or getattr(config, "CHARACTER_RENDERER", "vrm")
        self.model_id = model_id or getattr(config, "CHARACTER_MODEL", "helios-v1")

        self.model_registry = CharacterModelRegistry()
        self.personality = load_personality_card()
        self.emotion_engine = EmotionEngine(self.personality)

        self.state = CharacterState()
        self.safety_locked: bool = False
        self._turn_tool_count: int = 0
        self._turn_had_error: bool = False
        self._turn_text_accum: str = ""
        self._turn_user_text: str = ""
        self._clients: Set[Any] = set()
        self.history: List[Dict[str, Any]] = []

        self._enabled = False
        self._subscribed_buses: Set[int] = set()

        if is_enabled:
            self.enable()
        else:
            self.disable()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def adapter(self):
        return self.active_adapter if self._enabled else self.null_adapter

    def enable(self) -> None:
        """Enable character state tracking and EventBus subscriptions."""
        self._enabled = True
        self.attach_event_bus(self.bus)
        logger.info(
            f"[CharacterManager] Enabled (renderer={self.renderer}, model={self.model_id})"
        )

    def disable(self) -> None:
        """Disable character subsystem and switch to NullCharacterAdapter."""
        self._enabled = False
        self.state = CharacterState()
        self.safety_locked = False
        logger.info("[CharacterManager] Disabled (using NullCharacterAdapter)")

    def attach_event_bus(self, bus: Optional[EventBus]) -> None:
        """Subscribe to a HELIOS EventBus (global or request-local)."""
        if bus is None or id(bus) in self._subscribed_buses:
            return
        self._subscribed_buses.add(id(bus))
        bus.subscribe("ui_state", self._on_ui_state)
        bus.subscribe("status", self._on_status)
        bus.subscribe("chunk", self._on_chunk)
        bus.subscribe("done", self._on_done)
        bus.subscribe("approval_request", self._on_approval_request)
        bus.subscribe("tool_start", self._on_tool_start)
        bus.subscribe("tool_complete", self._on_tool_complete)
        bus.subscribe("tool_error", self._on_tool_error)
        bus.subscribe("safety_event", self._on_safety_event)
        bus.subscribe("speech_started", self._on_speech_started)
        bus.subscribe("audio_chunk", self._on_audio_chunk)
        bus.subscribe("speech_finished", self._on_speech_finished)
        bus.subscribe("speech_interrupted", self._on_speech_interrupted)

    # ── WebSocket Client Management (Process Isolation & Reconnection) ──────

    async def register_client(self, websocket: Any) -> Dict[str, Any]:
        """Register a connected character renderer process and send current state."""
        self._clients.add(websocket)
        sync = self.get_sync_payload()
        if self._enabled:
            try:
                await websocket.send_json(sync)
                await websocket.send_json(self.state.to_protocol_dict())
            except Exception:
                self._clients.discard(websocket)
        return sync

    def unregister_client(self, websocket: Any) -> None:
        """Remove a disconnected character renderer without affecting HELIOS."""
        self._clients.discard(websocket)

    def get_sync_payload(self) -> Dict[str, Any]:
        """Return full synchronization snapshot for reconnecting character processes."""
        return {
            "type": "character_sync",
            "enabled": self._enabled,
            "renderer": self.renderer,
            "model": self.model_registry.get_manifest(self.model_id),
            "personality": {
                "name": self.personality.get("name", "HELIOS"),
                "archetype": self.personality.get("identity", {}).get(
                    "archetype", "friendly_engineering_companion"
                ),
                "traits": self.personality.get("traits", {}),
            },
            "state": self.state.to_protocol_dict(),
        }

    async def _dispatch_protocol_message(self, payload: Dict[str, Any]) -> None:
        if not self._enabled:
            return
        self.history.append(payload)
        if len(self.history) > 100:
            self.history = self.history[-100:]

        # Publish on global_bus so standard /ws listeners can also observe character events
        try:
            await self.bus.publish(payload["type"], payload)
        except Exception as e:
            logger.debug(f"[CharacterManager] Bus publish warning: {e}")

        # Broadcast to dedicated character WebSocket processes (fault-isolated)
        dead_clients = []
        for ws in list(self._clients):
            try:
                await ws.send_json(payload)
            except Exception:
                dead_clients.append(ws)
        for ws in dead_clients:
            self._clients.discard(ws)

    # ── Core State Mutators (Section 6) ─────────────────────────────────────

    async def set_state(
        self,
        mode: str,
        *,
        emotion: Optional[str] = None,
        intensity: Optional[float] = None,
        expression: Optional[str] = None,
        animation: Optional[str] = None,
        movement: Optional[str] = None,
        style: Optional[str] = None,
        choreography: Optional[List[Dict[str, Any]]] = None,
        custom_pose: Optional[Dict[str, Any]] = None,
        speaking: Optional[bool] = None,
        activity: Optional[str] = "__UNSET__",
    ) -> Optional[Dict[str, Any]]:
        if not self._enabled:
            return await self.null_adapter.set_state()

        clean_mode = mode if mode in VALID_MODES else CharacterMode.IDLE.value
        self.state.mode = clean_mode

        if emotion is not None:
            await self.set_emotion(emotion, intensity=intensity, broadcast=False)
        elif intensity is not None:
            self.state.intensity = max(0.0, min(1.0, float(intensity)))

        if expression is not None:
            self.state.expression = (
                "serious"
                if (self.safety_locked and expression in {"smirk", "happy", "amused"})
                else expression
            )
        else:
            self.state.expression = DEFAULT_EMOTION_EXPRESSION.get(
                self.state.emotion, "neutral"
            )

        if animation is not None:
            self.state.animation = animation
        else:
            self.state.animation = DEFAULT_MODE_ANIMATION.get(clean_mode, "idle")

        if movement is not None:
            clean_move = movement.lower()
            self.state.movement = (
                "stay"
                if self.safety_locked
                else (clean_move if clean_move in VALID_MOVEMENTS else "stay")
            )
        elif clean_mode in (CharacterMode.LISTENING.value, CharacterMode.THINKING.value, CharacterMode.ERROR.value):
            self.state.movement = "stay"

        if style is not None:
            clean_style = str(style).lower()
            self.state.style = "natural" if self.safety_locked else (clean_style if clean_style in VALID_STYLES else "natural")
        elif isinstance(custom_pose, dict) and custom_pose.get("style") in VALID_STYLES:
            self.state.style = "natural" if self.safety_locked else custom_pose["style"]

        if choreography is not None:
            self.state.choreography = (
                [{"movement": "stay", "animation": "idle", "duration": 1.0}]
                if self.safety_locked
                else list(choreography)
            )
        else:
            self.state.choreography = []

        self.state.custom_pose = None if self.safety_locked else custom_pose

        if speaking is not None:
            self.state.speaking = bool(speaking)
        else:
            self.state.speaking = clean_mode == CharacterMode.SPEAKING.value

        if activity != "__UNSET__":
            self.state.activity = sanitize_activity_text(activity)

        self.state.timestamp = time.time()
        msg = self.state.to_protocol_dict()
        await self.adapter.publish_protocol(msg)
        return msg

    async def set_emotion(
        self,
        emotion: str,
        intensity: Optional[float] = None,
        *,
        safety_critical: bool = False,
        broadcast: bool = True,
    ) -> Optional[Dict[str, Any]]:
        if not self._enabled:
            return await self.null_adapter.set_emotion()

        if safety_critical:
            self.safety_locked = True

        # Section 10 & Test 5: Humorous/playful emotions cannot override serious safety state
        requested = (emotion or "neutral").lower()
        if self.safety_locked and requested in {
            CharacterEmotion.AMUSED.value,
            CharacterEmotion.HAPPY.value,
            CharacterEmotion.EXCITED.value,
        }:
            requested = CharacterEmotion.SERIOUS.value

        if requested not in VALID_EMOTIONS:
            requested = CharacterEmotion.NEUTRAL.value

        self.state.emotion = requested
        if intensity is not None:
            self.state.intensity = max(0.0, min(1.0, float(intensity)))
        self.state.expression = DEFAULT_EMOTION_EXPRESSION.get(requested, "neutral")
        self.state.timestamp = time.time()

        if broadcast:
            msg = self.state.to_protocol_dict()
            await self.adapter.publish_protocol(msg)
            return msg
        return None

    async def set_expression(self, expression: str) -> Optional[Dict[str, Any]]:
        if not self._enabled:
            return await self.null_adapter.set_expression()
        if self.safety_locked and expression in {"smirk", "happy", "amused"}:
            expression = "serious"
        self.state.expression = expression
        self.state.timestamp = time.time()
        msg = self.state.to_protocol_dict()
        await self.adapter.publish_protocol(msg)
        return msg

    async def set_animation(self, animation: str) -> Optional[Dict[str, Any]]:
        if not self._enabled:
            return await self.null_adapter.set_animation()
        self.state.animation = animation
        self.state.timestamp = time.time()
        msg = self.state.to_protocol_dict()
        await self.adapter.publish_protocol(msg)
        return msg

    async def set_movement(self, movement: str) -> Optional[Dict[str, Any]]:
        if not self._enabled:
            return await self.null_adapter.set_movement()
        clean_move = (movement or "stay").lower()
        self.state.movement = (
            "stay"
            if self.safety_locked
            else (clean_move if clean_move in VALID_MOVEMENTS else "stay")
        )
        self.state.timestamp = time.time()
        msg = self.state.to_protocol_dict()
        await self.adapter.publish_protocol(msg)
        return msg

    def set_user_turn_text(self, user_text: str) -> None:
        """Record the active user message so body & spatial cues can be resolved."""
        self._turn_user_text = str(user_text or "").strip()

    async def direct_turn_body(
        self,
        user_text: str = "",
        assistant_text: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Invoke HELIOS Core's Pose Synthesizer + Trained 4-Head Neural MLP Body Director
        to move the character's 3D body, synthesize custom bone/IK poses, and execute
        multi-step choreography strictly under HELIOS's control.
        """
        if not self._enabled:
            return await self.null_adapter.direct_turn_body()

        u_text = user_text or self._turn_user_text
        a_text = assistant_text or self._turn_text_accum

        eval_res = await self.emotion_engine.direct_body_with_small_ai(
            user_text=u_text,
            assistant_text=a_text,
            tool_count=self._turn_tool_count,
            safety_locked=self.safety_locked,
        )
        if self.safety_locked:
            return await self.set_state(
                self.state.mode,
                emotion=CharacterEmotion.SERIOUS.value,
                intensity=0.9,
                expression="serious",
                animation="idle",
                movement="stay",
                style="natural",
                choreography=[{"movement": "stay", "animation": "idle", "duration": 1.0}],
                custom_pose=None,
                speaking=self.state.speaking,
                activity=None,
            )

        return await self.set_state(
            self.state.mode,
            emotion=eval_res.emotion,
            intensity=eval_res.intensity,
            expression=eval_res.expression,
            animation=eval_res.animation,
            movement=eval_res.movement,
            style=getattr(eval_res, "style", "natural"),
            choreography=eval_res.choreography,
            custom_pose=eval_res.custom_pose,
            speaking=self.state.speaking,
            activity=None,
        )

    async def generate_custom_pose(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Have HELIOS Core synthesize a brand-new 3D VRM pose (normalized humanoid bones + 2-Bone IK)
        and immediately broadcast it to the character renderer.
        """
        if not self._enabled:
            return None
        from .pose_generator import pose_generator

        ollama_host = getattr(config, "OLLAMA_HOST", "http://127.0.0.1:11434")
        synthesized = await pose_generator.synthesize_pose_with_llm(prompt, ollama_host=ollama_host)
        emo = synthesized.get("emotion", "happy")
        move = synthesized.get("movement", "stay")
        style = synthesized.get("style", "natural")
        return await self.set_state(
            self.state.mode,
            emotion=emo,
            intensity=0.85,
            expression=DEFAULT_EMOTION_EXPRESSION.get(emo, "happy"),
            animation=synthesized.get("name", "custom_pose"),
            movement=move,
            style=style,
            choreography=[{"movement": move, "animation": synthesized.get("name", "custom_pose"), "duration_ms": synthesized.get("duration_ms", 4000)}],
            custom_pose=synthesized,
            speaking=self.state.speaking,
            activity=None,
        )

    async def train_rl_pose(
        self,
        pose_name: str = "all",
        episodes: int = 20,
        simulate_curriculum: bool = True,
    ) -> Dict[str, Any]:
        """
        Train HELIOS Core's RL Human-Reference Pose Policy Network on one or all
        human reference poses, and broadcast the trained 3D pose (with curriculum
        keyframes) to the 3D VRM character viewer.
        """
        from .rl_pose_trainer import rl_pose_trainer

        train_res = rl_pose_trainer.train_episodes(
            pose_name=pose_name or "all",
            episodes=max(1, min(120, int(episodes))),
            simulate_curriculum=bool(simulate_curriculum),
        )
        trained_pose = train_res.get("trained_pose")
        if self._enabled and isinstance(trained_pose, dict):
            emo = trained_pose.get("emotion", "happy")
            move = trained_pose.get("movement", "stay")
            style = trained_pose.get("style", "natural")
            await self.set_state(
                self.state.mode,
                emotion=emo,
                intensity=0.90,
                expression=DEFAULT_EMOTION_EXPRESSION.get(emo, "happy"),
                animation=trained_pose.get("name", "custom_pose"),
                movement=move,
                style=style,
                choreography=[
                    {
                        "movement": move,
                        "animation": trained_pose.get("name", "custom_pose"),
                        "duration_ms": trained_pose.get("duration_ms", 4200),
                    }
                ],
                custom_pose=trained_pose,
                speaking=self.state.speaking,
                activity=None,
            )
        return train_res

    async def apply_rl_pose_feedback(
        self,
        pose_name: str,
        user_award_delta: float = 100.0,
        browser_telemetry: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Apply online Reinforcement Learning reward (+100 pts) or penalty (-50 pts)
        plus live 3D VRM browser bone telemetry to update the policy network.
        """
        from .rl_pose_trainer import rl_pose_trainer

        candidate_pose = self.state.custom_pose
        res = rl_pose_trainer.record_online_feedback(
            pose_name=pose_name or (candidate_pose.get("name") if isinstance(candidate_pose, dict) else "cyber_salute"),
            candidate_pose=candidate_pose if isinstance(candidate_pose, dict) else None,
            user_award_delta=float(user_award_delta),
            browser_telemetry=browser_telemetry,
        )
        refined_pose = res.get("refined_pose")
        if self._enabled and isinstance(refined_pose, dict):
            emo = refined_pose.get("emotion", self.state.emotion)
            move = refined_pose.get("movement", "stay")
            style = refined_pose.get("style", self.state.style)
            await self.set_state(
                self.state.mode,
                emotion=emo,
                intensity=0.90,
                expression=DEFAULT_EMOTION_EXPRESSION.get(emo, "happy"),
                animation=refined_pose.get("name", "custom_pose"),
                movement=move,
                style=style,
                choreography=[
                    {
                        "movement": move,
                        "animation": refined_pose.get("name", "custom_pose"),
                        "duration_ms": refined_pose.get("duration_ms", 4000),
                    }
                ],
                custom_pose=refined_pose,
                speaking=self.state.speaking,
                activity=None,
            )
        return res

    def get_rl_status(self) -> Dict[str, Any]:
        """Return RL policy status, reward breakdown across all 24 human reference poses, and award counters."""
        from .rl_pose_trainer import rl_pose_trainer

        return rl_pose_trainer.get_status()

    async def set_activity(self, activity: Optional[str]) -> Optional[Dict[str, Any]]:
        if not self._enabled:
            return None
        clean = sanitize_activity_text(activity)
        self.state.activity = clean
        msg = build_activity_message(clean)
        await self.adapter.publish_protocol(msg)
        return msg

    async def start_speaking(
        self,
        text: Optional[str] = None,
        *,
        audio_b64: Optional[str] = None,
        mime_type: str = "audio/wav",
        sample_rate: Optional[int] = None,
        duration: Optional[float] = None,
        rms: Optional[List[float]] = None,
        visemes: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not self._enabled:
            return await self.null_adapter.start_speaking()

        # Evaluate text emotion if not already locked by safety or error
        if text and not self.safety_locked and not self._turn_had_error:
            eval_res = self.emotion_engine.evaluate_event(
                "speaking", text=text, safety_locked=self.safety_locked
            )
            if eval_res.emotion != CharacterEmotion.NEUTRAL.value:
                self.state.emotion = eval_res.emotion
                self.state.intensity = eval_res.intensity
                self.state.expression = eval_res.expression

        keep_custom = self.state.custom_pose
        keep_anim = (
            self.state.animation
            if (
                keep_custom
                or (
                    self.state.animation
                    and self.state.animation not in ("idle", "thinking", "listening")
                )
            )
            else "talking"
        )
        await self.set_state(
            CharacterMode.SPEAKING.value,
            speaking=True,
            animation=keep_anim,
            movement=self.state.movement,
            choreography=self.state.choreography if self.state.choreography else None,
            custom_pose=keep_custom,
            activity=None,
        )
        speech_msg = build_speech_message(
            True,
            event="speech_started",
            text=text,
            audio_b64=audio_b64,
            mime_type=mime_type,
            sample_rate=sample_rate,
            duration=duration,
            rms=rms,
            visemes=visemes,
        )
        await self.adapter.publish_protocol(speech_msg)
        return speech_msg

    async def stop_speaking(
        self, *, interrupted: bool = False
    ) -> Optional[Dict[str, Any]]:
        if not self._enabled:
            return await self.null_adapter.stop_speaking()

        self.state.speaking = False
        if interrupted:
            stop_msg = build_stop_message(reason="speech_interrupted")
            await self.adapter.publish_protocol(stop_msg)
            speech_msg = build_speech_message(False, event="speech_interrupted")
            await self.adapter.publish_protocol(speech_msg)
            await self.set_state(
                CharacterMode.IDLE.value,
                speaking=False,
                animation="idle",
                activity=None,
            )
            return stop_msg

        speech_msg = build_speech_message(False, event="speech_finished")
        await self.adapter.publish_protocol(speech_msg)
        await self.set_state(
            CharacterMode.IDLE.value,
            speaking=False,
            animation="idle",
            activity=None,
        )
        return speech_msg

    async def shutdown(self) -> None:
        if not self._enabled:
            return await self.null_adapter.shutdown()
        self._clients.clear()
        self._enabled = False

    # ── EventBus Subscribers (Section 7 Mapping) ────────────────────────────

    async def _on_ui_state(self, data: Any) -> None:
        if not self._enabled:
            return
        state_str = str(data).lower() if data else ""
        if state_str == "listening":
            self.safety_locked = False
            self._turn_tool_count = 0
            self._turn_had_error = False
            self._turn_text_accum = ""
            await self.set_state(
                CharacterMode.LISTENING.value,
                emotion=CharacterEmotion.CURIOUS.value,
                intensity=0.6,
                expression="neutral",
                animation="listening",
                speaking=False,
                activity=None,
            )
        elif state_str == "thinking":
            await self.set_state(
                CharacterMode.THINKING.value,
                emotion=CharacterEmotion.CURIOUS.value,
                intensity=0.65,
                expression="thinking",
                animation="thinking",
                speaking=False,
            )
        elif state_str == "speaking":
            if self.state.mode != CharacterMode.SPEAKING.value:
                await self.start_speaking()
        elif state_str == "idle":
            if self.state.speaking:
                await self.stop_speaking(interrupted=False)
            else:
                await self.set_state(
                    CharacterMode.IDLE.value,
                    speaking=False,
                    animation="idle",
                    activity=None,
                )

    async def _on_status(self, data: Any) -> None:
        if not self._enabled or not isinstance(data, str):
            return
        text = data.strip()
        if "Analyzing your request" in text:
            # Start of a new user turn
            self.safety_locked = False
            self._turn_tool_count = 0
            self._turn_had_error = False
            self._turn_text_accum = ""
            await self.set_state(
                CharacterMode.THINKING.value,
                emotion=CharacterEmotion.CURIOUS.value,
                intensity=0.6,
                expression="thinking",
                animation="thinking",
                speaking=False,
                activity="Analyzing request",
            )
        elif "Generating response" in text:
            await self.set_state(
                CharacterMode.THINKING.value,
                emotion=(
                    CharacterEmotion.SERIOUS.value
                    if self.safety_locked
                    else (
                        CharacterEmotion.CONCERNED.value
                        if self._turn_had_error
                        else CharacterEmotion.CURIOUS.value
                    )
                ),
                intensity=0.65,
                expression=(
                    "serious"
                    if self.safety_locked
                    else ("concerned" if self._turn_had_error else "thinking")
                ),
                animation="thinking",
                speaking=False,
                activity=None,
            )
        elif "Running tool" in text:
            self._turn_tool_count += 1
            clean_act = sanitize_activity_text(text)
            await self.set_state(
                CharacterMode.EXECUTING.value,
                emotion=(
                    CharacterEmotion.SERIOUS.value
                    if self.safety_locked
                    else CharacterEmotion.CURIOUS.value
                ),
                intensity=0.7,
                expression="serious" if self.safety_locked else "thinking",
                animation="thinking",
                speaking=False,
                activity=clean_act,
            )
            await self.set_activity(clean_act)

    async def _on_tool_start(self, data: Any) -> None:
        if not self._enabled:
            return
        self._turn_tool_count += 1
        tool_name = data.get("tool", "tool") if isinstance(data, dict) else str(data)
        activity = TOOL_ACTIVITY_LABELS.get(
            tool_name, f"Running {tool_name.replace('_', ' ')}"
        )
        await self.set_state(
            CharacterMode.EXECUTING.value,
            emotion=(
                CharacterEmotion.SERIOUS.value
                if self.safety_locked
                else CharacterEmotion.CURIOUS.value
            ),
            intensity=0.7,
            expression="serious" if self.safety_locked else "thinking",
            animation="thinking",
            speaking=False,
            activity=activity,
        )
        await self.set_activity(activity)

    async def _on_tool_complete(self, data: Any) -> None:
        if not self._enabled:
            return
        eval_res = self.emotion_engine.evaluate_event(
            "task_success",
            tool_count=self._turn_tool_count,
            safety_locked=self.safety_locked,
        )
        await self.set_emotion(eval_res.emotion, eval_res.intensity)
        await self.set_activity(None)

    async def _on_tool_error(self, data: Any) -> None:
        if not self._enabled:
            return
        self._turn_had_error = True
        err_text = data.get("error", "") if isinstance(data, dict) else str(data or "")
        eval_res = self.emotion_engine.evaluate_event(
            "tool_failure", text=err_text, safety_locked=self.safety_locked
        )
        await self.set_state(
            CharacterMode.ERROR.value,
            emotion=eval_res.emotion,
            intensity=eval_res.intensity,
            expression=eval_res.expression,
            animation=eval_res.animation,
            speaking=False,
            activity=None,
        )

    async def _on_approval_request(self, data: Any) -> None:
        """Destructive or sensitive operation requires approval -> serious state."""
        if not self._enabled:
            return
        self.safety_locked = True
        op = data.get("operation", "operation") if isinstance(data, dict) else "action"
        await self.set_state(
            CharacterMode.EXECUTING.value,
            emotion=CharacterEmotion.SERIOUS.value,
            intensity=0.9,
            expression="serious",
            animation="idle",
            speaking=False,
            activity=f"Awaiting approval for {op}",
        )
        await self.set_activity(f"Awaiting approval for {op}")

    async def _on_safety_event(self, data: Any) -> None:
        """Critical or safety event -> serious state, overriding humor."""
        if not self._enabled:
            return
        self.safety_locked = True
        reason = (
            data.get("reason", "Safety warning")
            if isinstance(data, dict)
            else str(data or "Safety warning")
        )
        await self.set_state(
            CharacterMode.ERROR.value,
            emotion=CharacterEmotion.SERIOUS.value,
            intensity=0.95,
            expression="serious",
            animation="idle",
            speaking=False,
            activity=sanitize_activity_text(reason),
        )

    async def _on_chunk(self, data: Any) -> None:
        if not self._enabled:
            return
        chunk_text = (
            data.get("content", "") if isinstance(data, dict) else str(data or "")
        )
        if not chunk_text:
            return
        self._turn_text_accum += chunk_text
        if self.emotion_engine.is_safety_critical(text=chunk_text):
            self.safety_locked = True
            await self.set_emotion(
                CharacterEmotion.SERIOUS.value, 0.9, safety_critical=True
            )
        elif "[System Error" in chunk_text:
            self._turn_had_error = True
            await self.set_emotion(CharacterEmotion.CONCERNED.value, 0.75)

    async def _on_done(self, data: Any) -> None:
        if not self._enabled:
            return
        resolved_anim = "idle"
        resolved_move = "stay"
        resolved_choreo: List[Dict[str, Any]] = []
        resolved_custom_pose: Optional[Dict[str, Any]] = None
        # Evaluate final turn outcome
        if self.safety_locked:
            await self.set_emotion(
                CharacterEmotion.SERIOUS.value, 0.9, safety_critical=True
            )
        elif self._turn_had_error:
            await self.set_emotion(CharacterEmotion.CONCERNED.value, 0.75)
        else:
            ev_type = (
                "task_success"
                if self._turn_tool_count > 0
                else "normal"
            )
            eval_res = self.emotion_engine.evaluate_event(
                ev_type,
                text=self._turn_text_accum,
                user_text=self._turn_user_text,
                tool_count=self._turn_tool_count,
                safety_locked=self.safety_locked,
            )
            if eval_res.emotion == CharacterEmotion.NEUTRAL.value and not self._turn_text_accum.strip():
                eval_res = self.emotion_engine.evaluate_event("task_success")
            resolved_anim = eval_res.animation or ("nod" if eval_res.emotion == "happy" else "idle")
            resolved_move = eval_res.movement or "stay"
            resolved_choreo = list(eval_res.choreography)
            resolved_custom_pose = eval_res.custom_pose
            await self.set_emotion(eval_res.emotion, eval_res.intensity)

        # If VoiceManager is not actively speaking, transition with resolved body pose & movement
        if not self.state.speaking:
            await self.set_state(
                CharacterMode.IDLE.value,
                emotion=self.state.emotion,
                intensity=self.state.intensity,
                speaking=False,
                animation=resolved_anim if not self.safety_locked else "idle",
                movement=resolved_move if not self.safety_locked else "stay",
                choreography=resolved_choreo if not self.safety_locked else [],
                custom_pose=resolved_custom_pose if not self.safety_locked else None,
                activity=None,
            )

    async def _on_speech_started(self, data: Any) -> None:
        if not self._enabled:
            return
        text = data.get("text") if isinstance(data, dict) else None
        await self.start_speaking(text=text)

    async def _on_audio_chunk(self, data: Any) -> None:
        if not self._enabled or not isinstance(data, dict):
            return
        speech_msg = build_speech_message(
            True,
            event="audio_chunk",
            text=data.get("text"),
            audio_b64=data.get("audio_b64"),
            mime_type=data.get("mime_type", "audio/wav"),
            sample_rate=data.get("sample_rate"),
            duration=data.get("duration"),
            rms=data.get("rms"),
            visemes=data.get("visemes"),
        )
        await self.adapter.publish_protocol(speech_msg)

    async def _on_speech_finished(self, data: Any) -> None:
        if not self._enabled:
            return
        await self.stop_speaking(interrupted=False)

    async def _on_speech_interrupted(self, data: Any) -> None:
        if not self._enabled:
            return
        await self.stop_speaking(interrupted=True)


# Singleton CharacterManager attached to global_bus
character_manager = CharacterManager(event_bus=global_bus)
