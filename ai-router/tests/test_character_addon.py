"""
Automated tests for the HELIOS Character Addon architecture (Sections 1–21).

Covers all 9 required test scenarios from Section 21:
- Test 1: Character Disabled (NullCharacterAdapter)
- Test 2: Character Connect (initial state sync)
- Test 3: Tool Execution (executing mode + sanitized activity summary)
- Test 4: Tool Failure (error mode + concerned emotion)
- Test 5: Critical Action (safety override -> serious, humor suppressed)
- Test 6: Character Crash (client raises exception mid-response -> Core unaffected)
- Test 7: Reconnection (viewer reconnects and syncs current state)
- Test 8: Speech Sync (speech_started -> audio_chunk with RMS/visemes -> speech_finished)
- Test 9: Speech Interrupt (speech_interrupted -> character_stop + return to idle)
"""
from typing import Any, Dict, List
import pytest

from core.events import EventBus
from core.character_state import (
    CharacterState,
    CharacterMode,
    CharacterEmotion,
)
from core.emotion_engine import EmotionEngine, load_personality_card
from core.character_manager import (
    CharacterManager,
    NullCharacterAdapter,
    sanitize_activity_text,
)
from core.character_models import CharacterModelRegistry


class MockWebSocketClient:
    """Mock WebSocket client for testing CharacterManager.register_client & broadcasting."""

    def __init__(self, should_crash: bool = False):
        self.should_crash = should_crash
        self.messages: List[Dict[str, Any]] = []

    async def send_json(self, payload: Dict[str, Any]) -> None:
        if self.should_crash:
            raise RuntimeError("Simulated WebGL / WebSocket renderer crash!")
        self.messages.append(payload)


# =====================================================================
# Test 1 — Character Disabled
# =====================================================================
@pytest.mark.asyncio
async def test_1_character_disabled():
    """
    Run HELIOS with CHARACTER_ENABLED=false.
    Expected: normal EventBus operation, NullCharacterAdapter active, no protocol traffic.
    """
    bus = EventBus()
    manager = CharacterManager(event_bus=bus, enabled=False)
    assert manager.enabled is False
    assert isinstance(manager.adapter, NullCharacterAdapter)

    ws_client = MockWebSocketClient()
    await manager.register_client(ws_client)

    # Publish full lifecycle events on the EventBus
    await bus.publish("ui_state", "thinking")
    await bus.publish("tool_start", {"tool": "web_search"})
    await bus.publish("tool_complete", {"tool": "web_search"})
    await bus.publish("chunk", {"content": "Here is the answer."})
    await bus.publish("done", {})
    await bus.publish("ui_state", "idle")

    # NullCharacterAdapter must not emit any character protocol messages
    assert ws_client.messages == []
    assert manager.history == []
    sync = manager.get_sync_payload()
    assert sync["type"] == "character_sync"
    assert sync["enabled"] is False


# =====================================================================
# Test 2 — Character Connect
# =====================================================================
@pytest.mark.asyncio
async def test_2_character_connect():
    """
    Start HELIOS, then start/connect character viewer.
    Expected: character receives current state (`character_sync` + `character_state`) and enters idle.
    """
    bus = EventBus()
    manager = CharacterManager(
        event_bus=bus,
        enabled=True,
        renderer="vrm",
        model_id="helios-v1",
    )
    assert manager.enabled is True

    ws_client = MockWebSocketClient()
    sync = await manager.register_client(ws_client)

    assert sync["type"] == "character_sync"
    assert sync["enabled"] is True
    assert sync["renderer"] == "vrm"
    assert sync["model"]["id"] == "helios-v1"
    assert sync["state"]["type"] == "character_state"
    assert sync["state"]["mode"] == "idle"
    assert sync["state"]["emotion"] == "neutral"
    assert sync["state"]["animation"] == "idle"
    assert sync["state"]["speaking"] is False
    assert len(ws_client.messages) == 2
    assert ws_client.messages[0]["type"] == "character_sync"
    assert ws_client.messages[1]["type"] == "character_state"


