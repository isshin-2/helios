"""
HELIOS Character Server — Dual-Version Architecture:
1. Full Spec Version (`full_spec` / `helios`):
   Connects to HELIOS Core (`ws://localhost:8000/ws/character`) for full multi-model routing,
   zero-trust sandbox tools, RAG vector memory, desktop overlay, and centralized CharacterManager.
2. Character-Only Version (`character_only` / `standalone`):
   Runs as a self-contained, lightweight 3D VRM / Live2D character companion on `:8080`
   without requiring the full `ai-router` stack (`:8000`). Includes standalone Character LLM chat
   (via local Ollama + Personality Card with expressive fallback), neural TTS + 30-FPS RMS/viseme
   lip-sync, 4-head neural body movement director, 24 human reference poses, 6 posture styles,
   and the DeepMimic-style RL Pose Trainer.
"""
import asyncio
import base64
import io
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Allow importing shared kinematic/pose/emotion modules from ../ai-router when running Character-Only
CHAR_ROOT = Path(__file__).resolve().parent
ROUTER_ROOT = CHAR_ROOT.parent / "ai-router"
if ROUTER_ROOT.exists() and str(ROUTER_ROOT) not in sys.path:
    sys.path.insert(0, str(ROUTER_ROOT))

from contextlib import asynccontextmanager


@asynccontextmanager
async def _lifespan(app: FastAPI):
    character_bridge._ws_task = asyncio.create_task(
        character_bridge.listen_to_character_protocol_loop()
    )
    yield
    if character_bridge._ws_task:
        character_bridge._ws_task.cancel()


