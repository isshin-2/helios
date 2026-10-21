"""
AI Router - Configuration
All settings for the local AI model router system.
"""
import os
import psutil
from dotenv import load_dotenv

load_dotenv()

# --- Identity & Personality -------------------------------
BOT_NAME = os.environ.get("BOT_NAME", "HELIOS")
USER_NAME = os.environ.get("USER_NAME", "User")
WAKE_WORD = os.environ.get("WAKE_WORD", "helios").lower()
PERSONALITY = os.environ.get("PERSONALITY", "helpful, professional, and concise")

# --- Network & Server Ports (Guaranteed Unique Across Functions) ---
SERVER_HOST = os.environ.get("HELIOS_BIND_HOST", os.environ.get("SERVER_HOST", "127.0.0.1"))
SERVER_PORT = int(os.environ.get("SERVER_PORT", "8000"))         # HELIOS Core FastAPI + WebSocket + VLA
HELIOS_WS_SECRET = os.environ.get("HELIOS_WS_SECRET", "").strip() # Optional shared secret for WebSocket auth
CHARACTER_PORT = int(os.environ.get("CHARACTER_PORT", "8080"))   # Airi 3D VRM Three.js Companion
METRO_PORT = int(os.environ.get("METRO_PORT", "8081"))           # Mobile Expo / React Native Metro Bundler
LIVE2D_PORT = int(os.environ.get("LIVE2D_PORT", "8085"))         # Standalone Live2D static viewer
PORTFOLIO_PORT = int(os.environ.get("PORTFOLIO_PORT", "5174"))   # Vite React 19 Engineering Portfolio
OLLAMA_PORT = int(os.environ.get("OLLAMA_PORT", "11434"))        # Local Ollama daemon
PAIR_PORT = int(os.environ.get("PAIR_PORT", "14321"))            # NVIDIA PAIR cluster inter-node
WOL_PORT = int(os.environ.get("WOL_PORT", "9"))                  # Wake-on-LAN UDP beacon

def get_service_ports() -> dict:
    return {
        "core_server": SERVER_PORT,
        "character_vrm": CHARACTER_PORT,
        "mobile_metro": METRO_PORT,
        "live2d_viewer": LIVE2D_PORT,
        "portfolio": PORTFOLIO_PORT,
        "ollama_daemon": OLLAMA_PORT,
        "pair_cluster": PAIR_PORT,
    }

def validate_unique_ports():
    ports = get_service_ports()
    seen = {}
    for service, port in ports.items():
        if port in seen:
            raise ValueError(f"Port collision detected: '{service}' and '{seen[port]}' both use port {port}")
        seen[port] = service
    return True

validate_unique_ports()

# --- Network & Providers ----------------------------------
# Choose "pair", "ollama", "localai", "vllm", "openrouter", "gemini", or "airllm"
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "pair")

ENABLE_LOCAL_MODELS = os.environ.get("ENABLE_LOCAL_MODELS", "True").lower() == "true"
# NVIDIA PAIR Node Settings (Dedicated NVIDIA GPU Workstation)
AI_PC_IP = os.environ.get("AI_PC_IP", "192.168.100.254")
AI_PC_MAC = os.environ.get("AI_PC_MAC", "30:56:0F:A8:76:05")
AI_PC_BROADCAST = os.environ.get("AI_PC_BROADCAST", "192.168.100.255")
AI_PC_WAKE_SCRIPT = os.environ.get("AI_PC_WAKE_SCRIPT", "")
AUTO_WAKE_AI_PC = os.environ.get("AUTO_WAKE_AI_PC", "True").lower() == "true"

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
PAIR_HOST = os.environ.get("PAIR_HOST", f"http://{AI_PC_IP}:11434")

# vLLM / LM Studio / SGLang Backend Settings (100% Local)
VLLM_API_BASE = os.environ.get("VLLM_API_BASE", "http://127.0.0.1:8000/v1")
VLLM_API_KEY = os.environ.get("VLLM_API_KEY", "sk-helios")  # Local vLLM/LM Studio dummy key — override via env

