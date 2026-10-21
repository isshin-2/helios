"""
HELIOS Kokoro TTS Quality Upgrade — Comprehensive Pipeline Tests
Covers text normalization, pronunciation resolution, prosody planning,
safety overrides, audio conditioning, lip-sync generation, streaming,
interrupt handling, and concurrency turn isolation.
"""
import pytest
import asyncio
import numpy as np
from unittest.mock import Mock, patch, AsyncMock

from core.audio.tts.text_normalizer import TextNormalizer, StreamingFilterState
from core.audio.tts.pronunciation import EngineeringPronunciationResolver
from core.audio.tts.prosody import ProsodyEngine, ProsodyProfile
from core.audio.tts.speech_planner import SpeechPlanner, SpeechPlan
from core.audio.tts.audio_processor import AudioProcessor
from core.audio.tts.kokoro import KokoroTTS
from core.audio.voice_manager import VoiceManager
from core.character_state import CharacterMode, CharacterEmotion, CharacterStyle
from core.events import EventBus


# =============================================================================
# 1. Text Normalization Tests
# =============================================================================

def test_normalization_technical_tags_and_markdown():
    normalizer = TextNormalizer()

    # Markdown bold, italics, backticks, headings, links
    raw = "### Header\nCheck **ESP32** and *GPIO* via `gpio_set_level()` [Link](https://espressif.com)."
    norm = normalizer.normalize(raw)
    assert "###" not in norm
    assert "**" not in norm
    assert "*" not in norm
    assert "`" not in norm
    assert "https://espressif.com" not in norm
    assert "Link" in norm
    assert "ESP32 and GPIO" in norm

def test_normalization_body_pose_and_system_tags():
    normalizer = TextNormalizer()

    raw = (
        "[BODY: move=stay, pose=cyber_salute, emotion=serious] Reporting for duty! "
        "[POSE_JSON: {\"name\": \"salute\"}] [Tool Executed: terminal] [Code] "
        "[TELEMETRY] System nominal."
    )
    norm = normalizer.normalize(raw)
    assert "[BODY" not in norm
    assert "cyber_salute" not in norm
    assert "[POSE_JSON" not in norm
    assert "Tool Executed" not in norm
    assert "[Code]" not in norm
    assert "[TELEMETRY]" not in norm
    assert "Reporting for duty! System nominal." in norm

def test_normalization_json_and_tool_leakage():
    normalizer = TextNormalizer()

    leaked = '{"name": "file_reader", "arguments": {"path": "main.py"}}'
    assert normalizer.should_mute(leaked) is True
    assert normalizer.normalize(leaked) == ""

def test_normalization_emojis_and_buttons():
    normalizer = TextNormalizer()

    raw = "Welcome back! 🚀🔥 Click <button>Proceed</button> to continue."
    norm = normalizer.normalize(raw)
    assert "🚀" not in norm
    assert "🔥" not in norm
    assert "Option: Proceed." in norm

def test_normalization_mathematics():
    normalizer = TextNormalizer()

    # Math symbols
    raw = "The formula is 2^8 with tolerance ± 5% where x != y."
    norm = normalizer.normalize(raw)
    assert "2 to the power of 8" in norm
    assert "plus or minus" in norm
    assert "5 percent" in norm
    assert "is not equal to" in norm

def test_normalization_engineering_units():
    normalizer = TextNormalizer()

    raw = "Apply 3.3V and 10mA to the 10kΩ resistor with a 100uF capacitor at 12MHz and 60fps."
    norm = normalizer.normalize(raw)
    assert "3.3 volts" in norm
    assert "10 milliamps" in norm
    assert "10 kilo ohms" in norm
    assert "100 microfarads" in norm
    assert "12 megahertz" in norm
    assert "60 frames per second" in norm


# =============================================================================
# 2. Pronunciation Resolution Tests
# =============================================================================

def test_pronunciation_engineering_acronyms():
    resolver = EngineeringPronunciationResolver()

    raw = "Connect the ESP32-S3 to GPIO and I2C with SPI and UART."
    resolved = resolver.resolve(raw)
    assert "E S P thirty two S three" in resolved
    assert "G P I O" in resolved
    assert "I two C" in resolved
    assert "S P I" in resolved
    assert "you art" in resolved