# =====================================================================
# Test 3 — Tool Execution & Sanitized Activity Summary
# =====================================================================
@pytest.mark.asyncio
async def test_3_tool_execution():
    """
    Trigger file/shell/search tool.
    Expected: character enters executing mode, displays safe activity summary
    (with any <think> tags stripped), and returns to normal after completion.
    """
    bus = EventBus()
    manager = CharacterManager(event_bus=bus, enabled=True)
    ws_client = MockWebSocketClient()
    await manager.register_client(ws_client)
    ws_client.messages.clear()

    # Verify sanitize_activity_text strips chain-of-thought and raw JSON
    leaked = "<think>secret internal chain of thought</think>[System] Running tool web_search..."
    clean = sanitize_activity_text(leaked)
    assert clean == "Searching the web"
    assert "secret internal" not in clean

    # Trigger tool via EventBus status with <think> block
    await bus.publish("status", leaked)

    state_msgs = [m for m in ws_client.messages if m["type"] == "character_state"]
    activity_msgs = [m for m in ws_client.messages if m["type"] == "character_activity"]

    assert len(state_msgs) >= 1
    assert state_msgs[-1]["mode"] == "executing"
    assert state_msgs[-1]["emotion"] == "curious"
    assert state_msgs[-1]["activity"] == "Searching the web"

    assert len(activity_msgs) >= 1
    assert activity_msgs[-1]["activity"] == "Searching the web"

    # Complete tool call and return to idle
    await bus.publish("tool_complete", {"tool": "web_search"})
    await bus.publish("ui_state", "idle")

    assert manager.state.mode == CharacterMode.IDLE.value
    assert manager.state.activity is None


# =====================================================================
# Test 4 — Tool Failure
# =====================================================================
@pytest.mark.asyncio
async def test_4_tool_failure():
    """
    Trigger failed tool call.
    Expected: character shows concerned expression in error mode.
    """
    bus = EventBus()
    manager = CharacterManager(event_bus=bus, enabled=True)
    ws_client = MockWebSocketClient()
    await manager.register_client(ws_client)
    ws_client.messages.clear()

    await bus.publish(
        "tool_error",
        {"tool": "stateful_shell", "error": "Command timed out"},
    )

    state_msgs = [m for m in ws_client.messages if m["type"] == "character_state"]
    assert len(state_msgs) >= 1
    latest = state_msgs[-1]
    assert latest["mode"] == "error"
    assert latest["emotion"] == "concerned"
    assert latest["expression"] == "concerned"
    assert latest["intensity"] == pytest.approx(0.75)


# =====================================================================
# Test 5 — Critical Action (Safety Override)
# =====================================================================
@pytest.mark.asyncio
async def test_5_critical_action_safety_override():
    """
    Trigger high-risk tool requiring approval or destructive operation.
    Expected: character enters serious expression, humor/smirk suppressed even
    if response contains playful keywords.
    """
    bus = EventBus()
    manager = CharacterManager(event_bus=bus, enabled=True)
    ws_client = MockWebSocketClient()
    await manager.register_client(ws_client)
    ws_client.messages.clear()

    # 1. Approval request event
    await bus.publish(
        "approval_request",
        {"operation": "delete production config"},
    )

    assert manager.safety_locked is True
    assert manager.state.emotion == CharacterEmotion.SERIOUS.value
    assert manager.state.expression == "serious"
    assert manager.state.intensity == pytest.approx(0.9)

    # 2. Even if response chunks and done contain playful/humor keywords while safety_locked,
    #    the EmotionEngine and CharacterManager must keep emotion locked to SERIOUS.
    await bus.publish("chunk", {"content": "Haha lol plot twist, all tests pass!"})
    await bus.publish("done", {})

    assert manager.state.emotion == CharacterEmotion.SERIOUS.value
    assert manager.state.expression == "serious"

    # Attempting to manually set amusing expression while safety_locked is also overridden
    await manager.set_expression("smirk")
    assert manager.state.expression == "serious"


