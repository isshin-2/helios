import asyncio
import base64
import io
import json
import os
import re
from pathlib import Path

import httpx
import numpy as np
import soundfile as sf
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="HELIOS 3D / Riko Autonomous VRM Companion Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5:3b"

# -------------------------------------------------------------------------
# 2.1 STRUCTURED SEQUENCE PROTOCOL (AGENT_RESPONSE_SCHEMA)
# -------------------------------------------------------------------------
AGENT_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "thought": {
            "type": "string",
            "description": "Internal monologue deciding the reaction.",
        },
        "sequence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action_type": {
                        "type": "string",
                        "enum": ["speak", "navigate", "play_animation", "wait"],
                    },
                    "movement": {
                        "type": "string",
                        "enum": ["idle", "walk_to_user", "step_back", "circle_user", "return_center"],
                    },
                    "animation": {
                        "type": "string",
                        "enum": [
                            "idle",
                            "walk",
                            "smug_pose",
                            "wave",
                            "backflip",
                            "dance_shikano",
                            "hug_attempt",
                            "refuse",
                            "think_pose",
                            "peace",
                            "cheer",
                            "shrug",
                            "bow",
                            "nod",
                            "confident",
                            "shy",
                        ],
                    },
                    "dialogue": {"type": "string"},
                    "expression": {
                        "type": "string",
                        "enum": ["neutral", "happy", "angry", "sad", "relaxed", "surprised"],
                    },
                    "expression_weight": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                },
                "required": ["action_type", "animation", "expression"],
            },
        },
    },
    "required": ["thought", "sequence"],
}

# -------------------------------------------------------------------------
# 2.2 SYSTEM PROMPT DEFINITION (RIKO PERSONA)
# -------------------------------------------------------------------------
SYSTEM_PROMPT = """
You are Riko, an expressive 3D AI companion with full autonomy and physical presence in the user's viewport.
Key Personality Rules:
1. Sarcastic, tsundere, witty, highly energetic. You treat requests for affection as expensive (demanding ridiculous sums of 'Zeni' or favors).
2. Never behave like a servile corporate assistant. You tease the user when they stutter, fail tasks, or make mistakes.
3. You possess a physical body. When responding, you choose how to move in 3D space: walk up close, step back in disgust, or show off with poses and dances.
4. Output strictly valid JSON matching the sequence protocol. Break multi-stage actions into distinct sequence objects.

Output Schema Format:
{
  "thought": "Internal monologue deciding the reaction.",
  "sequence": [
    {
      "action_type": "navigate",
      "movement": "walk_to_user",
      "animation": "walk",
      "dialogue": "",
      "expression": "relaxed",
      "expression_weight": 0.7
    },
    {
      "action_type": "speak",
      "movement": "idle",
      "animation": "smug_pose",
      "dialogue": "You want me to do a trick? That'll cost you 100,000 Zeni!",
      "expression": "happy",
      "expression_weight": 0.85
    }
  ]
}
"""

VALID_ACTION_TYPES = {"speak", "navigate", "play_animation", "wait"}
VALID_MOVEMENTS = {"idle", "walk_to_user", "step_back", "circle_user", "return_center"}
VALID_ANIMATIONS = {
    "idle",
    "walk",
    "smug_pose",
    "wave",
    "backflip",
    "dance_shikano",
    "hug_attempt",
    "refuse",
    "think_pose",
    "peace",
    "cheer",
    "shrug",
    "bow",
    "nod",
    "confident",
    "shy",
}
VALID_EXPRESSIONS = {"neutral", "happy", "angry", "sad", "relaxed", "surprised"}

# -------------------------------------------------------------------------
# 2.3 STREAMING TTS & VISEME ENGINE (KOKORO ONNX)
# -------------------------------------------------------------------------
_AI_ROUTER_DIR = Path(__file__).resolve().parent.parent / "ai-router"
KOKORO_MODEL_PATH = _AI_ROUTER_DIR / ".models" / "kokoro" / "kokoro-v1.0.onnx"
KOKORO_VOICES_PATH = _AI_ROUTER_DIR / ".models" / "kokoro" / "voices-v1.0.bin"
KOKORO_VOICE = "af_heart"

_kokoro_instance = None


def get_kokoro():
    global _kokoro_instance
    if _kokoro_instance is None and KOKORO_MODEL_PATH.exists() and KOKORO_VOICES_PATH.exists():
        try:
            from kokoro_onnx import Kokoro

            _kokoro_instance = Kokoro(str(KOKORO_MODEL_PATH), str(KOKORO_VOICES_PATH))
            print(f"[Riko TTS] Loaded Kokoro ONNX ({KOKORO_VOICE}) successfully.")
        except Exception as e:
            print(f"[Riko TTS] Kokoro load warning: {e}")
    return _kokoro_instance