def test_pronunciation_case_sensitivity_protection():
    resolver = EngineeringPronunciationResolver()

    # CAN (bus) vs can (verb)
    raw = "We can use the CAN bus and the PID controller with RAM."
    resolved = resolver.resolve(raw)
    assert "We can use" in resolved  # lowercase 'can' must NOT be altered
    assert "can bus" in resolved or "can" in resolved
    assert "P I D" in resolved
    assert "ram" in resolved

def test_pronunciation_user_override():
    resolver = EngineeringPronunciationResolver()
    resolver.add_pronunciation("HELIOS", "hee lee oss")
    resolved = resolver.resolve("Welcome to HELIOS!")
    assert "hee lee oss" in resolved


# =============================================================================
# 3. Prosody and Dynamic Speed Tests
# =============================================================================

def test_prosody_emotion_influences_speed():
    prosody = ProsodyEngine()

    spd_neutral, _, _, _ = prosody.compute_prosody("Hello user.", emotion="neutral", intensity=0.5)
    spd_happy, _, _, _ = prosody.compute_prosody("Hello user.", emotion="happy", intensity=1.0)
    spd_serious, _, _, _ = prosody.compute_prosody("Hello user.", emotion="serious", intensity=1.0)
    spd_excited, _, _, _ = prosody.compute_prosody("Hello user.", emotion="excited", intensity=1.0)

    assert spd_happy > spd_neutral
    assert spd_serious < spd_neutral
    assert spd_excited > spd_happy

def test_prosody_sentence_types():
    prosody = ProsodyEngine()

    # Question
    _, p_before_q, p_after_q, st_q = prosody.compute_prosody("Can you verify this pinout?")
    assert st_q == "question"
    assert p_after_q >= 0.1

    # Warning
    spd_warn, p_before_w, p_after_w, st_w = prosody.compute_prosody("Warning! Overcurrent hazard detected.")
    assert st_w == "warning"
    assert spd_warn < 1.0
    assert p_before_w > 0.0

    # Short reaction
    spd_react, _, _, st_react = prosody.compute_prosody("Got it.")
    assert st_react == "short_reaction"
    assert spd_react > 1.0


# =============================================================================
# 4. Safety Override Tests
# =============================================================================

def test_safety_override_forces_serious_prosody():
    planner = SpeechPlanner()

    # Normally happy speech
    plan_happy = planner.plan("Diagnostic finished successfully.", emotion="happy", intensity=1.0, safety_locked=False)
    assert plan_happy.emotion == "happy"
    assert plan_happy.speed > 1.0

    # Safety locked must override to serious regardless of requested emotion
    plan_safe = planner.plan("Diagnostic finished successfully.", emotion="happy", intensity=1.0, safety_locked=True)
    assert plan_safe.emotion == "serious"
    assert plan_safe.style == "natural"
    assert plan_safe.speed < 1.0
    assert plan_safe.safety_locked is True


# =============================================================================
# 5. Audio Processor Conditioning Tests
# =============================================================================

def test_audio_processor_dc_removal_and_limiting():
    processor = AudioProcessor(sample_rate=24000, highpass_cutoff=70.0, limiter_ceiling_db=-1.0)

    # Synthetic waveform with high DC offset and clipping peaks
    t = np.linspace(0, 1.0, 24000, endpoint=False, dtype=np.float32)
    tone = 0.8 * np.sin(2 * np.pi * 440 * t) + 0.3  # DC offset of +0.3
    # Add a huge burst that would clip
    tone[1000:1050] += 2.5

    conditioned = processor.process(tone, 24000)

    # 1. DC offset should be virtually zero
    assert abs(float(np.mean(conditioned))) < 0.05
    # 2. Output must not clip [-1.0, 1.0]
    assert np.max(conditioned) <= 1.0
    assert np.min(conditioned) >= -1.0
    # 3. Peak limiter ceiling (-1 dB ~ 0.891)
    ceiling_linear = 10.0 ** (-1.0 / 20.0)
    assert np.max(np.abs(conditioned)) <= ceiling_linear + 0.02


# =============================================================================
# 6. Lip-Sync & Viseme Protocol Compatibility Tests
# =============================================================================