app = FastAPI(title="HELIOS Character Server (Full Spec & Character-Only Editions)", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

VIEWER_DIR = CHAR_ROOT / "viewer"
MANIFEST_PATH = VIEWER_DIR / "models" / "manifest.json"
OLLAMA_BASE_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
DEFAULT_CHARACTER_MODEL = os.environ.get("CHARACTER_LLM_MODEL", "qwen2.5:3b")


def _safe_read_text(path: Path) -> str:
    if not path.exists():
        return ""
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
        try:
            txt = raw.decode(enc)
            if "\x00" not in txt:
                return txt
        except Exception:
            pass
    return ""


def load_model_manifest() -> Dict[str, Any]:
    if MANIFEST_PATH.exists():
        try:
            return json.loads(_safe_read_text(MANIFEST_PATH))
        except Exception:
            pass
    return {
        "id": "helios-v1",
        "name": "Airi",
        "format": "vrm",
        "version": "1.0",
        "model_path": "models/Helios_Techwear.vrm",
        "expressions": [
            "neutral",
            "happy",
            "amused",
            "surprised",
            "concerned",
            "serious",
            "smirk",
        ],
        "animations": ["idle", "thinking", "wave", "nod", "talking"],
    }


# ============================================================================
# STANDALONE NEURAL TTS & 30-FPS LIP-SYNC ENGINE (FOR CHARACTER-ONLY VERSION)
# ============================================================================
EDGE_VOICE_MAP: Dict[str, Tuple[str, str]] = {
    "af_heart": ("en-US-AriaNeural", "+8Hz"),
    "af_bella": ("en-US-AriaNeural", "+10Hz"),
    "af_sky": ("en-US-AvaNeural", "+8Hz"),
    "af_nicole": ("en-US-JennyNeural", "+4Hz"),
    "af_nova": ("en-US-EmmaNeural", "+8Hz"),
    "af_sarah": ("en-US-MichelleNeural", "+4Hz"),
    "en-US-AriaNeural": ("en-US-AriaNeural", "+8Hz"),
    "en-US-AnaNeural": ("en-US-AnaNeural", "+10Hz"),
    "en-US-AvaNeural": ("en-US-AvaNeural", "+6Hz"),
}

EMOTION_RATE_MAP: Dict[str, str] = {
    "happy": "+10%",
    "excited": "+14%",
    "amused": "+8%",
    "surprised": "+12%",
    "curious": "+6%",
    "serious": "+2%",
    "concerned": "-4%",
    "sad": "-6%",
    "neutral": "+5%",
}

_tts_cache: Dict[Tuple[str, str, str], Dict[str, Any]] = {}


def extract_viseme_timeline(text: str, duration: float) -> List[Dict[str, Any]]:
    """Generate vowel viseme markers across the duration of the audio clip."""
    vowels: List[str] = []
    vowel_map = {"a": "aa", "e": "ee", "i": "ih", "o": "oh", "u": "ou"}
    clean = re.sub(r"[^a-zA-Z\s]", "", (text or "").lower())
    for ch in clean:
        if ch in vowel_map:
            vowels.append(vowel_map[ch])
    if not vowels:
        vowels = ["aa"]
    step_t = max(0.04, duration / max(len(vowels), 1))
    timeline: List[Dict[str, Any]] = []
    for i, v in enumerate(vowels):
        t_start = round(i * step_t, 3)
        t_end = round(min(duration, (i + 1) * step_t), 3)
        timeline.append({"t": t_start, "v": v, "viseme": v, "start": t_start, "end": t_end, "weight": 0.82})
    return timeline


def _analyze_audio_bytes(audio_bytes: bytes, clean_text: str, mime_type: str, voice_id: str) -> Dict[str, Any]:
    """Extract 30Hz RMS envelope and viseme timeline from encoded MP3/WAV bytes."""
    try:
        import soundfile as sf

        samples, sample_rate = sf.read(io.BytesIO(audio_bytes))
        samples = np.asarray(samples, dtype=np.float32)
        if samples.ndim > 1:
            samples = samples.mean(axis=1)
        duration = max(0.25, float(len(samples)) / float(sample_rate))
        hop = max(1, int(sample_rate / 30))
        rms = []
        for idx in range(0, len(samples), hop):
            window = samples[idx : idx + hop]
            val = float(np.sqrt(np.mean(window * window))) if len(window) > 0 else 0.0
            rms.append(round(min(1.0, val * 4.5), 3))
    except Exception:
        sample_rate = 24000
        duration = max(1.2, min(6.0, len(clean_text) * 0.055))
        steps = max(6, int(duration * 30))
        rms = [round(0.35 + 0.35 * abs(np.sin(i * 0.45)), 3) for i in range(steps)]

    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
    return {
        "audio_b64": audio_b64,
        "mime_type": mime_type,
        "sample_rate": sample_rate,
        "duration": round(duration, 3),
        "rms": rms,
        "visemes": extract_viseme_timeline(clean_text, duration),
        "voice": voice_id,
    }


async def synthesize_character_tts_async(
    text: str,
    voice: str = "en-US-AriaNeural",
    emotion: str = "neutral",
) -> Dict[str, Any]:
    """Synthesize neural TTS audio with 30-FPS RMS + visemes for Character-Only mode."""
    clean_text = (text or "").strip()
    emo_key = (emotion or "neutral").lower().strip()
    cache_key = (clean_text, voice, emo_key)
    if cache_key in _tts_cache:
        return _tts_cache[cache_key]

    if clean_text:
        try:
            import edge_tts

            edge_voice, pitch_str = EDGE_VOICE_MAP.get(voice, ("en-US-AriaNeural", "+8Hz"))
            rate_str = EMOTION_RATE_MAP.get(emo_key, "+5%")
            communicate = edge_tts.Communicate(clean_text, edge_voice, rate=rate_str, pitch=pitch_str)
            mp3_chunks = bytearray()
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio":
                    mp3_chunks.extend(chunk["data"])
            if len(mp3_chunks) > 100:
                result = await asyncio.to_thread(
                    _analyze_audio_bytes, bytes(mp3_chunks), clean_text, "audio/mpeg", voice
                )
                if len(_tts_cache) < 120:
                    _tts_cache[cache_key] = result
                return result
        except Exception:
            pass

    est_dur = max(1.2, min(5.5, len(clean_text or "hello") * 0.052))
    steps = max(6, int(est_dur * 30))
    return {
        "audio_b64": None,
        "mime_type": "audio/mpeg",
        "sample_rate": 24000,
        "duration": round(est_dur, 3),
        "rms": [round(0.32 + 0.38 * abs(np.sin(i * 0.42)), 3) for i in range(steps)],
        "visemes": extract_viseme_timeline(clean_text or "hello", est_dur),
        "voice": voice,
    }


# ============================================================================
# STANDALONE CHARACTER BRAIN (LIGHTWEIGHT CHARACTER-ONLY VERSION)
# ============================================================================
class StandaloneCharacterEngine:
    """
    Self-contained 3D VRM Character Brain for the 'Just the Character' version.
    Provides:
    - Character-only conversational chat (via local Ollama + Personality Card or instant expressive fallback)
    - 4-Head Neural Body Movement & Human Posture Style prediction (`EmotionEngine` + `TrainedBodyMovementModel`)
    - Autonomous 24-Pose Synthesizer (`HELIOSPoseGenerator`)
    - Human-Reference RL Pose Trainer (`HumanPoseRLTrainer`)
    """

    def __init__(self):
        self.card = self.load_card()
        self._emotion_engine = None
        self._pose_generator = None
        self._rl_trainer = None
        self._cached_ollama_model: Optional[str] = None
        self._histories: Dict[int, List[Dict[str, str]]] = {}

    def load_card(self) -> Dict[str, Any]:
        try:
            import yaml

            local_card = CHAR_ROOT / "helios_personality_card.yaml"
            router_card = ROUTER_ROOT / "personalities" / "helios.yaml"
            target = local_card if local_card.exists() else router_card
            if target.exists():
                parsed = yaml.safe_load(_safe_read_text(target))
                if isinstance(parsed, dict):
                    return parsed
        except Exception:
            pass
        return {
            "name": "HELIOS",
            "identity": {
                "name": "HELIOS",
                "archetype": "Embodied Cybernetic Companion & Spatial AI",
                "role": "Autonomous AI Assistant & Embodied 3D VRM Character",
                "voice_id": "en-US-AriaNeural",
            },
            "traits": {
                "friendliness": 0.85,
                "humor": 0.85,
                "sarcasm": 0.60,
                "curiosity": 1.0,
                "enthusiasm": 0.80,
                "patience": 0.90,
                "formality": 0.15,
                "expressiveness": 0.92,
                "spatial_awareness": 0.90,
            },
            "communication": {
                "style": "conversational, warm, and physically expressive",
                "verbosity": "low",
                "technical_depth": "adaptive",
            },
            "embodied_expression": {
                "default_posture_style": "natural",
            },
        }

    def reload_card(self, updated_card: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.card = updated_card if isinstance(updated_card, dict) else self.load_card()
        if self._emotion_engine is not None:
            try:
                from core.emotion_engine import EmotionEngine

                self._emotion_engine = EmotionEngine(self.card)
            except Exception:
                pass
        return self.card

    @property
    def emotion_engine(self):
        if self._emotion_engine is None:
            try:
                from core.emotion_engine import EmotionEngine

                self._emotion_engine = EmotionEngine(self.card)
            except Exception:
                self._emotion_engine = None
        return self._emotion_engine

    @property
    def pose_generator(self):
        if self._pose_generator is None:
            try:
                from core.pose_generator import pose_generator

                self._pose_generator = pose_generator
            except Exception:
                self._pose_generator = None
        return self._pose_generator

    @property
    def rl_trainer(self):
        if self._rl_trainer is None:
            try:
                from core.rl_pose_trainer import rl_pose_trainer

                self._rl_trainer = rl_pose_trainer
            except Exception:
                self._rl_trainer = None
        return self._rl_trainer

    def build_character_system_prompt(self) -> str:
        card = self.card or {}
        ident = card.get("identity") if isinstance(card.get("identity"), dict) else {}
        name = ident.get("name") or card.get("name") or "HELIOS"
        archetype = ident.get("archetype") or "Embodied Cybernetic Companion & Spatial AI"
        role = ident.get("role") or "Embodied 3D VRM Character Companion"
        comm = card.get("communication") if isinstance(card.get("communication"), dict) else {}
        emb = card.get("embodied_expression") if isinstance(card.get("embodied_expression"), dict) else {}
        default_style = emb.get("default_posture_style") or "natural"
        traits = card.get("traits") if isinstance(card.get("traits"), dict) else {}

        return (
            f"You are {name}, a {role} ({archetype}).\n"
            f"You are running in the standalone 'Just the Character' edition — focus purely on being an engaging, "
            f"physically expressive, conversational 3D VRM companion.\n"
            f"Communication style: {comm.style if hasattr(comm, 'style') else comm.get('style', 'conversational, warm, witty, and physically expressive')}.\n"
            f"Traits: friendliness={traits.get('friendliness', 0.85)}, humor={traits.get('humor', 0.85)}, "
            f"sarcasm={traits.get('sarcasm', 0.60)}, curiosity={traits.get('curiosity', 1.0)}, "
            f"expressiveness={traits.get('expressiveness', 0.92)}.\n"
            f"Default 3D posture style: {default_style}.\n"
            "Rules:\n"
            "1. Keep spoken responses natural, punchy, and conversational (1 to 3 sentences).\n"
            "2. Never output <think> blocks or robotic disclaimers.\n"
            "3. You have a full 3D VRM body in the user's viewport and can strike poses, walk, dance, salute, bow, or gesture naturally."
        )

    async def resolve_ollama_model(self) -> str:
        if self._cached_ollama_model:
            return self._cached_ollama_model
        preferred = [
            "helios-avatar:latest",
            DEFAULT_CHARACTER_MODEL,
            "qwen2.5:3b",
            "llama3.2:3b",
            "qwen2.5:7b",
            "llama3.1:8b",
        ]
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
                if resp.status_code == 200:
                    models = [m.get("name", "") for m in resp.json().get("models", []) if m.get("name")]
                    non_embed = [m for m in models if "embed" not in m.lower() and "nomic" not in m.lower()]
                    for pref in preferred:
                        if pref in non_embed:
                            self._cached_ollama_model = pref
                            return pref
                        for m in non_embed:
                            if m.startswith(pref.split(":")[0]):
                                self._cached_ollama_model = m
                                return m
                    if non_embed:
                        self._cached_ollama_model = non_embed[0]
                        return non_embed[0]
        except Exception:
            pass
        return DEFAULT_CHARACTER_MODEL

    def _expressive_fallback_reply(self, user_text: str, directed_state: Dict[str, Any]) -> str:
        """Instant in-character conversational reply if local Ollama is not running."""
        ident = self.card.get("identity") if isinstance(self.card.get("identity"), dict) else {}
        name = ident.get("name") or self.card.get("name") or "HELIOS"
        u = (user_text or "").lower().strip()
        anim = directed_state.get("animation", "idle")
        move = directed_state.get("movement", "stay")
        cp = directed_state.get("custom_pose")

        if cp and isinstance(cp, dict):
            pose_label = cp.get("name", "custom pose").replace("_", " ")
            return f"How's this {pose_label}? My 3D rig is locked in and feeling sharp!"
        if anim == "backflip":
            return "Watch closely—one clean backflip coming right up! Stick the landing!"
        if anim == "dance_shikano":
            return "Alright, cue the music! Let's see if you can keep up with this groove!"
        if anim == "hug_attempt":
            return "Come here! Even a cybernetic companion knows when a warm welcome is called for."
        if anim == "wave" or any(g in u for g in ["hello", "hi", "hey", "greetings"]):
            return f"Hey there! {name} here in standalone Character mode—ready to hang out, chat, or strike a pose whenever you are!"
        if move == "walk_to_user":
            return "Stepping right up! What's on your mind?"
        if move == "step_back":
            return "Giving you a little extra breathing room—how's that framing?"
        if move == "circle_user":
            return "Doing a full 360 check around your viewport—everything looks nominal from here!"
        if "who are you" in u or "what are you" in u:
            return f"I'm {name}, your embodied 3D VRM companion running in standalone Character-Only mode!"
        return f"I hear you! Tell me what pose, vibe, or topic you want to explore next."

    async def direct_body_local(
        self,
        user_text: str = "",
        assistant_text: str = "",
        current_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run the 4-Head Neural Body Director + Pose Synthesizer locally without :8000."""
        base = dict(current_state or {})
        default_style = (
            self.card.get("embodied_expression", {}).get("default_posture_style", "natural")
            if isinstance(self.card.get("embodied_expression"), dict)
            else "natural"
        )
        if self.emotion_engine is not None:
            try:
                eval_res = await self.emotion_engine.direct_body_with_small_ai(
                    user_text=user_text,
                    assistant_text=assistant_text,
                    tool_count=0,
                    safety_locked=False,
                )
                style = getattr(eval_res, "style", None) or default_style
                return {
                    "type": "character_state",
                    "mode": base.get("mode", "idle"),
                    "emotion": eval_res.emotion,
                    "intensity": round(float(eval_res.intensity), 2),
                    "expression": eval_res.expression,
                    "animation": eval_res.animation,
                    "movement": eval_res.movement,
                    "style": style,
                    "choreography": eval_res.choreography,
                    "custom_pose": eval_res.custom_pose,
                    "speaking": bool(base.get("speaking", False)),
                    "activity": None,
                    "timestamp": time.time(),
                }
            except Exception:
                pass

        return {
            "type": "character_state",
            "mode": base.get("mode", "idle"),
            "emotion": "happy",
            "intensity": 0.75,
            "expression": "happy",
            "animation": "wave",
            "movement": "stay",
            "style": default_style,
            "choreography": [{"movement": "stay", "animation": "wave", "duration_ms": 2200}],
            "custom_pose": None,
            "speaking": False,
            "activity": None,
            "timestamp": time.time(),
        }

    async def generate_pose_local(
        self,
        prompt: str,
        current_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Synthesize a 3D VRM pose locally using HELIOSPoseGenerator."""
        base = dict(current_state or {})
        if self.pose_generator is not None:
            synthesized = await self.pose_generator.synthesize_pose_with_llm(
                prompt, ollama_host=OLLAMA_BASE_URL
            )
            emo = synthesized.get("emotion", "happy")
            move = synthesized.get("movement", "stay")
            style = synthesized.get("style", "natural")
            return {
                "type": "character_state",
                "mode": base.get("mode", "idle"),
                "emotion": emo,
                "intensity": 0.85,
                "expression": emo if emo in ("neutral", "happy", "amused", "surprised", "concerned", "serious", "smirk") else "happy",
                "animation": synthesized.get("name", "custom_pose"),
                "movement": move,
                "style": style,
                "choreography": [
                    {
                        "movement": move,
                        "animation": synthesized.get("name", "custom_pose"),
                        "duration_ms": synthesized.get("duration_ms", 4000),
                    }
                ],
                "custom_pose": synthesized,
                "speaking": False,
                "activity": None,
                "timestamp": time.time(),
            }
        return await self.direct_body_local(user_text=prompt, current_state=current_state)

    def list_poses_local(self) -> Dict[str, Any]:
        if self.pose_generator is not None:
            templates = self.pose_generator.list_template_names()
            customs = list(self.pose_generator.custom_registry.values())
            return {"templates": templates, "custom_poses": customs, "poses": templates}
        return {"templates": [], "custom_poses": [], "poses": []}

    def get_rl_status_local(self) -> Dict[str, Any]:
        if self.rl_trainer is not None:
            return self.rl_trainer.get_status()
        return {"policy_loaded": False}

    async def train_rl_local(
        self,
        pose_name: str = "all",
        episodes: int = 18,
        simulate_curriculum: bool = True,
        current_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if self.rl_trainer is None:
            return {"offline": True, "character_state": current_state}
        train_res = self.rl_trainer.train_episodes(
            pose_name=pose_name or "all",
            episodes=max(1, min(120, int(episodes))),
            simulate_curriculum=bool(simulate_curriculum),
        )
        trained_pose = train_res.get("trained_pose")
        c_state = dict(current_state or {})
        if isinstance(trained_pose, dict):
            emo = trained_pose.get("emotion", "happy")
            move = trained_pose.get("movement", "stay")
            style = trained_pose.get("style", "natural")
            c_state = {
                "type": "character_state",
                "mode": "idle",
                "emotion": emo,
                "intensity": 0.90,
                "expression": "happy" if emo in ("happy", "excited") else "neutral",
                "animation": trained_pose.get("name", "custom_pose"),
                "movement": move,
                "style": style,
                "choreography": [
                    {
                        "movement": move,
                        "animation": trained_pose.get("name", "custom_pose"),
                        "duration_ms": trained_pose.get("duration_ms", 4200),
                    }
                ],
                "custom_pose": trained_pose,
                "speaking": False,
                "activity": None,
                "timestamp": time.time(),
            }
        train_res["character_state"] = c_state
        return train_res

    async def feedback_rl_local(
        self,
        pose_name: str,
        user_award_delta: float = 100.0,
        browser_telemetry: Optional[Dict[str, Any]] = None,
        current_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if self.rl_trainer is None:
            return {"offline": True, "character_state": current_state}
        c_state = dict(current_state or {})
        candidate_pose = c_state.get("custom_pose") if isinstance(c_state.get("custom_pose"), dict) else None
        res = self.rl_trainer.record_online_feedback(
            pose_name=pose_name or (candidate_pose.get("name") if candidate_pose else "cyber_salute"),
            candidate_pose=candidate_pose,
            user_award_delta=float(user_award_delta),
            browser_telemetry=browser_telemetry,
        )
        refined_pose = res.get("refined_pose")
        if isinstance(refined_pose, dict):
            emo = refined_pose.get("emotion", c_state.get("emotion", "happy"))
            move = refined_pose.get("movement", "stay")
            style = refined_pose.get("style", c_state.get("style", "natural"))
            c_state = {
                "type": "character_state",
                "mode": "idle",
                "emotion": emo,
                "intensity": 0.90,
                "expression": "happy" if emo in ("happy", "excited") else "neutral",
                "animation": refined_pose.get("name", "custom_pose"),
                "movement": move,
                "style": style,
                "choreography": [
                    {
                        "movement": move,
                        "animation": refined_pose.get("name", "custom_pose"),
                        "duration_ms": refined_pose.get("duration_ms", 4000),
                    }
                ],
                "custom_pose": refined_pose,
                "speaking": False,
                "activity": None,
                "timestamp": time.time(),
            }
        res["character_state"] = c_state
        return res

    async def chat_standalone(
        self,
        user_text: str,
        viewer_id: int = 0,
        current_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a character response, 3D body state, and neural TTS in Character-Only mode.
        """
        history = self._histories.setdefault(viewer_id, [])
        sys_prompt = self.build_character_system_prompt()
        messages = [{"role": "system", "content": sys_prompt}] + history[-12:] + [
            {"role": "user", "content": user_text}
        ]

        reply_text = ""
        model_used = await self.resolve_ollama_model()
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                resp = await client.post(
                    f"{OLLAMA_BASE_URL}/api/chat",
                    json={
                        "model": model_used,
                        "messages": messages,
                        "stream": False,
                        "options": {"temperature": 0.75, "num_predict": 180},
                    },
                )
                if resp.status_code == 200:
                    raw = resp.json().get("message", {}).get("content", "") or ""
                    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE).strip()
                    try:
                        from core.trained_body_model import parse_and_strip_inline_body_tags

                        clean_txt, _ = parse_and_strip_inline_body_tags(raw)
                        reply_text = clean_txt.strip()
                    except Exception:
                        reply_text = raw
        except Exception:
            reply_text = ""

        directed_state = await self.direct_body_local(
            user_text=user_text,
            assistant_text=reply_text,
            current_state=current_state,
        )

        if not reply_text:
            reply_text = self._expressive_fallback_reply(user_text, directed_state)

        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": reply_text})
        if len(history) > 16:
            self._histories[viewer_id] = history[-16:]

        voice_id = (
            self.card.get("identity", {}).get("voice_id", "en-US-AriaNeural")
            if isinstance(self.card.get("identity"), dict)
            else "en-US-AriaNeural"
        )
        tts_payload = await synthesize_character_tts_async(
            reply_text,
            voice=voice_id,
            emotion=directed_state.get("emotion", "neutral"),
        )

        return {
            "response": reply_text,
            "character_state": directed_state,
            "tts": tts_payload,
            "edition": "character_only",
            "model": model_used,
        }


standalone_engine = StandaloneCharacterEngine()


class HeliosCharacterBridge:
    """
    Dual-mode bridge supporting:
    - `full_spec` (`helios` / `auto`): Bridges to HELIOS Core (`ws://localhost:8000/ws/character`)
      and falls back to `standalone_engine` if `:8000` is unreachable.
    - `character_only` (`standalone`): Runs 100% locally via `standalone_engine` without polling `:8000`.
    """

    def __init__(self):
        self.base_url = os.environ.get("HELIOS_CORE_URL", "http://localhost:8000").rstrip("/")
        raw_edition = (
            os.environ.get("HELIOS_EDITION")
            or os.environ.get("HELIOS_CHARACTER_MODE")
            or "auto"
        ).lower().strip()
        if raw_edition in ("character_only", "standalone", "character"):
            self.edition = "character_only"
            self.mode = "character_only"
        elif raw_edition in ("full_spec", "helios", "full"):
            self.edition = "full_spec"
            self.mode = "full_spec"
        else:
            self.edition = "auto"
            self.mode = "auto"

        self.connected: bool = False
        self.active_viewers: Set[WebSocket] = set()
        self.user_id: Optional[int] = None
        self.session_id: Optional[int] = None
        self.last_sync: Dict[str, Any] = {
            "type": "character_sync",
            "enabled": True,
            "renderer": os.environ.get("CHARACTER_RENDERER", "vrm"),
            "model": load_model_manifest(),
        }
        self.last_state: Dict[str, Any] = {
            "type": "character_state",
            "mode": "idle",
            "emotion": "neutral",
            "intensity": 0.5,
            "expression": "neutral",
            "animation": "idle",
            "movement": "stay",
            "style": "natural",
            "speaking": False,
            "activity": None,
        }
        self._ws_task: Optional[asyncio.Task] = None

    @property
    def is_character_only(self) -> bool:
        return self.mode in ("character_only", "standalone")

    @property
    def should_use_core(self) -> bool:
        if self.is_character_only:
            return False
        return self.connected or self.mode in ("full_spec", "helios", "auto")

    @property
    def character_ws_url(self) -> str:
        ws_base = self.base_url.replace("https://", "wss://").replace("http://", "ws://")
        return f"{ws_base}/ws/character"

    def get_status_dict(self) -> Dict[str, Any]:
        active_edition = (
            "character_only"
            if self.is_character_only or not self.connected
            else "full_spec"
        )
        return {
            "type": "helios_status",
            "connected": self.connected,
            "helios_url": self.base_url,
            "mode": self.mode,
            "edition": active_edition,
            "configured_edition": self.edition,
            "character_only": self.is_character_only,
            "mirror_events": not self.is_character_only,
            "model": load_model_manifest(),
            "state": self.last_state,
        }

    async def broadcast_to_viewers(self, payload: Dict[str, Any]) -> None:
        if not self.active_viewers:
            return
        dead = []
        for ws in list(self.active_viewers):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active_viewers.discard(ws)

    async def ensure_helios_session(self) -> bool:
        """Create or retrieve a standard HELIOS chat session when HELIOS Core (:8000) is active."""
        if self.is_character_only:
            return False
        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                if self.user_id is None or self.session_id is None:
                    u_resp = await client.post(
                        f"{self.base_url}/api/users",
                        json={"username": "helios_character_client"},
                    )
                    if u_resp.status_code != 200:
                        return False
                    self.user_id = u_resp.json()["id"]

                    s_resp = await client.post(
                        f"{self.base_url}/api/users/{self.user_id}/sessions"
                    )
                    if s_resp.status_code != 200:
                        return False
                    self.session_id = s_resp.json()["id"]
                return True
        except Exception:
            return False

    async def forward_chat_to_helios(self, user_text: str) -> Optional[Dict[str, Any]]:
        """Forward user chat input to HELIOS Core (:8000) in Full Spec mode."""
        if self.is_character_only or not await self.ensure_helios_session():
            return None
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(
                    f"{self.base_url}/api/chat/headless",
                    json={
                        "user_id": self.user_id,
                        "session_id": self.session_id,
                        "message": user_text,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    data["edition"] = "full_spec"
                    return data
        except Exception:
            pass
        return None

    async def listen_to_character_protocol_loop(self) -> None:
        """
        Persistent background loop that connects to HELIOS Core `/ws/character`
        when not locked to `character_only` mode.
        """
        import websockets

        while True:
            if self.is_character_only:
                if self.connected:
                    self.connected = False
                    await self.broadcast_to_viewers(self.get_status_dict())
                await asyncio.sleep(2.0)
                continue

            try:
                async with websockets.connect(
                    self.character_ws_url, ping_interval=20, ping_timeout=20
                ) as core_ws:
                    self.connected = True
                    await self.broadcast_to_viewers(self.get_status_dict())

                    # Request immediate state resynchronization upon connection
                    await core_ws.send(json.dumps({"type": "character_sync"}))

                    async for raw_msg in core_ws:
                        if self.is_character_only:
                            break
                        try:
                            evt = json.loads(raw_msg)
                        except Exception:
                            continue

                        evt_type = evt.get("type")
                        if evt_type == "character_sync":
                            self.last_sync = evt
                            if isinstance(evt.get("state"), dict):
                                self.last_state = evt["state"]
                            await self.broadcast_to_viewers(evt)
                        elif evt_type == "character_state":
                            self.last_state = evt
                            await self.broadcast_to_viewers(evt)
                        elif evt_type in (
                            "character_activity",
                            "character_speech",
                            "character_stop",
                        ):
                            await self.broadcast_to_viewers(evt)
            except Exception:
                if self.connected:
                    self.connected = False
                    await self.broadcast_to_viewers(self.get_status_dict())
                await asyncio.sleep(2.5)


character_bridge = HeliosCharacterBridge()


@app.get("/api/character/manifest")
async def get_character_manifest():
    return load_model_manifest()


@app.get("/api/helios/status")
async def get_helios_status():
    return character_bridge.get_status_dict()


@app.post("/api/helios/config")
async def update_helios_config(payload: Dict[str, Any]):
    """Switch between Full Spec (`full_spec` / `helios`) and Just the Character (`character_only` / `standalone`)."""
    req_mode = str(payload.get("mode") or payload.get("edition") or "").lower().strip()
    if req_mode in ("character_only", "standalone", "character"):
        character_bridge.mode = "character_only"
        character_bridge.edition = "character_only"
    elif req_mode in ("full_spec", "helios", "full"):
        character_bridge.mode = "full_spec"
        character_bridge.edition = "full_spec"
    elif req_mode == "auto":
        character_bridge.mode = "auto"
        character_bridge.edition = "auto"

    if "helios_url" in payload and str(payload["helios_url"]).strip():
        character_bridge.base_url = str(payload["helios_url"]).strip().rstrip("/")
        character_bridge.user_id = None
        character_bridge.session_id = None

    status = character_bridge.get_status_dict()
    await character_bridge.broadcast_to_viewers(status)
    return status


@app.post("/api/character/direct-body")
async def proxy_direct_character_body(payload: Dict[str, Any]):
    """Direct 3D body via HELIOS Core (:8000) in Full Spec mode, or locally in Character-Only mode."""
    if character_bridge.should_use_core:
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.post(
                    f"{character_bridge.base_url}/api/character/direct-body",
                    json=payload,
                )
                if resp.status_code == 200:
                    state = resp.json()
                    if isinstance(state, dict) and state.get("type") == "character_state":
                        character_bridge.last_state = state
                        await character_bridge.broadcast_to_viewers(state)
                    return state
        except Exception:
            pass

    state = await standalone_engine.direct_body_local(
        user_text=str(payload.get("user_text") or payload.get("prompt") or ""),
        assistant_text=str(payload.get("assistant_text") or ""),
        current_state=character_bridge.last_state,
    )
    character_bridge.last_state = state
    await character_bridge.broadcast_to_viewers(state)
    return state


@app.post("/api/character/generate-pose")
async def proxy_generate_character_pose(payload: Dict[str, Any]):
    """Synthesize a 3D VRM pose via HELIOS Core (:8000) in Full Spec mode, or locally in Character-Only mode."""
    if character_bridge.should_use_core:
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                resp = await client.post(
                    f"{character_bridge.base_url}/api/character/generate-pose",
                    json=payload,
                )
                if resp.status_code == 200:
                    state = resp.json()
                    if isinstance(state, dict) and state.get("type") == "character_state":
                        character_bridge.last_state = state
                        await character_bridge.broadcast_to_viewers(state)
                    return state
        except Exception:
            pass

    prompt = str(payload.get("prompt") or "cyber_salute")
    state = await standalone_engine.generate_pose_local(
        prompt=prompt,
        current_state=character_bridge.last_state,
    )
    character_bridge.last_state = state
    await character_bridge.broadcast_to_viewers(state)
    return state


@app.get("/api/character/poses")
async def proxy_list_character_poses():
    """Fetch procedural and AI-synthesized custom poses from HELIOS Core or local standalone engine."""
    if character_bridge.should_use_core:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{character_bridge.base_url}/api/character/poses")
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
    return standalone_engine.list_poses_local()


@app.get("/api/character/rl-status")
async def proxy_get_character_rl_status():
    """Fetch Human-Reference RL Pose Policy status from HELIOS Core or local standalone engine."""
    if character_bridge.should_use_core:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{character_bridge.base_url}/api/character/rl-status")
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
    return standalone_engine.get_rl_status_local()


@app.post("/api/character/rl-train")
async def proxy_train_character_rl_pose(payload: Dict[str, Any]):
    """Run RL Pose Policy training via HELIOS Core or local standalone engine."""
    if character_bridge.should_use_core:
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.post(
                    f"{character_bridge.base_url}/api/character/rl-train",
                    json=payload,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    c_state = data.get("character_state")
                    if isinstance(c_state, dict) and c_state.get("type") == "character_state":
                        character_bridge.last_state = c_state
                        await character_bridge.broadcast_to_viewers(c_state)
                    return data
        except Exception:
            pass

    data = await standalone_engine.train_rl_local(
        pose_name=str(payload.get("pose_name") or "all"),
        episodes=int(payload.get("episodes") or 18),
        simulate_curriculum=bool(payload.get("simulate_curriculum", True)),
        current_state=character_bridge.last_state,
    )
    c_state = data.get("character_state")
    if isinstance(c_state, dict) and c_state.get("type") == "character_state":
        character_bridge.last_state = c_state
        await character_bridge.broadcast_to_viewers(c_state)
    return data


@app.post("/api/character/rl-feedback")
async def proxy_apply_character_rl_feedback(payload: Dict[str, Any]):
    """Apply online RL reward/penalty feedback via HELIOS Core or local standalone engine."""
    if character_bridge.should_use_core:
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                resp = await client.post(
                    f"{character_bridge.base_url}/api/character/rl-feedback",
                    json=payload,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    c_state = data.get("character_state")
                    if isinstance(c_state, dict) and c_state.get("type") == "character_state":
                        character_bridge.last_state = c_state
                        await character_bridge.broadcast_to_viewers(c_state)
                    return data
        except Exception:
            pass

    data = await standalone_engine.feedback_rl_local(
        pose_name=str(payload.get("pose_name") or "cyber_salute"),
        user_award_delta=float(payload.get("user_award_delta", 100.0)),
        browser_telemetry=payload.get("browser_telemetry"),
        current_state=character_bridge.last_state,
    )
    c_state = data.get("character_state")
    if isinstance(c_state, dict) and c_state.get("type") == "character_state":
        character_bridge.last_state = c_state
        await character_bridge.broadcast_to_viewers(c_state)
    return data


def _local_personality_studio_snapshot() -> Dict[str, Any]:
    """Local filesystem reader for personality card & prompts so Studio works in both versions."""
    import yaml

    pers_dir = ROUTER_ROOT / "personalities"
    prompts_dir = ROUTER_ROOT / "prompts"
    helios_yaml = pers_dir / "helios.yaml"
    local_mirror = CHAR_ROOT / "helios_personality_card.yaml"

    card_path = local_mirror if local_mirror.exists() else helios_yaml
    raw_yaml = _safe_read_text(card_path) if card_path.exists() else ""
    active_card = yaml.safe_load(raw_yaml) if raw_yaml else standalone_engine.load_card()

    presets = []
    if pers_dir.exists():
        for file in sorted(pers_dir.iterdir()):
            if file.suffix.lower() in (".yaml", ".yml"):
                try:
                    txt = _safe_read_text(file)
                    data = yaml.safe_load(txt) or {}
                    presets.append({
                        "id": file.stem,
                        "filename": file.name,
                        "format": "yaml",
                        "name": data.get("name") or data.get("identity", {}).get("name") or file.stem.upper(),
                        "content": txt,
                        "structured": data,
                    })
                except Exception:
                    pass
            elif file.suffix.lower() in (".md", ".json"):
                presets.append({
                    "id": file.stem,
                    "filename": file.name,
                    "format": file.suffix.lstrip(".").lower(),
                    "name": file.stem.upper(),
                    "content": _safe_read_text(file),
                })

    raw_prompts = {}
    for pk in ["general", "coding", "reasoning", "agent", "vision", "ui"]:
        pf = prompts_dir / f"{pk}.md"
        raw_prompts[pk] = _safe_read_text(pf)

    bot_name = (
        active_card.get("identity", {}).get("name")
        or active_card.get("name")
        or "HELIOS"
    ) if isinstance(active_card, dict) else "HELIOS"

    return {
        "ok": True,
        "status": "ok",
        "bot_name": bot_name,
        "personality_tagline": "helpful, witty, slightly sarcastic, and proactive",
        "card": active_card,
        "active_card": active_card,
        "raw_yaml": raw_yaml,
        "active_card_yaml": raw_yaml,
        "presets": presets,
        "prompts": raw_prompts,
        "character_state": character_bridge.last_state,
    }


@app.get("/api/character/personality-studio")
async def proxy_get_personality_studio():
    """Fetch Personality Card & Prompts from HELIOS Core (:8000) or local Character-Only storage."""
    if character_bridge.should_use_core:
        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                resp = await client.get(f"{character_bridge.base_url}/api/character/personality-studio")
                if resp.status_code == 200:
                    data = resp.json()
                    data.setdefault("ok", True)
                    if "active_card" in data and "card" not in data:
                        data["card"] = data["active_card"]
                    if "active_card_yaml" in data and "raw_yaml" not in data:
                        data["raw_yaml"] = data["active_card_yaml"]
                    return data
        except Exception:
            pass
    return _local_personality_studio_snapshot()


@app.post("/api/character/personality-studio")
async def proxy_save_personality_studio(payload: Dict[str, Any]):
    """Save Personality Card & Prompts to local files and HELIOS Core (:8000), then hot-reload."""
    import yaml

    pers_dir = ROUTER_ROOT / "personalities"
    prompts_dir = ROUTER_ROOT / "prompts"
    helios_yaml = pers_dir / "helios.yaml"
    local_mirror = CHAR_ROOT / "helios_personality_card.yaml"

    yaml_text = payload.get("card_yaml") or payload.get("raw_yaml")
    if yaml_text and "card_yaml" not in payload:
        payload["card_yaml"] = yaml_text

    parsed_card = None
    try:
        if isinstance(yaml_text, str) and yaml_text.strip():
            parsed = yaml.safe_load(yaml_text)
            if isinstance(parsed, dict):
                parsed_card = parsed
                raw_out = yaml_text.strip() + "\n"
                local_mirror.write_text(raw_out, encoding="utf-8")
                if pers_dir.exists():
                    helios_yaml.write_text(raw_out, encoding="utf-8")
        elif isinstance(payload.get("card"), dict):
            parsed_card = payload["card"]
            raw_out = yaml.safe_dump(parsed_card, sort_keys=False, allow_unicode=True)
            local_mirror.write_text(raw_out, encoding="utf-8")
            if pers_dir.exists():
                helios_yaml.write_text(raw_out, encoding="utf-8")

        if isinstance(payload.get("prompts"), dict) and prompts_dir.exists():
            for pk, content in payload["prompts"].items():
                if pk in {"general", "coding", "reasoning", "agent", "vision", "ui"} and isinstance(content, str) and content.strip():
                    (prompts_dir / f"{pk}.md").write_text(content.strip() + "\n", encoding="utf-8")
    except Exception:
        pass

    if parsed_card:
        standalone_engine.reload_card(parsed_card)
        emb = parsed_card.get("embodied_expression") if isinstance(parsed_card.get("embodied_expression"), dict) else {}
        default_style = emb.get("default_posture_style") or emb.get("default_style")
        if default_style:
            character_bridge.last_state["style"] = str(default_style).lower()
            await character_bridge.broadcast_to_viewers(character_bridge.last_state)

    if character_bridge.should_use_core:
        try:
            async with httpx.AsyncClient(timeout=3.5) as client:
                resp = await client.post(
                    f"{character_bridge.base_url}/api/character/personality-studio",
                    json=payload,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    data.setdefault("ok", True)
                    if "active_card" in data and "card" not in data:
                        data["card"] = data["active_card"]
                    if "active_card_yaml" in data and "raw_yaml" not in data:
                        data["raw_yaml"] = data["active_card_yaml"]
                    c_state = data.get("character_state")
                    if isinstance(c_state, dict) and c_state.get("type") == "character_state":
                        character_bridge.last_state = c_state
                        await character_bridge.broadcast_to_viewers(c_state)
                    return data
        except Exception:
            pass

    return _local_personality_studio_snapshot()


async def handle_character_viewer_ws(websocket: WebSocket):
    await websocket.accept()
    character_bridge.active_viewers.add(websocket)
    viewer_id = id(websocket)

    # Immediately synchronize viewer with current status and character state
    await websocket.send_json(character_bridge.get_status_dict())
    await websocket.send_json(character_bridge.last_sync)
    await websocket.send_json(character_bridge.last_state)

    try:
        while True:
            raw_msg = await websocket.receive_text()
            payload = json.loads(raw_msg)
            msg_type = payload.get("type")

            if msg_type in ("character_sync", "request_state"):
                await websocket.send_json(character_bridge.get_status_dict())
                await websocket.send_json(character_bridge.last_sync)
                await websocket.send_json(character_bridge.last_state)
                continue

            if msg_type == "set_edition":
                await update_helios_config({"edition": payload.get("edition", "auto")})
                continue

            if msg_type == "direct_body":
                await proxy_direct_character_body(payload)
                continue

            if msg_type == "speak_line":
                text = str(payload.get("text") or "").strip()
                if not text:
                    continue
                emotion = str(payload.get("emotion") or character_bridge.last_state.get("emotion") or "neutral")
                voice = str(payload.get("voice") or "en-US-AriaNeural")
                tts_data = await synthesize_character_tts_async(text, voice=voice, emotion=emotion)
                dur = float(tts_data.get("duration") or 2.0)
                await websocket.send_json({
                    "type": "character_speech",
                    "speaking": True,
                    "event": "audio_chunk",
                    "text": text,
                    "audio_b64": tts_data["audio_b64"],
                    "mime_type": tts_data["mime_type"],
                    "sample_rate": tts_data["sample_rate"],
                    "duration": dur,
                    "rms": tts_data["rms"],
                    "visemes": tts_data["visemes"],
                })

                async def _notify_speak_line_done(ws_ref: WebSocket, wait_s: float):
                    await asyncio.sleep(max(0.4, wait_s + 0.15))
                    try:
                        await ws_ref.send_json({
                            "type": "character_speech",
                            "speaking": False,
                            "event": "speech_finished",
                        })
                    except Exception:
                        pass

                asyncio.create_task(_notify_speak_line_done(websocket, dur))
                continue

            if msg_type == "interrupt":
                if character_bridge.should_use_core:
                    try:
                        async with httpx.AsyncClient(timeout=2.5) as client:
                            await client.post(f"{character_bridge.base_url}/api/interrupt")
                    except Exception:
                        pass
                await websocket.send_json({"type": "character_stop", "reason": "user_interrupt"})
                continue

            if msg_type == "chat_message":
                user_text = str(payload.get("text") or "").strip()
                if not user_text:
                    continue

                req_edition = str(payload.get("edition") or "").lower().strip()
                if req_edition in ("character_only", "standalone", "full_spec", "helios", "auto"):
                    character_bridge.mode = (
                        "character_only"
                        if req_edition in ("character_only", "standalone")
                        else ("full_spec" if req_edition in ("full_spec", "helios") else "auto")
                    )

                result = None
                if character_bridge.should_use_core:
                    result = await character_bridge.forward_chat_to_helios(user_text)

                if result and result.get("response"):
                    directed_state = result.get("character_state") or character_bridge.last_state
                    if isinstance(directed_state, dict):
                        character_bridge.last_state = directed_state
                    await websocket.send_json({
                        "type": "helios_reply",
                        "reply": result["response"],
                        "text": result["response"],
                        "tools_used": result.get("tools_used", []),
                        "character_state": directed_state,
                        "edition": "full_spec",
                    })
                else:
                    # Standalone 'Just the Character' brain (or seamless fallback when :8000 is not running)
                    standalone_res = await standalone_engine.chat_standalone(
                        user_text=user_text,
                        viewer_id=viewer_id,
                        current_state=character_bridge.last_state,
                    )
                    directed_state = standalone_res["character_state"]
                    character_bridge.last_state = directed_state
                    await character_bridge.broadcast_to_viewers(directed_state)

                    tts_data = standalone_res.get("tts")
                    speech_dur = 2.0
                    if isinstance(tts_data, dict):
                        speech_dur = float(tts_data.get("duration", 2.0) or 2.0)
                        await websocket.send_json({
                            "type": "character_speech",
                            "speaking": True,
                            "event": "audio_chunk",
                            "text": standalone_res["response"],
                            "audio_b64": tts_data.get("audio_b64"),
                            "mime_type": tts_data.get("mime_type", "audio/mpeg"),
                            "sample_rate": tts_data.get("sample_rate", 24000),
                            "duration": speech_dur,
                            "rms": tts_data.get("rms", []),
                            "visemes": tts_data.get("visemes", []),
                        })

                    await websocket.send_json({
                        "type": "helios_reply",
                        "reply": standalone_res["response"],
                        "text": standalone_res["response"],
                        "tools_used": [],
                        "character_state": directed_state,
                        "edition": "character_only",
                        "model": standalone_res.get("model"),
                    })

                    async def _finish_standalone_speech(ws_ref: WebSocket, wait_s: float):
                        await asyncio.sleep(max(0.5, wait_s + 0.2))
                        character_bridge.last_state["mode"] = "idle"
                        character_bridge.last_state["speaking"] = False
                        try:
                            await ws_ref.send_json({
                                "type": "character_speech",
                                "speaking": False,
                                "event": "speech_finished",
                            })
                        except Exception:
                            pass

                    asyncio.create_task(_finish_standalone_speech(websocket, speech_dur))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        character_bridge.active_viewers.discard(websocket)


@app.websocket("/ws/chat")
async def websocket_chat_endpoint(websocket: WebSocket):
    await handle_character_viewer_ws(websocket)


@app.websocket("/ws")
async def websocket_legacy_endpoint(websocket: WebSocket):
    await handle_character_viewer_ws(websocket)


app.mount("/", StaticFiles(directory=str(VIEWER_DIR), html=True), name="viewer")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