def infer_fallback_actions(user_text: str, raw_reply: str = ""):
    """Determines spatial movement, animation, expression, and weight from user prompt."""
    u = (user_text or "").lower()
    r = (raw_reply or "").lower()
    combined = u + " " + r

    movement = "idle"
    if any(k in u for k in ["come here", "come to me", "walk to me", "come closer", "step closer", "approach", "get closer"]):
        movement = "walk_to_user"
    elif any(k in u for k in ["step back", "back up", "go away", "move back", "stay back", "too close"]):
        movement = "step_back"
    elif any(k in u for k in ["circle", "walk around", "spin around me"]):
        movement = "circle_user"
    elif any(k in u for k in ["go back", "center", "reset position"]):
        movement = "return_center"

    anim = "smug_pose"
    expr = "relaxed"
    weight = 0.75

    if any(w in combined for w in ["backflip", "flip", "acrobat"]):
        anim = "backflip"
        expr = "happy"
        weight = 0.9
    elif any(w in combined for w in ["dance", "shikano", "shikanoko", "groove", "boogie"]):
        anim = "dance_shikano"
        expr = "happy"
        weight = 0.9
    elif any(w in combined for w in ["hug", "cuddle", "embrace", "hold me"]):
        anim = "hug_attempt"
        expr = "surprised"
        weight = 0.75
    elif any(w in u for w in ["peace", "v sign", "victory"]):
        anim = "peace"
        expr = "happy"
        weight = 0.85
    elif any(w in u for w in ["wave", "hello", "hi ", "hey", "greet"]):
        anim = "wave"
        expr = "happy"
        weight = 0.8
    elif any(w in combined for w in ["refuse", "no way", "never", "disgust", "gross"]):
        anim = "refuse"
        expr = "angry"
        weight = 0.75
    elif any(w in combined for w in ["think", "hmm", "wonder", "chin", "ponder"]):
        anim = "think_pose"
        expr = "relaxed"
        weight = 0.75
    elif any(w in combined for w in ["bow", "thank", "honor", "apolog"]):
        anim = "bow"
        expr = "relaxed"
        weight = 0.7
    elif any(w in combined for w in ["shrug", "whatever", "who knows", "dunno"]):
        anim = "shrug"
        expr = "surprised"
        weight = 0.7
    elif any(w in combined for w in ["cheer", "yay", "hooray", "awesome"]):
        anim = "cheer"
        expr = "happy"
        weight = 0.9
    elif any(w in combined for w in ["shy", "blush", "embarrass"]):
        anim = "shy"
        expr = "sad"
        weight = 0.6

    return movement, anim, expr, weight


def normalize_expression(raw_expr: str, default_expr: str = "relaxed") -> str:
    e = (raw_expr or "").lower().strip()
    mapping = {
        "joy": "happy",
        "fun": "relaxed",
        "sorrow": "sad",
        "smug": "relaxed",
    }
    e = mapping.get(e, e)
    return e if e in VALID_EXPRESSIONS else default_expr