# Cloud Providers (Dynamic Escalation)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# FreeLLMAPI (Unified Zero-Cost Free-Tier Proxy / Port 3001)
FREELLMAPI_URL = os.environ.get("FREELLMAPI_URL", "http://localhost:3001/v1")
FREELLMAPI_API_KEY = os.environ.get("FREELLMAPI_API_KEY", "freellmapi-default-key")
FREELLMAPI_DEFAULT_MODEL = os.environ.get("FREELLMAPI_DEFAULT_MODEL", "auto")

# --- UI & Interaction -------------------------------------
# If True, AskUserTool will spawn a native desktop GUI overlay. 
# If False (e.g. running in Docker), it will fallback to standard terminal output.
ENABLE_TENSURA_OVERLAY = os.environ.get("ENABLE_TENSURA_OVERLAY", "True").lower() == "true"

# If True, the main HELIOS Tensura-style Desktop App will launch automatically with the server.
ENABLE_DESKTOP_APP = os.environ.get("ENABLE_DESKTOP_APP", "True").lower() == "true"

# Model specific configurations
VISION_MODEL = os.environ.get("VISION_MODEL", "moondream:latest")

MODEL_CONFIG = {
    # Fast / Background (Low Latency)
    "phi4:mini": {"type": "fast", "max_tokens": 2048, "cloud_fallback": "groq/openai/gpt-oss-20b"},
    "llama3.2:3b": {"type": "fast", "max_tokens": 4096, "cloud_fallback": "groq/openai/gpt-oss-20b"},
    "helios-avatar:latest": {"type": "fast", "max_tokens": 2048, "cloud_fallback": "groq/openai/gpt-oss-20b"},
    
    # Base / General (Core Workhorses)
    "qwen3.5:4b": {"type": "general", "max_tokens": 4096, "fallback": "llama3.2:3b", "cloud_fallback": "groq/openai/gpt-oss-20b"},
    "qwen3.5:9b": {"type": "general", "max_tokens": 4096, "fallback": "qwen2.5-coder:7b", "cloud_fallback": "groq/openai/gpt-oss-20b"},
    "ministral3:8b": {"type": "general", "max_tokens": 4096, "fallback": "llama3.2:3b", "cloud_fallback": "groq/openai/gpt-oss-20b"},
    
    # Tool Use / System
    "hermes3:8b": {"type": "tool_use", "max_tokens": 8192, "fallback": "qwen2.5-coder:7b", "cloud_fallback": "google/gemini-3.6-flash"},
    
    # Reasoning
    "qwen3.6-thinking:9b": {"type": "reasoning", "max_tokens": 8192, "fallback": "qwen2.5-coder:14b", "cloud_fallback": "google/gemini-3.1-pro-preview"},
    
    # Coding / Agentic (Best-in-class for 16 GB VRAM + 64 GB RAM)
    "qwen2.5-coder:32b": {"type": "coding", "max_tokens": 32768, "fallback": "qwen2.5-coder:14b", "cloud_fallback": "google/gemini-3.1-pro-preview"},
    "qwen2.5-coder:14b": {"type": "coding", "max_tokens": 16000, "fallback": "qwen2.5-coder:7b", "cloud_fallback": "google/gemini-3.1-pro-preview"},
    "qwen2.5-coder:7b": {"type": "coding", "max_tokens": 8192, "fallback": "llama3.2:3b", "cloud_fallback": "google/gemini-3.6-flash"},
    "devstral-small-2:24b": {"type": "coding", "max_tokens": 16000, "fallback": "qwen2.5-coder:14b", "cloud_fallback": "google/gemini-3.1-pro-preview"},
    "ornith:9b": {"type": "coding", "max_tokens": 8192, "fallback": "qwen2.5-coder:7b", "cloud_fallback": "google/gemini-3.1-pro-preview"},
    "gemma4:12b": {"type": "coding", "max_tokens": 16000, "cloud_fallback": "google/gemini-3.1-pro-preview"},
    
    # Vision
    "moondream:latest": {"type": "vision", "max_tokens": 2048, "cloud_fallback": "google/gemini-3.6-flash"},
    "qwen3-vl:8b": {"type": "vision", "max_tokens": 4096, "cloud_fallback": "google/gemini-3.6-flash"},
    
    # Cloud models (Fallbacks)
    "google/gemini-3.6-flash": {"type": "agent", "max_tokens": 8192, "cloud_fallback": "google/gemini-3.1-pro-preview"},
    "google/gemini-1.5-pro": {"type": "agent", "max_tokens": 32000, "cloud_fallback": "google/gemini-3.1-pro-preview"},
    "google/gemini-3.1-pro-preview": {"type": "agent", "max_tokens": 64000, "cloud_fallback": "groq/openai/gpt-oss-20b"},
}