# =====================================================================
# Test 6 — Character Crash Isolation
# =====================================================================
@pytest.mark.asyncio
async def test_6_character_crash_isolation():
    """
    Simulate a crashing character viewer process mid-response.
    Expected: HELIOS finishes response normally, logs/prunes dead client cleanly.
    """
    bus = EventBus()
    manager = CharacterManager(event_bus=bus, enabled=True)

    crashing_client = MockWebSocketClient(should_crash=False)
    healthy_client = MockWebSocketClient(should_crash=False)

    await manager.register_client(crashing_client)
    await manager.register_client(healthy_client)

    # Now make crashing_client fail on next message
    crashing_client.should_crash = True
    healthy_client.messages.clear()

    # Publishing events must not raise even though crashing_client throws RuntimeError
    await bus.publish("ui_state", "thinking")
    await bus.publish("chunk", {"content": "Completed successfully!"})
    await bus.publish("done", {})

    # Crashing client was automatically pruned; healthy client received all updates
    assert crashing_client not in manager._clients
    assert healthy_client in manager._clients
    assert len(healthy_client.messages) >= 2


# =====================================================================
# Test 7 — Reconnection & State Sync
# =====================================================================
@pytest.mark.asyncio
async def test_7_reconnection_sync():
    """
    Restart/reconnect character viewer after state changes occurred while disconnected.
    Expected: character reconnects and syncs to current state immediately.
    """
    bus = EventBus()
    manager = CharacterManager(event_bus=bus, enabled=True)

    # State changes happen while no viewer is connected
    await bus.publish("tool_start", {"tool": "file_reader"})
    assert manager.state.mode == CharacterMode.EXECUTING.value
    assert manager.state.emotion == CharacterEmotion.CURIOUS.value
    assert manager.state.activity == "Reading project files"

    # Viewer connects later and receives sync payload
    reconnected_client = MockWebSocketClient()
    sync = await manager.register_client(reconnected_client)

    assert sync["type"] == "character_sync"
    assert sync["state"]["mode"] == "executing"
    assert sync["state"]["emotion"] == "curious"
    assert sync["state"]["activity"] == "Reading project files"
    assert reconnected_client.messages[0]["type"] == "character_sync"


# =====================================================================
# Test 8 — Speech Sync
# =====================================================================
@pytest.mark.asyncio
async def test_8_speech_sync():
    """
    Speak response via VoiceManager events (speech_started -> audio_chunk -> speech_finished).
    Expected: character mouth moves (speaking=True with RMS/visemes) and stops when speech ends.
    """
    bus = EventBus()
    manager = CharacterManager(event_bus=bus, enabled=True)
    ws_client = MockWebSocketClient()
    await manager.register_client(ws_client)
    ws_client.messages.clear()

    await bus.publish("speech_started", {"text": "Hello from HELIOS."})
    assert manager.state.speaking is True
    assert manager.state.mode == CharacterMode.SPEAKING.value

    await bus.publish(
        "audio_chunk",
        {
            "text": "Hello from HELIOS.",
            "rms": [0.1, 0.45, 0.8, 0.3, 0.0],
            "visemes": [{"viseme": "aa", "start": 0.0, "end": 0.2, "weight": 0.8}],
            "duration": 0.5,
            "audio_b64": "UklGRg==",
            "mime_type": "audio/wav",
        },
    )

    speech_msgs = [
        m
        for m in ws_client.messages
        if m["type"] == "character_speech" and m.get("event") == "audio_chunk"
    ]
    assert len(speech_msgs) == 1
    assert speech_msgs[0]["speaking"] is True
    assert speech_msgs[0]["rms"] == [0.1, 0.45, 0.8, 0.3, 0.0]
    assert len(speech_msgs[0]["visemes"]) == 1

    await bus.publish("speech_finished", {"text": "Hello from HELIOS."})
    assert manager.state.speaking is False
    assert manager.state.mode == CharacterMode.IDLE.value


# =====================================================================
# Test 9 — Speech Interrupt
# =====================================================================
@pytest.mark.asyncio
async def test_9_speech_interrupt():
    """
    Interrupt speech mid-sentence.
    Expected: character_stop emitted, speaking=False, character returns to idle.
    """
    bus = EventBus()
    manager = CharacterManager(event_bus=bus, enabled=True)
    ws_client = MockWebSocketClient()
    await manager.register_client(ws_client)
    ws_client.messages.clear()

    await bus.publish(
        "speech_started",
        {"text": "Long explanation that gets interrupted mid-sentence..."},
    )
    assert manager.state.speaking is True

    await bus.publish("speech_interrupted", {})

    stop_msgs = [m for m in ws_client.messages if m["type"] == "character_stop"]
    assert len(stop_msgs) == 1
    assert stop_msgs[0]["reason"] == "speech_interrupted"
    assert manager.state.speaking is False
    assert manager.state.mode == CharacterMode.IDLE.value
    assert manager.state.animation == "idle"


