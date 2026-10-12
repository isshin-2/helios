"""Interactive Local Voice Biometrics Verification & Calibration Runner.
Handles zero-cloud speaker enrollment, centroid calculation, cosine similarity scoring, and fallback PIN verification.
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import time
import argparse
import numpy as np

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AI_ROUTER_DIR = os.path.join(BASE_DIR, "ai-router")
if AI_ROUTER_DIR not in sys.path:
    sys.path.insert(0, AI_ROUTER_DIR)

from core.security.voice_biometrics import VoiceBiometricsManager, VoiceBiometricError

def run_synthetic_test(manager: VoiceBiometricsManager):
    """Automated synthetic verification test without requiring an active live microphone."""
    print("[*] Running Voice Biometrics Self-Test (Synthetic Calibration)...")
    sample_rate = 16000
    t = np.linspace(0, 3.0, sample_rate * 3, endpoint=False, dtype=np.float32)

    def synth_voice(f0: float, seed: int) -> np.ndarray:
        np.random.seed(seed)
        signal = np.sin(2 * np.pi * f0 * t) + 0.5 * np.sin(2 * np.pi * 2 * f0 * t) + 0.25 * np.sin(2 * np.pi * 3 * f0 * t)
        noise = np.random.normal(0, 0.05, len(t)).astype(np.float32)
        return (signal + noise).astype(np.float32)

    # Enrolled Speaker 1 (F0 = 140 Hz)
    sample1 = synth_voice(140.0, 101)
    sample2 = synth_voice(140.0, 102)
    sample3 = synth_voice(140.0, 103)

    manager.enroll_speaker([sample1, sample2, sample3], pin="1337")
    print("  [OK] Successfully enrolled 3 calibration samples and established voiceprint centroid.")

    # Match test (Same speaker with new phrase/noise)
    test_match = synth_voice(140.0, 104)
    verified, score = manager.verify_voice(test_match)
    print(f"  [OK] Same-Speaker Similarity: {score:.4f} (Threshold: {manager.SIMILARITY_THRESHOLD}) -> Verified: {verified}")
    assert verified is True, f"Expected verified=True, got {verified} with score {score}"

    # Non-match test (Impostor Speaker with F0 = 320 Hz)
    impostor = synth_voice(320.0, 201)
    verified_imp, score_imp = manager.verify_voice(impostor)
    print(f"  [OK] Impostor Similarity: {score_imp:.4f} -> Verified: {verified_imp}")
    assert verified_imp is False, f"Expected impostor rejected, got score {score_imp}"

    # Fallback PIN test
    pin_ok = manager.verify_pin("1337")
    pin_bad = manager.verify_pin("9999")
    print(f"  [OK] Fallback PIN '1337': {pin_ok} | Invalid PIN '9999': {pin_bad}")
    assert pin_ok is True and pin_bad is False

    print("\n[OK] Voice Biometrics & Access Gate verification passed 100%.")

def run_interactive_enrollment(manager: VoiceBiometricsManager):
    print("=" * 70)
    print("  HELIOS Local Voice Biometrics Enrollment & Calibration Loop")
    print("  Privacy Notice: Zero cloud transmission. All audio processed on CPU.")
    print("=" * 70)

    try:
        import sounddevice
    except ImportError:
        print("[!] sounddevice library not available. Falling back to synthetic test.")
        run_synthetic_test(manager)
        return

    samples = []
    print("\nYou will be prompted to record 3 audio calibration samples (3 seconds each).")
    input("Press Enter when ready to record Sample 1...")
    samples.append(manager.record_sample(3.0))

    input("\nPress Enter when ready to record Sample 2...")
    samples.append(manager.record_sample(3.0))

    input("\nPress Enter when ready to record Sample 3...")
    samples.append(manager.record_sample(3.0))

    pin = input("\nEnter a 4-8 digit Fallback PIN (for noisy environments): ").strip()
    while len(pin) < 4:
        pin = input("PIN must be at least 4 digits: ").strip()

    print("\n[*] Processing acoustic features and computing speaker centroid...")
    res = manager.enroll_speaker(samples, pin=pin)
    print(f"[OK] Voiceprint successfully enrolled! Centroid computed from {res['sample_count']} samples.")

    print("\n[*] Testing live speaker verification...")
    input("Press Enter and speak a phrase to verify authentication...")
    test_audio = manager.record_sample(3.0)
    verified, score = manager.verify_voice(test_audio)
    
    print(f"\nVerification Results:")
    print(f"  - Cosine Similarity Score : {score:.4f}")
    print(f"  - Acceptance Threshold    : {manager.SIMILARITY_THRESHOLD}")
    print(f"  - Gate Status             : {'[ACCESS GRANTED]' if verified else '[ACCESS DENIED - FALLBACK PIN REQUIRED]'}")

    if not verified:
        pin_input = input("Enter your Fallback PIN to unlock: ").strip()
        if manager.verify_pin(pin_input):
            print("[OK] Fallback PIN accepted. Access Granted.")
        else:
            print("[!] Fallback PIN incorrect. Access Denied.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Run automated synthetic test suite")
    args = parser.parse_args()

    vbm = VoiceBiometricsManager()
    if args.test or not sys.stdin.isatty():
        run_synthetic_test(vbm)
    else:
        run_interactive_enrollment(vbm)