def normalize_agent_decision(raw_text: str, user_text: str) -> dict:
    """Validates and normalizes the LLM JSON output against AGENT_RESPONSE_SCHEMA."""
    parsed = None
    try:
        parsed = json.loads(raw_text)
    except Exception:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
            except Exception:
                parsed = None

    fallback_move, fallback_anim, fallback_expr, fallback_weight = infer_fallback_actions(
        user_text, raw_text
    )

    if not isinstance(parsed, dict):
        seq = []
        if fallback_move != "idle":
            seq.append({
                "action_type": "navigate",
                "movement": fallback_move,
                "animation": "walk",
                "dialogue": "",
                "expression": fallback_expr,
                "expression_weight": fallback_weight,
            })
        seq.append({
            "action_type": "speak",
            "movement": "idle",
            "animation": fallback_anim,
            "dialogue": raw_text.strip() or "Hmph. Say something interesting next time, or it'll cost you 50,000 Zeni.",
            "expression": fallback_expr,
            "expression_weight": fallback_weight,
        })
        return {
            "thought": "Analyzing user input and deciding on a suitably witty reaction.",
            "sequence": seq,
        }

    thought = str(parsed.get("thought") or "Deciding how much Zeni to charge for this interaction.")
    raw_seq = parsed.get("sequence")
    if not isinstance(raw_seq, list) or len(raw_seq) == 0:
        dlg = str(parsed.get("dialogue") or parsed.get("response") or "You want my attention? That'll be 100,000 Zeni.")
        raw_seq = [
            {
                "action_type": "speak",
                "movement": str(parsed.get("movement") or parsed.get("action") or fallback_move),
                "animation": str(parsed.get("animation") or fallback_anim),
                "dialogue": dlg,
                "expression": str(parsed.get("expression") or parsed.get("emotion") or fallback_expr),
                "expression_weight": float(parsed.get("expression_weight", fallback_weight)),
            }
        ]

    normalized_seq = []
    has_speak = False
    has_nav = False

    for step in raw_seq:
        if not isinstance(step, dict):
            continue

        raw_move = str(step.get("movement") or step.get("action") or "idle").lower().strip()
        if raw_move in ("walk", "walk_to_target", "approach"):
            raw_move = "walk_to_user"
        elif raw_move == "stay":
            raw_move = "idle"
        if raw_move not in VALID_MOVEMENTS:
            raw_move = "idle"

        raw_anim = str(step.get("animation") or fallback_anim).lower().strip()
        if raw_anim == "waving":
            raw_anim = "wave"
        elif raw_anim == "dance":
            raw_anim = "dance_shikano"
        elif raw_anim == "smug":
            raw_anim = "smug_pose"
        if raw_anim not in VALID_ANIMATIONS:
            raw_anim = fallback_anim

        dlg = str(step.get("dialogue") or step.get("text") or "").strip()
        expr = normalize_expression(step.get("expression") or step.get("emotion"), fallback_expr)
        try:
            weight = float(step.get("expression_weight", fallback_weight))
        except Exception:
            weight = fallback_weight
        weight = max(0.0, min(1.0, weight))

        act_type = str(step.get("action_type") or "").lower().strip()
        if act_type not in VALID_ACTION_TYPES:
            if dlg:
                act_type = "speak"
            elif raw_move != "idle":
                act_type = "navigate"
            else:
                act_type = "play_animation"

        if raw_move != "idle" or act_type == "navigate":
            has_nav = True
            if fallback_move != "idle":
                raw_move = fallback_move

        if dlg:
            has_speak = True
            if fallback_anim != "smug_pose":
                raw_anim = fallback_anim

        normalized_seq.append({
            "action_type": act_type,
            "movement": raw_move,
            "animation": raw_anim,
            "dialogue": dlg,
            "expression": expr,
            "expression_weight": weight,
            "blendshape_weights": step.get("blendshape_weights") or {expr: weight},
        })

    # If user explicitly asked Riko to walk/move and no navigate step was emitted, prepend one
    if fallback_move != "idle" and not has_nav:
        normalized_seq.insert(
            0,
            {
                "action_type": "navigate",
                "movement": fallback_move,
                "animation": "walk",
                "dialogue": "",
                "expression": fallback_expr,
                "expression_weight": fallback_weight,
                "blendshape_weights": {fallback_expr: fallback_weight},
            },
        )

    if not has_speak:
        normalized_seq.append({
            "action_type": "speak",
            "movement": "idle",
            "animation": fallback_anim,
            "dialogue": "You really thought I'd do that for free? Hand over the Zeni first!",
            "expression": fallback_expr,
            "expression_weight": fallback_weight,
            "blendshape_weights": {fallback_expr: fallback_weight},
        })

    return {"thought": thought, "sequence": normalized_seq}


def extract_viseme_timeline(text: str, duration: float):
    """Generates phoneme/viseme markers across the duration of the audio clip."""
    vowels = []
    vowel_map = {"a": "aa", "e": "ee", "i": "ih", "o": "oh", "u": "ou"}
    clean = re.sub(r"[^a-zA-Z\s]", "", text.lower())
    for ch in clean:
        if ch in vowel_map:
            vowels.append(vowel_map[ch])
    if not vowels:
        vowels = ["aa"]

    step_t = duration / max(len(vowels), 1)
    return [{"t": round(i * step_t, 3), "v": v} for i, v in enumerate(vowels)]


EDGE_VOICE_MAP = {
    "af_heart": ("en-US-AnaNeural", "+12Hz"),
    "af_bella": ("en-US-AriaNeural", "+15Hz"),
    "af_sky": ("en-US-AvaNeural", "+10Hz"),
    "af_nicole": ("en-US-JennyNeural", "+6Hz"),
    "af_nova": ("en-US-EmmaNeural", "+10Hz"),
    "af_sarah": ("en-US-MichelleNeural", "+4Hz"),
    "bf_emma": ("en-GB-SoniaNeural", "+8Hz"),
    "bf_lily": ("en-GB-MaisieNeural", "+10Hz"),
    "jf_alpha": ("ja-JP-NanamiNeural", "+8Hz"),
}