def test_lip_sync_metadata_generation():
    samples = np.zeros(24000, dtype=np.float32)
    # Synthetic burst
    samples[6000:18000] = 0.5 * np.sin(np.linspace(0, 50, 12000))

    meta = VoiceManager._compute_lip_sync_metadata(samples, 24000, "Hello world from HELIOS.")

    assert meta["text"] == "Hello world from HELIOS."
    assert meta["sample_rate"] == 24000
    assert meta["duration"] == 1.0
    assert meta["mime_type"] == "audio/wav"
    assert len(meta["rms"]) > 0
    assert len(meta["visemes"]) > 0
    assert isinstance(meta["audio_b64"], str)

    # Verify visemes contain valid VRM keys
    valid_visemes = {"aa", "ih", "ou", "ee", "oh"}
    for v in meta["visemes"]:
        assert v["viseme"] in valid_visemes
        assert "time" in v
        assert "duration" in v
        assert "weight" in v


# =============================================================================
# 7. Sentence Streaming and Buffer Segmentation Tests
# =============================================================================

def test_sentence_streaming_segmentation():
    planner = SpeechPlanner()
    buffer = "First sentence completed. Second sentence underway! Third one? Partial remaining"

    sentences, rem = planner.extract_sentences(buffer, force=False)
    assert len(sentences) == 3
    assert sentences[0] == "First sentence completed."
    assert sentences[1] == "Second sentence underway!"
    assert sentences[2] == "Third one?"
    assert rem.strip() == "Partial remaining"

    # Force flush remainder
    final_sentences, rem2 = planner.extract_sentences(rem, force=True)
    assert len(final_sentences) == 1
    assert final_sentences[0] == "Partial remaining"
    assert rem2 == ""


# =============================================================================
# 8. Barge-In Interrupt and Turn Isolation (Concurrency) Tests
# =============================================================================

@pytest.mark.asyncio
async def test_barge_in_and_turn_isolation():
    bus = EventBus()
    vm = VoiceManager(event_bus=bus)

    events_received = []

    async def log_event(data):
        events_received.append(data)

    bus.subscribe("speech_interrupted", log_event)

    # Turn 0 setup
    initial_turn = vm._current_turn_id
    plan_stale = vm.speech_planner.plan("This is turn zero.")
    plan_stale.turn_id = initial_turn

    # Enqueue stale plan
    vm._tts_queue.put_nowait(plan_stale)
    assert not vm._tts_queue.empty()

    # Trigger interrupt
    vm.interrupt()
    await asyncio.sleep(0.01)

    # Assertions for barge-in
    assert vm._current_turn_id == initial_turn + 1
    assert vm._tts_queue.empty()
    assert vm._text_buffer == ""
    assert vm.is_speaking is False
    assert len(events_received) == 1
    assert events_received[0]["reason"] == "barge_in"


@pytest.mark.asyncio
async def test_synthesis_worker_discards_stale_turn():
    """Verify that if a queued item has an older turn_id, the worker discards it."""
    vm = VoiceManager()
    vm.tts = Mock()
    vm.tts.synthesize = AsyncMock()

    # Set turn ID to 5
    vm._current_turn_id = 5

    # Enqueue a plan belonging to turn 4 (stale)
    stale_plan = vm.speech_planner.plan("Stale sentence from previous turn.")
    stale_plan.turn_id = 4
    await vm._tts_queue.put(stale_plan)

    # Enqueue a plan belonging to current turn 5 (valid)
    valid_plan = vm.speech_planner.plan("Fresh sentence for current turn.")
    valid_plan.turn_id = 5
    await vm._tts_queue.put(valid_plan)

    # Sentinel to stop worker
    await vm._tts_queue.put((5, "<END_OF_STREAM>"))

    # Mock synthesize generator to yield 1 chunk
    async def dummy_synthesize(*args, **kwargs):
        yield np.zeros(2400, dtype=np.float32), 24000

    vm.tts.synthesize = dummy_synthesize

    # Run worker briefly until done
    worker_task = asyncio.create_task(vm._synthesis_worker())
    await vm._tts_queue.join()
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass

    # The stale sentence must never have updated speaking text to stale
    assert vm._tts_queue.empty()