# --- RAM Management ---------------------------------------
try:
    from core.hardware_profiler import detect_hardware
    RAM_TOTAL_MB = int(detect_hardware().ram_total_gb * 1024)
except Exception:
    RAM_TOTAL_MB = 8192            # Fallback for Windows Budget PC 8 GB

RAM_MIN_FREE_MB = 256         # Keep at least 1 GB free for OS + browser (reduced for budget hardware)
RAM_CRITICAL_MB = 128          # Below this, force-unload everything
MODEL_CONTEXT_BUFFER_MB = 512  # Reduced padding for 4K context cap

# --- Timeouts (seconds) -----------------------------------
REQUEST_TIMEOUT = 120
HEALTH_CHECK_TIMEOUT = 5
MODEL_LOAD_TIMEOUT = 60

# --- Character Addon Settings (Section 17) ----------------
CHARACTER_ENABLED = os.environ.get("CHARACTER_ENABLED", "true").lower() == "true"
CHARACTER_RENDERER = os.environ.get("CHARACTER_RENDERER", "vrm")
CHARACTER_MODEL = os.environ.get("CHARACTER_MODEL", "helios-v1")

# --- System Prompt Templates ------------------------------
def load_prompt(filename, default):
    filepath = os.path.join(os.path.dirname(__file__), "prompts", filename)
    content = default
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()
            
    # Inject personality and identity
    content = content.replace("HELIOS", BOT_NAME)
    
    # Add personality trait block to the end of the system prompt if not present
    personality_block = f"\n\n[PERSONALITY TRAIT: {PERSONALITY}]"
    if personality_block not in content:
        content += personality_block

    if CHARACTER_ENABLED:
        avatar_block = (
            "\n\n[EMBODIED 3D VRM AVATAR & MOVEMENT PROTOCOL]: You are Airi, embodied in a real-time 3D Techwear VRM avatar body. "
            "You directly control your 3D room navigation (`move`: walk_to_user, step_back, circle_user, return_center, stay), "
            "full-body 2-bone IK poses & tricks (`pose`: wave, nod, peace, cheer, shrug, bow, confident, shy, smug_pose, "
            "refuse, hug_attempt, dance_shikano, backflip, think_pose, talk_explain, talk_excited, talk_smug, "
            "cyber_salute, superhero_landing, martial_arts_guard, double_biceps_flex, facepalm, zen_meditation, "
            "point_forward, hands_up_surrender, cyber_dab, rock_on_pose), and "
            "emotional expression (`emotion`: neutral, happy, amused, curious, excited, concerned, serious, confused).\n"
            "You can ALSO invent brand-new custom 3D poses on your own by including `[POSE_JSON: {\"name\": \"custom_name\", \"hipsOffsetY\": 0.0, "
            "\"leftHandShape\": \"open|fist|peace|point|salute|thumbs_up|rock_on\", \"rightHandShape\": \"...\", "
            "\"bones\": {\"spine\": [pitch, yaw, roll], \"head\": [pitch, yaw, roll], \"leftUpperLeg\": [...], \"rightUpperLeg\": [...]}, "
            "\"ik\": {\"rightWrist\": {\"anchor\": \"head|chest|hips|shoulder\", \"offset\": [x, y, z]}, \"leftWrist\": {...}}}]`.\n"
            "Begin every reply with a `[BODY: move=<move>, pose=<pose>, emotion=<emotion>]` tag to drive your 3D rig:\n"
            "- User: 'Give me a salute!' -> `[BODY: move=stay, pose=cyber_salute, emotion=serious]` Reporting for duty, Commander!\n"
            "- User: 'Do a superhero landing!' -> `[BODY: move=stay, pose=superhero_landing, emotion=excited]` Dropping in for a three-point superhero landing!\n"
            "- User: 'Walk closer and wave!' -> `[BODY: move=walk_to_user, pose=wave, emotion=happy]` Hey there! Walking right up to you!\n"
            "- User: 'Do a backflip!' -> `[BODY: move=stay, pose=backflip, emotion=excited]` Watch this! Launching a full 360 backflip!\n"
            "NEVER say you lack a physical body—always move your 3D VRM body enthusiastically in character as Airi!"
        )
        if "[EMBODIED 3D VRM AVATAR" not in content:
            content += avatar_block

    return content