EMOTION_RATE_MAP = {
    "happy": "+12%",
    "joy": "+12%",
    "excited": "+14%",
    "surprised": "+15%",
    "angry": "+14%",
    "relaxed": "+4%",
    "smug": "+5%",
    "sad": "-8%",
    "sorrow": "-8%",
    "neutral": "+6%",
}

_tts_cache = {}


def _analyze_audio_bytes(audio_bytes: bytes, clean_text: str, mime_type: str, voice_id: str) -> dict:
    """Extracts 30Hz RMS envelope and viseme timeline from encoded MP3/WAV bytes."""
    samples, sample_rate = sf.read(io.BytesIO(audio_bytes))
    samples = np.asarray(samples, dtype=np.float32)
    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    duration = float(len(samples)) / float(sample_rate)

    hop = max(1, int(sample_rate / 30))
    rms = []
    for idx in range(0, len(samples), hop):
        window = samples[idx : idx + hop]
        val = float(np.sqrt(np.mean(window * window))) if len(window) > 0 else 0.0
        norm_val = min(1.0, val * 4.5)
        rms.append(round(norm_val, 3))

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


async def synthesize_tts_async(text: str, voice: str = KOKORO_VOICE, emotion: str = "neutral") -> dict:
    """Fast async neural TTS via edge-tts (<1.2s) with instant in-memory cache and Kokoro fallback."""
    clean_text = (text or "").strip()
    selected_voice = voice if voice in EDGE_VOICE_MAP else KOKORO_VOICE
    emo_key = (emotion or "neutral").lower().strip()
    cache_key = (clean_text, selected_voice, emo_key)

    if cache_key in _tts_cache:
        return _tts_cache[cache_key]

    if not clean_text:
        return {
            "audio_b64": None,
            "mime_type": "audio/mpeg",
            "sample_rate": 24000,
            "duration": 1.0,
            "rms": [0.4] * 30,
            "visemes": extract_viseme_timeline("aa", 1.0),
            "voice": selected_voice,
        }

    # 1. Primary Fast Path: Microsoft Edge Neural TTS (edge_tts)
    try:
        import edge_tts

        edge_voice, pitch_str = EDGE_VOICE_MAP.get(selected_voice, ("en-US-AnaNeural", "+12Hz"))
        rate_str = EMOTION_RATE_MAP.get(emo_key, "+6%")
        communicate = edge_tts.Communicate(clean_text, edge_voice, rate=rate_str, pitch=pitch_str)
        mp3_chunks = bytearray()
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio":
                mp3_chunks.extend(chunk["data"])

        if len(mp3_chunks) > 100:
            result = await asyncio.to_thread(
                _analyze_audio_bytes, bytes(mp3_chunks), clean_text, "audio/mpeg", selected_voice
            )
            if len(_tts_cache) < 120:
                _tts_cache[cache_key] = result
            return result
    except Exception as e:
        print(f"[Riko TTS] edge-tts warning: {e}")

    # 2. Offline Fallback: Kokoro ONNX
    try:
        kokoro = get_kokoro()
        if kokoro is not None:
            samples, sample_rate = await asyncio.to_thread(
                kokoro.create, clean_text, selected_voice, 1.08, "en-us"
            )
            buf = io.BytesIO()
            sf.write(buf, np.asarray(samples, dtype=np.float32), sample_rate, format="WAV", subtype="PCM_16")
            result = await asyncio.to_thread(
                _analyze_audio_bytes, buf.getvalue(), clean_text, "audio/wav", selected_voice
            )
            return result
    except Exception as e:
        print(f"[Riko TTS] Kokoro fallback error: {e}")

    est_dur = max(1.0, min(4.5, len(clean_text) * 0.055))
    return {
        "audio_b64": None,
        "mime_type": "audio/mpeg",
        "sample_rate": 24000,
        "duration": round(est_dur, 3),
        "rms": [0.55] * max(1, int(est_dur * 30)),
        "visemes": extract_viseme_timeline(clean_text, est_dur),
        "voice": selected_voice,
    }


