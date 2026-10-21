"""
HELIOS Kokoro TTS Quality & Expressiveness Evaluator
Compares speech synthesis output between:
1. Baseline Pipeline: Raw text, static speed, no normalization/pronunciation, unconditioned PCM.
2. Upgraded Pipeline: TextNormalizer, EngineeringPronunciationResolver, ProsodyEngine,
                     SpeechPlanner, AudioProcessor (DC removal, 70Hz high-pass, compression, limiter),
                     and enhanced lip-sync visemes.

Saves comparative audio WAVs into logs/tts_eval/ and prints empirical metrics.
"""
import os
import sys
import time
import asyncio
import numpy as np
import soundfile as sf
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from core.audio.tts.kokoro import KokoroTTS
from core.audio.tts.speech_planner import SpeechPlanner
from core.audio.tts.audio_processor import AudioProcessor
from core.audio.voice_manager import VoiceManager
import config


TEST_CASES = [
    {
        "id": "technical_hardware",
        "description": "Technical hardware setup with acronyms, voltage, units, and code",
        "text": "Connect the ESP32-S3 to GPIO pin 4 and initialize I2C at 400kHz with 3.3V and a 10kΩ pull-up resistor.",
        "emotion": "curious",
        "intensity": 0.6,
        "style": "natural",
        "safety_locked": False,
    },
    {
        "id": "safety_warning",
        "description": "Safety critical warning overriding casual tone",
        "text": "[BODY: move=stay, pose=martial_arts_guard, emotion=excited] Warning! Critical overcurrent and overheating detected on the MOSFET stage. Immediate shutdown required.",
        "emotion": "excited",  # Deliberately requested excited to verify safety override
        "intensity": 0.9,
        "style": "energetic",
        "safety_locked": True,  # Must force serious prosody and mute tags
    },
    {
        "id": "conversational_happy",
        "description": "Warm conversational greeting with markdown, button, and emojis",
        "text": "Hello there! 🚀 I've compiled your **FastAPI** backend and verified the WebSocket endpoints. Click <button>Deploy</button> to proceed.",
        "emotion": "happy",
        "intensity": 0.8,
        "style": "energetic",
        "safety_locked": False,
    },
    {
        "id": "question_cadence",
        "description": "Engineering inquiry with natural question intonation and pauses",
        "text": "Can you verify whether the RP2040 UART is configured for 115200 baud?",
        "emotion": "curious",
        "intensity": 0.7,
        "style": "natural",
        "safety_locked": False,
    },
]


