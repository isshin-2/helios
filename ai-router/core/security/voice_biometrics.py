import os
import sys
import json
import time
import hashlib
import secrets
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

class VoiceBiometricError(Exception):
    pass

class VoiceBiometricsManager:
    """Local Speaker Verification & Voice Biometrics Gate with PBKDF2 Fallback PIN.
    Strictly zero cloud transmission: all acoustic analysis and centroids remain on disk.
    """

    DEFAULT_STORE_PATH = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "biometrics", "voiceprint.json")
    )
    DEFAULT_BIN_PATH = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "voice_profile.bin")
    )

    SIMILARITY_THRESHOLD = 0.78  # Standard speaker verification acceptance threshold

    def __init__(self, store_path: Optional[str] = None, bin_path: Optional[str] = None):
        self.store_path = store_path or self.DEFAULT_STORE_PATH
        self.bin_path = bin_path or self.DEFAULT_BIN_PATH
        self.profile = self._load_profile()

    def _load_profile(self) -> Dict[str, Any]:
        if os.path.exists(self.store_path):
            try:
                with open(self.store_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        # Fallback to binary voice_profile.bin if present
        if os.path.exists(self.bin_path):
            try:
                import struct
                with open(self.bin_path, "rb") as bf:
                    data = bf.read()
                    if len(data) >= 16 + 768:
                        magic, ts = struct.unpack("<8sd", data[:16])
                        if magic == b"HELIOS_V":
                            centroid = np.frombuffer(data[16:16 + 768], dtype=np.float32).tolist()
                            return {
                                "enrolled": True,
                                "centroid": centroid,
                                "pin_hash": None,
                                "pin_salt": None,
                                "sample_count": 3,
                                "enrolled_at": ts
                            }
            except Exception:
                pass

        return {
            "enrolled": False,
            "centroid": None,
            "pin_hash": None,
            "pin_salt": None,
            "sample_count": 0,
            "enrolled_at": None
        }

    def _save_profile(self):
        os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump(self.profile, f, indent=2)

        # Serialize binary acoustic centroid profile to config/voice_profile.bin
        if self.profile.get("centroid"):
            try:
                os.makedirs(os.path.dirname(self.bin_path), exist_ok=True)
                centroid_arr = np.array(self.profile["centroid"], dtype=np.float32)
                magic = b"HELIOS_V"
                ts = float(self.profile.get("enrolled_at") or time.time())
                import struct
                header = struct.pack("<8sd", magic, ts)
                with open(self.bin_path, "wb") as bf:
                    bf.write(header)
                    bf.write(centroid_arr.tobytes())
            except Exception:
                pass

    def extract_embedding(self, audio_data: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
        """Extracts a normalized 192-dimensional acoustic speaker embedding locally using spectral filterbanks."""
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)

        # Normalize audio amplitude
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            audio_data = audio_data / max_val

        # Frame parameters
        frame_len = int(sample_rate * 0.025)  # 25ms
        hop_len = int(sample_rate * 0.010)    # 10ms

        if len(audio_data) < frame_len:
            audio_data = np.pad(audio_data, (0, frame_len - len(audio_data)))

        # FFT & Mel-filterbank simulation
        num_frames = max(1, (len(audio_data) - frame_len) // hop_len)
        window = np.hanning(frame_len)
        
        frames = []
        for i in range(min(num_frames, 200)):
            start = i * hop_len
            frame = audio_data[start:start + frame_len] * window
            spectrum = np.abs(np.fft.rfft(frame, n=512))
            frames.append(spectrum)

        spectrogram = np.array(frames) # (num_frames, 257)
        
        # Project down to 192-dim embedding (mean + std pooling)
        mean_spec = np.mean(spectrogram, axis=0)[:96]
        std_spec = np.std(spectrogram, axis=0)[:96]
        embedding = np.concatenate([mean_spec, std_spec]) # 192 dims

        # Center and L2 Normalize
        embedding = embedding - np.mean(embedding)
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding

    def record_sample(self, duration_sec: float = 3.0, sample_rate: int = 16000) -> np.ndarray:
        """Records an audio clip from default microphone."""
        try:
            import sounddevice as sd
            print(f"[*] Recording {duration_sec}s sample... (Speak naturally now)")
            audio = sd.rec(int(duration_sec * sample_rate), samplerate=sample_rate, channels=1, dtype='float32')
            sd.wait()
            return audio.flatten()
        except Exception as e:
            raise VoiceBiometricError(f"Microphone recording failed: {e}")

    def enroll_speaker(self, samples: List[np.ndarray], pin: str) -> Dict[str, Any]:
        """Enrolls user with 3 calibration audio samples and sets a fallback PIN."""
        if len(samples) < 3:
            raise VoiceBiometricError("Minimum 3 calibration samples required to construct speaker centroid.")

        embeddings = [self.extract_embedding(sample) for sample in samples]
        # Compute centroid
        centroid = np.mean(embeddings, axis=0)
        centroid = centroid / np.linalg.norm(centroid)

        # Hash fallback PIN with PBKDF2
        salt = secrets.token_hex(16)
        pin_hash = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt.encode("utf-8"), 100000).hex()

        self.profile = {
            "enrolled": True,
            "centroid": centroid.tolist(),
            "pin_hash": pin_hash,
            "pin_salt": salt,
            "sample_count": len(samples),
            "enrolled_at": time.time()
        }
        self._save_profile()
        return {"status": "enrolled", "sample_count": len(samples)}

    def set_fallback_pin(self, pin: str):
        salt = secrets.token_hex(16)
        pin_hash = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
        self.profile["pin_hash"] = pin_hash
        self.profile["pin_salt"] = salt
        self._save_profile()

    def verify_pin(self, pin: str) -> bool:
        if not self.profile.get("pin_hash") or not self.profile.get("pin_salt"):
            return False
        salt = self.profile["pin_salt"]
        calc_hash = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
        return secrets.compare_digest(calc_hash, self.profile["pin_hash"])

    def verify_voice(self, sample: np.ndarray) -> Tuple[bool, float]:
        """Compares sample embedding to stored centroid using Cosine Similarity."""
        if not self.profile.get("enrolled") or not self.profile.get("centroid"):
            raise VoiceBiometricError("No enrolled voiceprint found. Run voice enrollment first.")

        test_emb = self.extract_embedding(sample)
        centroid = np.array(self.profile["centroid"], dtype=np.float32)

        cosine_sim = float(np.dot(test_emb, centroid) / (np.linalg.norm(test_emb) * np.linalg.norm(centroid)))
        is_verified = cosine_sim >= self.SIMILARITY_THRESHOLD
        return is_verified, cosine_sim

    def authenticate_access(self, voice_sample: Optional[np.ndarray] = None, fallback_pin: Optional[str] = None) -> Tuple[bool, str]:
        """Access Gate: Authenticates via voiceprint centroid or fallback PIN."""
        if voice_sample is not None:
            try:
                verified, score = self.verify_voice(voice_sample)
                if verified:
                    return True, f"Voice biometrics authenticated (Score: {score:.3f} >= {self.SIMILARITY_THRESHOLD})"
                # If voice rejects and no PIN is provided, reject immediately
                if fallback_pin is None:
                    return False, f"Voice mismatch (Score: {score:.3f} < {self.SIMILARITY_THRESHOLD})"
            except Exception as e:
                if fallback_pin is None:
                    return False, f"Voice verification failed: {e}"

        if fallback_pin is not None:
            if self.verify_pin(fallback_pin):
                return True, "Authenticated via verified fallback PIN"
            return False, "Invalid fallback PIN"

        return False, "Authentication failed: No valid voiceprint match or PIN provided"

    def is_sensitive_operation(self, operation: str) -> bool:
        """Determines if a system operation or memory command requires biometric verification."""
        op = operation.lower().strip()
        sensitive_keywords = (
            "wipe_memory", "delete_memory", "clear_memory", "nuke_data",
            "format", "drop table", "privileged_exec", "terminal_raw",
            "modify_security", "disable_bridge", "export_secrets"
        )
        return any(k in op for k in sensitive_keywords)

    def gate_sensitive_action(
        self,
        operation: str,
        voice_sample: Optional[np.ndarray] = None,
        pin: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Gates sensitive vector memory and high-risk system commands behind biometric matches,
        falling back to local PIN prompt if voice rejects or is unavailable.
        """
        if not self.is_sensitive_operation(operation):
            return True, f"Operation '{operation}' is non-sensitive; authorization granted."

        if not self.profile.get("enrolled"):
            return True, f"Warning: Biometrics not enrolled; operation '{operation}' permitted."

        return self.authenticate_access(voice_sample=voice_sample, fallback_pin=pin)

_global_voice_biometrics = None

def get_voice_biometrics() -> VoiceBiometricsManager:
    global _global_voice_biometrics
    if _global_voice_biometrics is None:
        _global_voice_biometrics = VoiceBiometricsManager()
    return _global_voice_biometrics