# =====================================================================
# Additional Verification: Personality Card & Model Manifest Registry
# =====================================================================
def test_personality_card_and_model_registry():
    card = load_personality_card()
    assert card["name"] in ("Airi", "HELIOS")
    suppress_list = card["safety"]["suppress_humor_on"]
    assert "safety" in suppress_list
    assert "security" in suppress_list
    assert "destructive_action" in suppress_list
    assert "critical_failure" in suppress_list

    registry = CharacterModelRegistry()
    manifest = registry.get_manifest("helios-v1")
    assert manifest is not None
    assert manifest["id"] == "helios-v1"
    assert manifest["format"] == "vrm"
    assert "neutral" in manifest["expressions"]
    assert "idle" in manifest["animations"]


# =====================================================================
# Test 10 — AI Body Movement & Spatial Choreography
# =====================================================================
@pytest.mark.asyncio
async def test_10_ai_body_movement_and_spatial_choreography():
    """
    Verify that EmotionEngine and CharacterManager resolve full-body poses
    (backflip, dance_shikano, hug_attempt, wave, bow, peace) and 3D spatial
    movements (walk_to_user, step_back, circle_user, return_center), while
    still respecting safety overrides.
    """
    bus = EventBus()
    manager = CharacterManager(event_bus=bus, enabled=True)
    ws_client = MockWebSocketClient()
    await manager.register_client(ws_client)
    ws_client.messages.clear()

    # 1. Walk to user + backflip command
    manager.set_user_turn_text("Come closer and do a backflip!")
    await bus.publish("chunk", {"content": "Coming right over with a backflip!"})
    await bus.publish("done", {})

    assert manager.state.emotion == CharacterEmotion.EXCITED.value
    assert manager.state.animation == "backflip"
    assert manager.state.movement == "walk_to_user"
    assert ws_client.messages[-1]["animation"] == "backflip"
    assert ws_client.messages[-1]["movement"] == "walk_to_user"

    # 2. Dance command
    eval_dance = manager.emotion_engine.evaluate_event(
        "normal",
        user_text="Can you dance for me?",
        text="Let's groove!",
    )
    assert eval_dance.animation == "dance_shikano"
    assert eval_dance.emotion == CharacterEmotion.EXCITED.value

    # 3. Safety override suppresses body movement and tricks
    manager.safety_locked = True
    await manager.direct_turn_body("Come closer and dance!", "Sure!")
    assert manager.state.emotion == CharacterEmotion.SERIOUS.value
    assert manager.state.animation == "idle"
    assert manager.state.movement == "stay"


# =====================================================================
# Test 11 — Trained 3-Head Neural Body Movement Model & Inline [BODY] Tags
# =====================================================================
@pytest.mark.asyncio
async def test_11_trained_neural_body_model_and_inline_tags():
    """
    Verify that the Trained 3-Head Neural MLP Body Movement Model
    (`helios_body_movement_model.pkl`) is loaded, accurately predicts
    3D spatial movement, full-body IK poses, and multi-step choreography,
    and parses/strips inline `[BODY: move=..., pose=..., emotion=...]` tags.
    """
    from core.trained_body_model import (
        TrainedBodyMovementModel,
        parse_and_strip_inline_body_tags,
    )

    model = TrainedBodyMovementModel.load_default()
    assert model.trained is True

    # 1. Held-out natural language movement + trick predictions
    pred_flip = model.predict(user_text="Hey, walk over to me and do a backflip!")
    assert pred_flip["movement"] == "walk_to_user"
    assert pred_flip["animation"] == "backflip"
    assert pred_flip["emotion"] == "excited"
    assert len(pred_flip["choreography"]) >= 2

    pred_circle = model.predict(user_text="Circle around me to check my rig")
    assert pred_circle["movement"] == "circle_user"
    assert pred_circle["animation"] in ("think_pose", "thinking_chin_rest")

    pred_bow = model.predict(user_text="Step back and bow politely")
    assert pred_bow["movement"] == "step_back"
    assert pred_bow["animation"] in ("bow", "polite_namaste_bow")

    # 2. Inline [BODY: ...] control tag extraction and stripping
    raw_reply = "[BODY: move=walk_to_user, pose=peace, emotion=happy] Coming right up with a peace sign!"
    clean_text, tags = parse_and_strip_inline_body_tags(raw_reply)
    assert clean_text == "Coming right up with a peace sign!"
    assert tags[0]["movement"] == "walk_to_user"
    assert tags[0]["animation"] == "peace"
    assert tags[0]["emotion"] == "happy"

    # 3. End-to-end CharacterManager.direct_turn_body with multi-step choreography
    bus = EventBus()
    manager = CharacterManager(event_bus=bus, enabled=True)
    state_msg = await manager.direct_turn_body(
        "Walk closer and do a backflip!",
        "[BODY: move=walk_to_user, pose=backflip, emotion=excited] Watch this!",
    )
    assert state_msg["movement"] == "walk_to_user"
    assert state_msg["animation"] == "backflip"
    assert state_msg["emotion"] == "excited"
    assert len(state_msg["choreography"]) >= 2