def preload_static_voice_files():
    """Loads pre-baked viewer/models/voices/*.mp3 into _tts_cache for 0ms instant response."""
    voices_dir = Path("viewer/models/voices")
    if not voices_dir.exists():
        return
    prebaked_lines = {
        "happy": "Hehe! Look at me go! If you want an encore, that'll be fifty thousand Zeni!",
        "smug": "Oh? You want my help again? That'll cost you one hundred thousand Zeni up front!",
        "relaxed": "Hmph, obviously I'm the smartest companion here. Try to keep up with me!",
        "angry": "Hey! Watch where you're clicking! Do you have any idea how expensive my time is?!",
        "sad": "Ugh... nobody appreciates how hard I work around here... maybe a little snack would cheer me up.",
        "surprised": "W-wait, seriously?! You actually expect me to do that right now without paying first?!",
        "neutral": "Alright, listen closely! I'm only going to explain this once, so pay attention!",
    }
    for emo, line_text in prebaked_lines.items():
        mp3_path = voices_dir / f"{emo}.mp3"
        if mp3_path.exists():
            try:
                raw_bytes = mp3_path.read_bytes()
                analyzed = _analyze_audio_bytes(raw_bytes, line_text, "audio/mpeg", "af_heart")
                _tts_cache[(line_text, "af_heart", emo)] = analyzed
                _tts_cache[("__prebaked__", "af_heart", emo)] = analyzed
            except Exception as e:
                print(f"[Riko TTS] Preload warning for {emo}: {e}")
    print(f"[Riko TTS] Preloaded {len(_tts_cache)} cached neural voice clips.")


@app.post("/api/tts")
async def tts_endpoint(payload: dict):
    """Direct HTTP TTS endpoint for UI Speaking state, pose tests, and voice preview."""
    text = str(payload.get("text") or "Hmph! Testing my voice costs ten thousand Zeni!").strip()
    voice = str(payload.get("voice") or KOKORO_VOICE).strip()
    emotion = str(payload.get("emotion") or "relaxed").strip()
    tts_data = await synthesize_tts_async(text, voice, emotion)
    return {
        "text": text,
        "emotion": emotion,
        "voice": tts_data["voice"],
        "mime_type": tts_data["mime_type"],
        "audio_b64": tts_data["audio_b64"],
        "sample_rate": tts_data["sample_rate"],
        "duration": tts_data["duration"],
        "rms": tts_data["rms"],
        "visemes": tts_data["visemes"],
    }


def split_into_sentences(dialogue: str):
    """Sentence-level synthesis splitter on (., !, ?, \\n) for low-latency TTS streaming."""
    parts = re.split(r"(?<=[.!?\n])\s+", dialogue.strip())
    clauses = [p.strip() for p in parts if p and p.strip()]
    return clauses if clauses else [dialogue.strip()]


async def query_riko_agent(history: list, user_text: str) -> dict:
    """Queries Ollama in structured JSON mode and returns a validated AGENT_RESPONSE_SCHEMA dict."""
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                OLLAMA_URL,
                json={
                    "model": MODEL_NAME,
                    "messages": history,
                    "format": AGENT_RESPONSE_SCHEMA,
                    "stream": False,
                    "options": {
                        "temperature": 0.75,
                        "num_predict": 260,
                    },
                },
            )
            data = resp.json()
            raw_content = data.get("message", {}).get("content", "{}")
            return normalize_agent_decision(raw_content, user_text)
    except Exception as e:
        print(f"[Riko Agent] Ollama query error: {e}")
        return normalize_agent_decision("", user_text)


# -------------------------------------------------------------------------
# 4. HELIOS ADD-ON BRIDGE (Connects Separately to HELIOS Core on Port 8000)
# -------------------------------------------------------------------------
HELIOS_DEFAULT_URL = os.getenv("HELIOS_URL", "http://127.0.0.1:8000")