async def run_evaluation():
    print("=" * 75)
    print(" HELIOS Kokoro TTS Pipeline Quality Evaluation")
    print("=" * 75)

    output_dir = Path(__file__).resolve().parent.parent.parent / "logs" / "tts_eval"
    output_dir.mkdir(parents=True, exist_ok=True)

    tts = KokoroTTS()
    print("Initializing Kokoro ONNX model...")
    if not tts.initialize():
        print("ERROR: Failed to initialize Kokoro TTS.")
        return

    planner = SpeechPlanner()
    processor = AudioProcessor(sample_rate=24000)

    results = []

    for tc in TEST_CASES:
        tc_id = tc["id"]
        raw_text = tc["text"]
        print(f"\n--- Test Case: {tc_id} ({tc['description']}) ---")
        print(f"Raw Input Text: {raw_text}")

        # -------------------------------------------------------------
        # 1. Baseline Pipeline
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        base_chunks = []
        # Raw text directly into Kokoro with static speed 1.0, no normalization
        async for chunk, sr in tts.synthesize(raw_text, voice=config.VOICE_NAME, speed=1.0):
            base_chunks.append(chunk)
        t_base_synth = (time.perf_counter() - t0) * 1000

        base_samples = np.concatenate(base_chunks) if base_chunks else np.array([], dtype=np.float32)
        base_wav_path = output_dir / f"{tc_id}_baseline.wav"
        if len(base_samples) > 0:
            sf.write(str(base_wav_path), base_samples, 24000)

        # Baseline metrics
        base_dc = float(np.mean(base_samples)) if len(base_samples) else 0.0
        base_peak = float(np.max(np.abs(base_samples))) if len(base_samples) else 0.0
        base_rms = float(np.sqrt(np.mean(base_samples ** 2))) if len(base_samples) else 0.0
        base_peak_db = 20.0 * np.log10(base_peak + 1e-9)
        base_rms_db = 20.0 * np.log10(base_rms + 1e-9)

        # -------------------------------------------------------------
        # 2. Upgraded HELIOS Pipeline
        # -------------------------------------------------------------
        t_plan_start = time.perf_counter()
        plan = planner.plan(
            text=raw_text,
            emotion=tc["emotion"],
            intensity=tc["intensity"],
            style=tc["style"],
            safety_locked=tc["safety_locked"],
        )
        t_plan_ms = (time.perf_counter() - t_plan_start) * 1000

        print(f"Normalized TTS Text: '{plan.tts_text if plan else '<MUTED>'}'")
        if plan:
            print(f"Speech Plan: speed={plan.speed}, emotion={plan.emotion}, type={plan.sentence_type}, pause_before={plan.pause_before}s, pause_after={plan.pause_after}s")

        upgraded_chunks = []
        t_synth_start = time.perf_counter()
        if plan and plan.tts_text:
            async for raw_chunk, sr in tts.synthesize(plan.tts_text, voice=plan.voice, speed=plan.speed):
                # Condition audio through AudioProcessor
                t_proc_start = time.perf_counter()
                conditioned_chunk = processor.process(raw_chunk, sr)
                t_proc_ms = (time.perf_counter() - t_proc_start) * 1000
                upgraded_chunks.append(conditioned_chunk)
        t_upgraded_synth = (time.perf_counter() - t_synth_start) * 1000

        upgraded_samples = np.concatenate(upgraded_chunks) if upgraded_chunks else np.array([], dtype=np.float32)
        upgraded_wav_path = output_dir / f"{tc_id}_upgraded.wav"
        if len(upgraded_samples) > 0:
            sf.write(str(upgraded_wav_path), upgraded_samples, 24000)

        # Lip-sync metadata
        lip_meta = VoiceManager._compute_lip_sync_metadata(
            upgraded_samples, 24000, raw_text, kokoro_instance=tts
        )

        # Upgraded metrics
        upg_dc = float(np.mean(upgraded_samples)) if len(upgraded_samples) else 0.0
        upg_peak = float(np.max(np.abs(upgraded_samples))) if len(upgraded_samples) else 0.0
        upg_rms = float(np.sqrt(np.mean(upgraded_samples ** 2))) if len(upgraded_samples) else 0.0
        upg_peak_db = 20.0 * np.log10(upg_peak + 1e-9)
        upg_rms_db = 20.0 * np.log10(upg_rms + 1e-9)

        results.append({
            "id": tc_id,
            "base_synth_ms": round(t_base_synth, 1),
            "upg_synth_ms": round(t_upgraded_synth, 1),
            "plan_ms": round(t_plan_ms, 2),
            "base_duration": round(len(base_samples) / 24000, 2),
            "upg_duration": round(len(upgraded_samples) / 24000, 2),
            "base_peak_db": round(base_peak_db, 2),
            "upg_peak_db": round(upg_peak_db, 2),
            "base_dc": f"{base_dc:.6f}",
            "upg_dc": f"{upg_dc:.6f}",
            "visemes_count": len(lip_meta.get("visemes", [])),
            "tts_text": plan.tts_text if plan else "",
        })

    # Summary Table
    print("\n" + "=" * 85)
    print(f"{'Test Case':<22} | {'Duration (s)':<14} | {'Peak dBFS':<14} | {'Planning Latency':<16} | {'Visemes':<8}")
    print(f"{'':<22} | {'Base -> Upgr':<14} | {'Base -> Upgr':<14} | {'(ms)':<16} | {'Count':<8}")
    print("-" * 85)
    for r in results:
        dur_str = f"{r['base_duration']}s -> {r['upg_duration']}s"
        pk_str = f"{r['base_peak_db']} -> {r['upg_peak_db']}"
        plan_str = f"{r['plan_ms']} ms"
        print(f"{r['id']:<22} | {dur_str:<14} | {pk_str:<14} | {plan_str:<16} | {r['visemes_count']:<8}")
    print("=" * 85)
    print(f"\nAll generated evaluation audio files have been saved to:\n  {output_dir}")


if __name__ == "__main__":
    asyncio.run(run_evaluation())