# =====================================================================
# Test 12 — HELIOS Pose Generator (Kalidokit / @pixiv/three-vrm / ChatVRM / Amica)
# =====================================================================
@pytest.mark.asyncio
async def test_12_helios_pose_generator_and_strict_control():
    """
    Verify that:
    1. Plain conversation without explicit physical cues does NOT trigger random body movements.
    2. HELIOSPoseGenerator resolves procedural templates (cyber_salute, superhero_landing, etc.).
    3. HELIOSPoseGenerator composes arbitrary multi-joint 3D poses from natural language descriptions.
    4. Anatomical joint limits (VRM_BONE_LIMITS_DEG) clamp extreme rotations safely.
    """
    from core.pose_generator import (
        get_pose_generator,
        sanitize_custom_pose,
    )

    bus = EventBus()
    manager = CharacterManager(event_bus=bus, enabled=True)

    # 1. Plain conversational query does NOT trigger unprompted body movement
    plain_state = await manager.direct_turn_body(
        "What is the capital of France?",
        "The capital of France is Paris.",
    )
    assert plain_state["movement"] == "stay"
    assert plain_state["custom_pose"] is None

    # 2. Procedural template pose via generate_custom_pose
    salute_state = await manager.generate_custom_pose("Strike a cyber salute")
    assert salute_state["animation"] == "cyber_salute"
    assert salute_state["custom_pose"] is not None
    assert salute_state["custom_pose"]["name"] == "cyber_salute"
    assert salute_state["custom_pose"]["rightHandShape"] == "salute"
    assert "rightWrist" in salute_state["custom_pose"]["ik"]

    # 3. Arbitrary natural-language kinematic pose composition
    custom_state = await manager.generate_custom_pose(
        "Create a pose: crouch low, tilt head left, raise right hand high in a fist and left hand on hip"
    )
    cp = custom_state["custom_pose"]
    assert cp is not None
    assert cp["hipsOffsetY"] < 0.0
    assert cp["rightHandShape"] == "fist"
    assert "leftUpperLeg" in cp["bones"]
    assert "rightWrist" in cp["ik"]

    # 4. Anatomical clamping prevents impossible bone twists
    extreme = sanitize_custom_pose(
        {
            "name": "extreme_test",
            "hipsOffsetY": -99.0,
            "bones": {"head": [99.0, -99.0, 99.0]},
        }
    )
    assert extreme["hipsOffsetY"] == pytest.approx(-0.42)
    assert abs(extreme["bones"]["head"][0]) == pytest.approx(45.0)
    assert len(get_pose_generator().list_template_names()) >= 10


