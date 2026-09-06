"""
AI Router – Configuration
All settings for the local AI model router system.
"""
import os
import psutil
from dotenv import load_dotenv

load_dotenv()

# --- Identity & Personality -------------------------------
BOT_NAME = os.environ.get("BOT_NAME", "HELIOS")
WAKE_WORD = os.environ.get("WAKE_WORD", "helios").lower()
PERSONALITY = os.environ.get("PERSONALITY", "helpful, professional, and concise")

# --- Network & Providers ----------------------------------
# Choose "ollama" or "vllm" (for vLLM, LM Studio, SGLang, etc. running locally)
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "ollama")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

# vLLM / LM Studio / SGLang Backend Settings (100% Local)
VLLM_API_BASE = os.environ.get("VLLM_API_BASE", "http://127.0.0.1:8000/v1")
VLLM_API_KEY = "sk-helios"

# Cloud Providers (Dynamic Escalation)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# Model specific configurations
VISION_MODEL = os.environ.get("VISION_MODEL", "qwen2.5vl:3b")

MODEL_CONFIG = {
    # Tiny, hyper-fast models (<3B params)
    "qwen2.5:1.5b": {"type": "base", "max_tokens": 1024, "cloud_fallback": "gemini-3.5-flash-lite"},
    "deepseek-coder:1.3b": {"type": "coding", "max_tokens": 1500, "cloud_fallback": "gemini-3.5-flash-lite"},
    
    # Capable edge models (3B-8B params) - Core Workhorses
    "llama3.2:3b": {"type": "base", "max_tokens": 2048, "cloud_fallback": "gemini-3.5-flash-lite"},
    "phi3.5:3.8b": {"type": "reasoning", "max_tokens": 4096, "cloud_fallback": "gemini-3.5-flash-lite"},
    "qwen2.5-coder:7b": {"type": "coding", "max_tokens": 4096, "cloud_fallback": "gemini-3.7-flash"},
    
    # Vision models
    "llava:7b": {"type": "vision", "max_tokens": 1024, "cloud_fallback": "gemini-3.7-flash"},
    "qwen2.5vl:3b": {"type": "vision", "max_tokens": 1024, "cloud_fallback": "gemini-3.7-flash"},
    
    # Heavy Duty / Reasoning Models (Fallback to Cloud if RAM is tight)
    "deepseek-r1:8b": {"type": "reasoning", "max_tokens": 8192, "cloud_fallback": "deepseek-reasoner"},
    "qwen2.5:14b": {"type": "general", "max_tokens": 4096, "cloud_fallback": "google/gemini-pro-1.5"},
    "llama3.1:8b": {"type": "general", "max_tokens": 4096, "cloud_fallback": "anthropic/claude-3-haiku"},
}

# --- RAM Management ---------------------------------------
RAM_TOTAL_MB = 8192            # Windows Budget PC 8 GB
RAM_MIN_FREE_MB = 1024         # Keep at least 1 GB free for OS + browser (reduced for budget hardware)
RAM_CRITICAL_MB = 512          # Below this, force-unload everything
MODEL_CONTEXT_BUFFER_MB = 512  # Reduced padding for 4K context cap

# --- Timeouts (seconds) -----------------------------------
REQUEST_TIMEOUT = 120
HEALTH_CHECK_TIMEOUT = 5
MODEL_LOAD_TIMEOUT = 60

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
VOICE_NAME = os.environ.get("VOICE_NAME", "am_michael")
VOICE_SPEED = float(os.environ.get("VOICE_SPEED", "1.0"))

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