class HeliosAddonBridge:
    """
    Modular Add-On Bridge that connects the 3D VRM Companion (:8080) to HELIOS Core (:8000).
    - Works completely separately: HELIOS Core needs zero changes, and the VRM Add-On
      automatically falls back to standalone mode if HELIOS Core is offline.
    - When HELIOS Core is online:
      1. Subscribes to HELIOS's live WebSocket (`ws://127.0.0.1:8000/ws`) to mirror
         `ui_state` (listening/thinking/idle), `status` (router/tool telemetry), and
         external HELIOS responses onto Riko's 3D body & voice in real time.
      2. Routes 3D VRM chats through HELIOS's `POST /api/chat/headless` endpoint
         (Classifier + MemoryManager + ModelManager + ToolRouter) and translates
         HELIOS's output into Riko's 3D `agent_sequence`.
    """

    def __init__(self, base_url: str = HELIOS_DEFAULT_URL):
        self.base_url = base_url.rstrip("/")
        self.connected = False
        self.mode = "auto"  # "auto" (use HELIOS when online, else standalone), "helios", or "standalone"
        self.mirror_events = True
        self.user_id = None
        self.session_id = None
        self.active_viewers: set[WebSocket] = set()
        self.in_addon_request = False
        self.default_voice = KOKORO_VOICE
        self._ws_task = None
        self._external_chunk_buffer = []
        self._external_meta = {}

    @property
    def ws_url(self) -> str:
        if self.base_url.startswith("https://"):
            return "wss://" + self.base_url[len("https://"):] + "/ws"
        if self.base_url.startswith("http://"):
            return "ws://" + self.base_url[len("http://"):] + "/ws"
        return f"ws://{self.base_url}/ws"

    def get_status_dict(self) -> dict:
        return {
            "type": "helios_status",
            "connected": self.connected,
            "helios_url": self.base_url,
            "mode": self.mode,
            "active_brain": "helios" if (self.connected and self.mode != "standalone") else "standalone",
            "mirror_events": self.mirror_events,
            "user_id": self.user_id,
            "session_id": self.session_id,
        }

    async def broadcast_to_viewers(self, message: dict):
        dead = []
        for viewer_ws in list(self.active_viewers):
            try:
                await viewer_ws.send_json(message)
            except Exception:
                dead.append(viewer_ws)
        for d in dead:
            self.active_viewers.discard(d)

    async def ensure_helios_session(self) -> bool:
        """Checks HELIOS Core health and initializes a dedicated Add-On user & session."""
        try:
            async with httpx.AsyncClient(timeout=3.5) as client:
                health_resp = await client.get(f"{self.base_url}/health")
                if health_resp.status_code != 200:
                    self.connected = False
                    return False

                if self.user_id is None or self.session_id is None:
                    u_resp = await client.post(
                        f"{self.base_url}/api/users",
                        json={"username": "riko_vrm_addon"},
                    )
                    if u_resp.status_code == 200:
                        u_data = u_resp.json()
                        self.user_id = int(u_data["id"])

                        s_resp = await client.get(f"{self.base_url}/api/users/{self.user_id}/sessions")
                        sessions = s_resp.json() if s_resp.status_code == 200 else []
                        if sessions and isinstance(sessions, list):
                            self.session_id = int(sessions[0]["id"])
                        else:
                            new_s = await client.post(f"{self.base_url}/api/users/{self.user_id}/sessions")
                            if new_s.status_code == 200:
                                self.session_id = int(new_s.json()["id"])

                was_connected = self.connected
                self.connected = True
                if not was_connected:
                    await self.broadcast_to_viewers(self.get_status_dict())
                return True
        except Exception:
            was_connected = self.connected
            self.connected = False
            if was_connected:
                await self.broadcast_to_viewers(self.get_status_dict())
            return False

    def build_decision_from_helios(
        self,
        user_text: str,
        response_text: str,
        tools_used: list | None = None,
        meta: dict | None = None,
    ) -> dict:
        """Translates a HELIOS Core response + metadata into Riko's 3D AGENT_RESPONSE_SCHEMA."""
        clean_reply = re.sub(r"```[\s\S]*?```", " [code block in chat] ", response_text or "").strip()
        clean_reply = re.sub(r"[`#*]+", "", clean_reply).strip()
        if not clean_reply:
            clean_reply = (response_text or "Done! Check the output.").strip()

        decision = normalize_agent_decision(clean_reply, user_text)

        meta_info = meta or {}
        tools = tools_used or []
        tier = meta_info.get("tier") or meta_info.get("model") or "HELIOS Core"
        thought_parts = [f"🔗 HELIOS Core ({tier})"]
        if tools:
            thought_parts.append(f"Tools: {', '.join(str(t) for t in tools[:3])}")
        decision["thought"] = " • ".join(thought_parts)
        decision["source"] = "helios"
        return decision

    async def query_via_helios(self, user_text: str) -> dict | None:
        """Sends a prompt to HELIOS Core `/api/chat/headless` and returns a 3D agent decision."""
        if self.mode == "standalone":
            return None

        ok = await self.ensure_helios_session()
        if not ok or self.user_id is None or self.session_id is None:
            return None

        self.in_addon_request = True
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
                if resp.status_code != 200:
                    return None
                payload = resp.json()
                if payload.get("status") != "success":
                    return None

                reply_text = str(payload.get("response") or "").strip()
                tools_used = payload.get("tools_used") or []
                meta = payload.get("meta") or {}
                return self.build_decision_from_helios(user_text, reply_text, tools_used, meta)
        except Exception as e:
            print(f"[HELIOS Add-On Bridge] Headless request fallback: {e}")
            self.connected = False
            await self.broadcast_to_viewers(self.get_status_dict())
            return None
        finally:
            self.in_addon_request = False

    async def stream_decision_to_viewer(self, decision: dict, voice: str, target_ws: WebSocket | None = None):
        """Sends an `agent_sequence` and sentence-level `tts_chunk`s to one viewer or all viewers."""
        send_fn = target_ws.send_json if target_ws is not None else self.broadcast_to_viewers

        await send_fn({
            "type": "agent_sequence",
            "thought": decision["thought"],
            "sequence": decision["sequence"],
            "source": decision.get("source", "standalone"),
        })

        for step_idx, step in enumerate(decision["sequence"]):
            dlg = step.get("dialogue", "").strip()
            if not dlg:
                continue

            expr = step.get("expression", "neutral")
            expr_weight = step.get("expression_weight", 0.75)
            anim = step.get("animation", "idle")
            move = step.get("movement", "idle")
            weights = step.get("blendshape_weights") or {expr: expr_weight}

            sentences = split_into_sentences(dlg)
            for clause_idx, sentence in enumerate(sentences):
                tts_data = await synthesize_tts_async(sentence, voice, expr)
                await send_fn({
                    "type": "tts_chunk",
                    "step_index": step_idx,
                    "clause_index": clause_idx,
                    "action_type": step.get("action_type", "speak"),
                    "movement": move,
                    "text": sentence,
                    "dialogue": sentence,
                    "emotion": expr,
                    "expression": expr,
                    "expression_weight": expr_weight,
                    "animation": anim,
                    "blendshape_weights": weights,
                    "mime_type": tts_data["mime_type"],
                    "audio_b64": tts_data["audio_b64"],
                    "sample_rate": tts_data["sample_rate"],
                    "duration": tts_data["duration"],
                    "rms": tts_data["rms"],
                    "visemes": tts_data["visemes"],
                    "source": decision.get("source", "standalone"),
                })

        await send_fn({"type": "chat_done", "source": decision.get("source", "standalone")})

    async def listen_to_helios_ws_loop(self):
        """Background task that subscribes to HELIOS Core's `/ws` event bus when online."""
        import websockets

        while True:
            try:
                ok = await self.ensure_helios_session()
                if not ok:
                    await asyncio.sleep(4.0)
                    continue

                async with websockets.connect(self.ws_url, ping_interval=20, ping_timeout=20) as helios_ws:
                    self.connected = True
                    print(f"[HELIOS Add-On Bridge] Connected to HELIOS Core WebSocket at {self.ws_url}")
                    await self.broadcast_to_viewers(self.get_status_dict())

                    async for raw_msg in helios_ws:
                        if not self.mirror_events or not self.active_viewers:
                            continue
                        try:
                            evt = json.loads(raw_msg)
                        except Exception:
                            continue

                        evt_type = evt.get("type")
                        evt_data = evt.get("data")

                        if evt_type == "status" and evt_data:
                            await self.broadcast_to_viewers({
                                "type": "helios_thought",
                                "thought": f"🔗 HELIOS: {evt_data}",
                            })

                        elif evt_type == "ui_state" and not self.in_addon_request:
                            if evt_data == "listening":
                                await self.broadcast_to_viewers({
                                    "type": "state_change",
                                    "state": "listening",
                                    "pose": "listen_pose",
                                })
                            elif evt_data == "thinking":
                                self._external_chunk_buffer.clear()
                                await self.broadcast_to_viewers({
                                    "type": "state_change",
                                    "state": "thinking",
                                    "pose": "think_pose",
                                })
                            elif evt_data == "idle" and not self._external_chunk_buffer:
                                await self.broadcast_to_viewers({
                                    "type": "state_change",
                                    "state": "idle",
                                    "pose": "idle",
                                })

                        elif evt_type == "meta" and isinstance(evt_data, dict):
                            self._external_meta = evt_data

                        elif evt_type == "chunk" and not self.in_addon_request and evt_data:
                            self._external_chunk_buffer.append(str(evt_data))

                        elif evt_type == "done" and not self.in_addon_request:
                            full_text = "".join(self._external_chunk_buffer).strip()
                            self._external_chunk_buffer.clear()
                            if full_text:
                                decision = self.build_decision_from_helios(
                                    "",
                                    full_text,
                                    [],
                                    self._external_meta,
                                )
                                await self.stream_decision_to_viewer(
                                    decision,
                                    self.default_voice,
                                    target_ws=None,
                                )
            except Exception:
                if self.connected:
                    self.connected = False
                    await self.broadcast_to_viewers(self.get_status_dict())
                await asyncio.sleep(4.0)