SYSTEM_PROMPTS = {
    "coding": load_prompt("coding.md", f"You are {BOT_NAME}, an expert programming assistant."),
    "general": load_prompt("general.md", f"You are {BOT_NAME}, an advanced AI assistant."),
    "reasoning": load_prompt("reasoning.md", f"You are {BOT_NAME}, an expert engineer and problem solver."),
    "vision": load_prompt("vision.md", f"You are {BOT_NAME}, a visual analysis assistant."),
    "ui": load_prompt("ui.md", f"You are {BOT_NAME}, a UI designer."),
    "agent": load_prompt("agent.md", f"You are {BOT_NAME}, an autonomous agent."),
}

# Voice Settings
VOICE_ENABLED = os.environ.get("VOICE_ENABLED", "true").lower() == "true"
VOICE_BACKEND = os.environ.get("VOICE_BACKEND", "kokoro")
VOICE_NAME = os.environ.get("VOICE_NAME", "af_heart")
VOICE_SPEED = float(os.environ.get("VOICE_SPEED", "1.0"))

# Extended TTS / Speech Pipeline Settings
VOICE_PROSODY_ENABLED = os.environ.get("VOICE_PROSODY_ENABLED", "true").lower() == "true"
VOICE_NORMALIZATION_ENABLED = os.environ.get("VOICE_NORMALIZATION_ENABLED", "true").lower() == "true"
VOICE_PRONUNCIATION_ENABLED = os.environ.get("VOICE_PRONUNCIATION_ENABLED", "true").lower() == "true"
VOICE_AUDIO_PROCESSING_ENABLED = os.environ.get("VOICE_AUDIO_PROCESSING_ENABLED", "true").lower() == "true"
VOICE_LIPSYNC_ENABLED = os.environ.get("VOICE_LIPSYNC_ENABLED", "true").lower() == "true"
VOICE_PROSODY_PROFILE = os.environ.get("VOICE_PROSODY_PROFILE", "helios")
VOICE_AUDIO_HIGHPASS_CUTOFF = float(os.environ.get("VOICE_AUDIO_HIGHPASS_CUTOFF", "70.0"))
VOICE_AUDIO_COMPRESSION_ENABLED = os.environ.get("VOICE_AUDIO_COMPRESSION_ENABLED", "true").lower() == "true"
VOICE_AUDIO_LIMITER_CEILING_DB = float(os.environ.get("VOICE_AUDIO_LIMITER_CEILING_DB", "-1.0"))
VOICE_AUDIO_COMPRESSION_RATIO = float(os.environ.get("VOICE_AUDIO_COMPRESSION_RATIO", "2.0"))

# --- GPT-SoVITS Settings ---
GPT_SOVITS_ENABLED = os.environ.get("GPT_SOVITS_ENABLED", "true").lower() == "true"

def _resolve_default_gpt_sovits_url() -> str:
    explicit_url = os.environ.get("GPT_SOVITS_API_URL")
    # If using remote NVIDIA PAIR or AI PC node, co-locate GPT-SoVITS on the same hosting node unless user explicitly set a non-default remote address
    if LLM_PROVIDER == "pair" and AI_PC_IP and AI_PC_IP not in ("127.0.0.1", "localhost"):
        if not explicit_url or explicit_url in ("http://127.0.0.1:9880", "http://localhost:9880"):
            return f"http://{AI_PC_IP}:9880"
    if explicit_url:
        return explicit_url.rstrip("/")
    return "http://127.0.0.1:9880"