# =====================================================================
# Test 13 — Full Spec vs. Character-Only Standalone Editions
# =====================================================================
@pytest.mark.asyncio
async def test_13_full_spec_vs_character_only_editions():
    """
    Verify that `helios-character/ai_server.py` supports both:
    - Full Spec mode (`edition="full_spec"`)
    - Character-Only Standalone mode (`edition="character_only"`) with local
      chat, TTS + viseme timeline, 24 human poses, 6 posture styles, and RL trainer
      even when HELIOS Core (:8000) is not running.
    """
    import sys
    from pathlib import Path

    char_dir = Path(__file__).resolve().parent.parent.parent / "helios-character"
    if str(char_dir) not in sys.path:
        sys.path.insert(0, str(char_dir))

    import ai_server

    # Switch to Character-Only edition
    st_char = await ai_server.update_helios_config({"edition": "character_only"})
    assert st_char["character_only"] is True
    assert st_char["edition"] == "character_only"

    # Verify standalone pose synthesis works without :8000
    pose_state = await ai_server.proxy_generate_character_pose({"prompt": "heart_hands_love"})
    assert pose_state["type"] == "character_state"
    assert pose_state["custom_pose"]["name"] == "heart_hands_love"

    # Verify standalone RL status & RL training work without :8000
    rl_st = await ai_server.proxy_get_character_rl_status()
    assert rl_st.get("policy_loaded") is True
    rl_train = await ai_server.proxy_train_character_rl_pose(
        {"pose_name": "cyber_salute", "episodes": 3, "simulate_curriculum": True}
    )
    assert "character_state" in rl_train
    assert rl_train["character_state"]["type"] == "character_state"

    # Verify standalone Character Chat + TTS works without :8000
    chat_res = await ai_server.standalone_engine.chat_standalone(
        "Hello! Come closer and wave!",
        viewer_id=999,
    )
    assert isinstance(chat_res["response"], str) and len(chat_res["response"]) > 0
    assert chat_res["edition"] == "character_only"
    assert chat_res["character_state"]["type"] == "character_state"
    assert "rms" in chat_res["tts"] and "visemes" in chat_res["tts"]

    # Switch to Full Spec edition
    st_full = await ai_server.update_helios_config({"edition": "full_spec"})
    assert st_full["configured_edition"] == "full_spec"
    assert st_full["character_only"] is False


# =====================================================================
# Test 14 — Speaking Procedure Termination & Curious/Waiting Idle Animations
# =====================================================================
def test_14_speaking_termination_and_curious_waiting_idle_animations():
    """
    Verify that:
    1. All 6 curious object & waiting idle animations are registered in VALID_ANIMATIONS,
       viewer/vrm/animation.js, viewer/index.html, and viewer/app.js.
    2. viewer/vrm/lip_sync.js and viewer/app.js properly invoke finishSpeakingProcedure()
       and onFinishCallback() so the VRM stops speaking poses & head rhythm as soon as speech ends.
    """
    from pathlib import Path
    from core.character_state import VALID_ANIMATIONS

    idle_anims = {
        "idle_popup_curious",
        "idle_orb_curious",
        "idle_screen_curious",
        "idle_waiting_patient",
        "idle_waiting_look",
        "idle_waiting_stretch",
    }
    assert idle_anims.issubset(VALID_ANIMATIONS)

    viewer_dir = Path(__file__).resolve().parent.parent.parent / "helios-character" / "viewer"
    anim_js = (viewer_dir / "vrm" / "animation.js").read_text(encoding="utf-8")
    lip_js = (viewer_dir / "vrm" / "lip_sync.js").read_text(encoding="utf-8")
    app_js = (viewer_dir / "app.js").read_text(encoding="utf-8")
    index_html = (viewer_dir / "index.html").read_text(encoding="utf-8")

    for pose in idle_anims:
        assert pose in anim_js
        assert pose in app_js
        assert pose in index_html

    assert "export function isIdleObjectOrWaitingPose" in anim_js
    assert app_js.index("const clock = new THREE.Clock()") < app_js.index("function setPose")
    assert "finishSpeakingProcedure" in app_js
    assert "speakingIdleWatchdog" in app_js
    assert "pendingSpeechChunks" in app_js
    assert "this.onFinishCallback()" in lip_js
    assert "HeliosCharacterPopup3D" in app_js
    assert "HeliosCharacterOrb3D" in app_js
    assert "HeliosCharacterGlassTap3D" in app_js
    assert "HeliosCharacterWristHud3D" in app_js
    assert "render3dHeliosPopupCanvas" in app_js
    assert "drawBlackHoleSvgOnCanvas" in app_js
    assert "render3dBlackHoleOrbCanvas" in app_js
    assert "01 // NEURAL SYNC" in app_js
    assert "popupGroup.visible = false" in app_js
    assert "orbGroup.visible = false" in app_js
    assert 'id="helios-interactive-popup"' not in index_html