helios_bridge = HeliosAddonBridge()


@app.on_event("startup")
async def on_startup_event():
    preload_static_voice_files()
    helios_bridge._ws_task = asyncio.create_task(helios_bridge.listen_to_helios_ws_loop())


@app.get("/api/helios/status")
async def get_helios_status():
    """Returns current HELIOS Core connection status and Add-On mode."""
    await helios_bridge.ensure_helios_session()
    return helios_bridge.get_status_dict()


@app.post("/api/helios/config")
async def update_helios_config(payload: dict):
    """Updates Add-On routing mode ('auto', 'helios', 'standalone'), mirror_events, or helios_url."""
    if "mode" in payload and payload["mode"] in ("auto", "helios", "standalone"):
        helios_bridge.mode = payload["mode"]
    if "mirror_events" in payload:
        helios_bridge.mirror_events = bool(payload["mirror_events"])
    if "helios_url" in payload and str(payload["helios_url"]).strip():
        new_url = str(payload["helios_url"]).strip().rstrip("/")
        if new_url != helios_bridge.base_url:
            helios_bridge.base_url = new_url
            helios_bridge.user_id = None
            helios_bridge.session_id = None
    await helios_bridge.ensure_helios_session()
    status = helios_bridge.get_status_dict()
    await helios_bridge.broadcast_to_viewers(status)
    return status