GPT_SOVITS_API_URL = _resolve_default_gpt_sovits_url()
GPT_SOVITS_MODEL_PATH = os.environ.get("GPT_SOVITS_MODEL_PATH", "")
GPT_SOVITS_SOVITS_PATH = os.environ.get("GPT_SOVITS_SOVITS_PATH", "")
GPT_SOVITS_REF_AUDIO = os.environ.get("GPT_SOVITS_REF_AUDIO", "")
GPT_SOVITS_REF_TEXT = os.environ.get("GPT_SOVITS_REF_TEXT", "")
GPT_SOVITS_LANGUAGE = os.environ.get("GPT_SOVITS_LANGUAGE", "en")
GPT_SOVITS_DEVICE = os.environ.get("GPT_SOVITS_DEVICE", "auto")

# --- Resource Manager Settings ---
RESOURCES_CONFIG_PATH = os.environ.get("RESOURCES_CONFIG_PATH", "config/resources.yaml")
GPU_RESERVE_MB = float(os.environ.get("GPU_RESERVE_MB", "2048.0"))
RAM_RESERVE_GB = float(os.environ.get("RAM_RESERVE_GB", "8.0"))
RAM_CACHE_LIMIT_GB = float(os.environ.get("RAM_CACHE_LIMIT_GB", "32.0"))
TTS_IDLE_UNLOAD_SECONDS = float(os.environ.get("TTS_IDLE_UNLOAD_SECONDS", "300.0"))

# --- Set-of-Mark Vision Overlay ---------------------------
SOM_ENABLED = True
SOM_MIN_ELEMENT_THRESHOLD = 3

# --- Dynamic Budget Mode & Circuit Breaker ----------------
CIRCUIT_BREAKER_TRIPPED = False
BUDGET_MAX_CONTEXT = 4096

# --- Audio / STT Settings ---
STT_BACKEND = "whisper"  # "whisper" or "google"
WHISPER_MODEL_PATH = ".models/whisper/ggml-base.en.bin"
WHISPER_FALLBACK_MODEL_PATH = ".models/whisper/ggml-tiny.en.bin"
RMS_BARGE_IN_THRESHOLD = 1500

# --- Vision Settings ---
FALLBACK_VISION_MODEL = "moondream:latest"

# --- Hybrid / Thin-Client Settings ---
HYBRID_MODE = False
HYBRID_REMOTE_URL = "ws://localhost:8001/ws"

def is_budget_mode_active() -> bool:
    mem = psutil.virtual_memory()
    available_mb = mem.available / (1024 * 1024)
    return available_mb < RAM_MIN_FREE_MB

def check_circuit_breaker() -> bool:
    global CIRCUIT_BREAKER_TRIPPED
    mem = psutil.virtual_memory()
    available_mb = mem.available / (1024 * 1024)
    if available_mb < RAM_CRITICAL_MB:
        CIRCUIT_BREAKER_TRIPPED = True
        return True
    CIRCUIT_BREAKER_TRIPPED = False
    return False

def reset_circuit_breaker():
    global CIRCUIT_BREAKER_TRIPPED
    CIRCUIT_BREAKER_TRIPPED = False


# --- Skills Validation Settings ---
SKILLS_VALIDATION_ENABLED = os.environ.get("SKILLS_VALIDATION_ENABLED", "true").lower() == "true"
SKILLSPECTOR_LLM_ANALYSIS = os.environ.get("SKILLSPECTOR_LLM_ANALYSIS", "false").lower() == "true"
SKILLS_VALIDATION_TIMEOUT = int(os.environ.get("SKILLS_VALIDATION_TIMEOUT", "60"))
SKILLS_REJECT_CAUTION = os.environ.get("SKILLS_REJECT_CAUTION", "true").lower() == "true"
SKILLS_QUARANTINE_ENABLED = os.environ.get("SKILLS_QUARANTINE_ENABLED", "true").lower() == "true"


# ─── Context Sizes (tokens) ───────────────────────────────
CONTEXT_SIZES = {
    "simple": 2048,
    "medium": 4096,
    "complex": 8192,
}


# ─── Keep Alive Durations ───────────────────────────────
KEEP_ALIVE = {
    "default": "1h",
    "reuse_likely": "2h",
    "unload_now": 0,
}