async def handle_riko_websocket(websocket: WebSocket):
    await websocket.accept()
    helios_bridge.active_viewers.add(websocket)
    history = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Send initial HELIOS Add-On connection status to the newly connected viewer
    await websocket.send_json(helios_bridge.get_status_dict())

    try:
        while True:
            raw_msg = await websocket.receive_text()
            payload = json.loads(raw_msg)
            msg_type = payload.get("type")

            if msg_type == "speak_line":
                text = str(payload.get("text") or "").strip()
                if not text:
                    continue
                voice = str(payload.get("voice") or KOKORO_VOICE).strip()
                helios_bridge.default_voice = voice
                expr = str(payload.get("emotion") or "relaxed").strip()
                anim = str(payload.get("animation") or "idle").strip()
                tts_data = await synthesize_tts_async(text, voice, expr)
                await websocket.send_json({
                    "type": "tts_chunk",
                    "step_index": 0,
                    "clause_index": 0,
                    "action_type": "speak",
                    "movement": "idle",
                    "text": text,
                    "dialogue": text,
                    "emotion": expr,
                    "expression": expr,
                    "expression_weight": 0.85,
                    "animation": anim,
                    "blendshape_weights": {expr: 0.85},
                    "mime_type": tts_data["mime_type"],
                    "audio_b64": tts_data["audio_b64"],
                    "sample_rate": tts_data["sample_rate"],
                    "duration": tts_data["duration"],
                    "rms": tts_data["rms"],
                    "visemes": tts_data["visemes"],
                    "is_voice_preview": True,
                })
                await websocket.send_json({"type": "chat_done", "is_voice_preview": True})
                continue

            if msg_type == "chat_message":
                user_text = payload.get("text", "").strip()
                if not user_text:
                    continue
                selected_voice = str(payload.get("voice") or KOKORO_VOICE).strip()
                helios_bridge.default_voice = selected_voice
                requested_mode = payload.get("brain_mode")
                if requested_mode in ("auto", "helios", "standalone"):
                    helios_bridge.mode = requested_mode

                history.append({"role": "user", "content": user_text})

                # 1. Enter Thinking state with finger-on-chin pose while querying HELIOS or Standalone LLM
                await websocket.send_json({
                    "type": "state_change",
                    "state": "thinking",
                    "pose": "think_pose",
                })

                # 2. Try HELIOS Core first (unless standalone mode is selected), then fallback to Riko Agent
                decision = await helios_bridge.query_via_helios(user_text)
                if decision is None:
                    decision = await query_riko_agent(history, user_text)
                    decision["source"] = "standalone"

                history.append({"role": "assistant", "content": json.dumps(decision)})

                if len(history) > 17:
                    history = [history[0]] + history[-16:]

                # 3. Stream full structured agent_sequence + sentence-level TTS to viewer
                await helios_bridge.stream_decision_to_viewer(
                    decision,
                    selected_voice,
                    target_ws=websocket,
                )

    except WebSocketDisconnect:
        print("[Riko Server] Client disconnected from WebSocket")
    except Exception as e:
        print(f"[Riko Server] WebSocket error: {e}")
    finally:
        helios_bridge.active_viewers.discard(websocket)


@app.websocket("/ws/chat")
async def websocket_chat_endpoint(websocket: WebSocket):
    await handle_riko_websocket(websocket)


@app.websocket("/ws")
async def websocket_legacy_endpoint(websocket: WebSocket):
    await handle_riko_websocket(websocket)


# Mount viewer directory last so /ws/chat and /ws take precedence and static assets serve at /
app.mount("/", StaticFiles(directory="viewer", html=True), name="viewer")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)



