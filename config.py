"""
AI Router — Configuration
All settings for the local AI model router system.
"""
import os
import psutil
from dotenv import load_dotenv

load_dotenv()

# ─── Network & Providers ──────────────────────────────────
# Choose "ollama" or "vllm" (for vLLM, LM Studio, SGLang, etc. running locally)
LLM_PROVIDER = "ollama"
OLLAMA_HOST = "http://127.0.0.1:11434"

# vLLM / LM Studio / SGLang Backend Settings (100% Local)
VLLM_API_BASE = "http://127.0.0.1:8000/v1"
VLLM_API_KEY = "sk-helios"

# Cloud Providers (Dynamic Escalation)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Model specific configurations
VISION_MODEL = "moondream:latest"


# ─── Models ────────────────────────────────────────────────
MODEL_CONFIG = {
    "phi3:mini": {
        "roles": ["system"],
        "priority": 1,
        "fallback": None
    },
    "qwen2.5-coder:1.5b": {
        "roles": ["tool_use", "system", "fast"],
        "priority": 2,
        "fallback": "phi3:mini"
    },
    "qwen2.5:7b": {
        "roles": ["general", "conversation", "fast"],
        "priority": 1,
        "fallback": "antigravity"
    },
    "antigravity": {
        "roles": ["general", "tool_use", "conversation", "vision"],
        "priority": 2,
        "fallback": "gemini-3.7-flash"
    },
    "gemini-3.7-flash": {
        "roles": ["general", "tool_use", "conversation", "vision", "fast"],
        "priority": 2,
        "fallback": "gemini-3.6-flash"
    },
    "gemini-3.6-flash": {
        "roles": ["general", "tool_use", "conversation", "vision"],
        "priority": 2,
        "fallback": "gemini-3.1-pro-preview"
    },
    "gemini-3.1-pro-preview": {
        "roles": ["reasoning", "complex"],
        "priority": 2,
        "fallback": "gemini-2.5-pro"
    },
    "gemini-2.5-pro": {
        "roles": ["reasoning", "complex"],
        "priority": 2,
        "fallback": "gemini-2.5-flash"
    },
    "gemini-2.5-flash": {
        "roles": ["general", "fast"],
        "priority": 2,
        "fallback": "gemini-3.5-flash-lite"
    },
    "gemini-3.5-flash-lite": {
        "roles": ["fast", "fallback"],
        "priority": 2,
        "fallback": "phi3:mini"
    },
    "deepseek-r1:7b": {
        "roles": ["reasoning", "research"],
        "priority": 1,
        "fallback": "llama3.1:8b"
    },
    "qwen2.5-coder:7b": {
        "roles": ["coding"],
        "priority": 1,
        "fallback": "llama3.1:8b"
    },
    "moondream:latest": {
        "roles": ["vision"],
        "priority": 1,
        "fallback": "llama3.1:8b"
    },
    "nomic-embed-text": {
        "roles": ["embedding", "rag"],
        "priority": 1,
        "fallback": None
    },
    "faster-whisper": {
        "roles": ["stt"],
        "priority": 1,
        "fallback": None
    },
    "gemini-3.6-flash": {
        "roles": ["general", "tool_use", "conversation", "vision"],
        "priority": 2,
        "fallback": "phi3:mini"
    },
    "piper": {
        "roles": ["tts"],
        "priority": 1,
        "fallback": None
    },
    "llama3.1:8b": {
        "roles": ["experimental_tool_model"],
        "priority":  1,
        "fallback": "phi3:mini"
    },
    "deepseek-coder-v2:16b": {
        "roles": ["heavy_coding"],
        "priority": 0,
        "fallback": "qwen2.5-coder:7b"
    }
}

# ─── Context Sizes (tokens) ───────────────────────────────
CONTEXT_SIZES = {
    "simple": 2048,
    "medium": 4096,
    "complex": 8192,
}

# ─── Keep Alive Durations ─────────────────────────────────
KEEP_ALIVE = {
    "default": "1h",
    "reuse_likely": "2h",
    "unload_now": 0,
}

# Fallback logic is now unified inside MODEL_CONFIG

# ─── RAM Management ───────────────────────────────────────
RAM_TOTAL_MB = 8192            # Windows Budget PC 8 GB
RAM_MIN_FREE_MB = 1024         # Keep at least 1 GB free for OS + browser (reduced for budget hardware)
RAM_CRITICAL_MB = 512          # Below this, force-unload everything
MODEL_CONTEXT_BUFFER_MB = 512  # Reduced padding for 4K context cap

# ─── Timeouts (seconds) ───────────────────────────────────
REQUEST_TIMEOUT = 120
HEALTH_CHECK_TIMEOUT = 5
MODEL_LOAD_TIMEOUT = 60

import os

# ─── System Prompt Templates ──────────────────────────────
def load_prompt(filename, default):
    filepath = os.path.join(os.path.dirname(__file__), "prompts", filename)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read().strip()
    return default

SYSTEM_PROMPTS = {
    "coding": load_prompt("coding.md", "You are HELIOS, an expert programming assistant."),
    "general": load_prompt("general.md", "You are HELIOS, an advanced AI assistant."),
    "reasoning": load_prompt("reasoning.md", "You are HELIOS, an expert engineer and problem solver."),
    "vision": load_prompt("vision.md", "You are HELIOS, a visual analysis assistant."),
    "ui": load_prompt("ui.md", "You are HELIOS, a UI designer."),
    "agent": load_prompt("agent.md", "You are HELIOS, an autonomous agent."),
}

# Voice Settings
VOICE_ENABLED = True
VOICE_BACKEND = "kokoro"
VOICE_NAME = "am_michael"
VOICE_SPEED = 1.0

# ─── Dynamic Budget Mode & Circuit Breaker ────────────────
CIRCUIT_BREAKER_TRIPPED = False
BUDGET_MAX_CONTEXT = 4096

def is_budget_mode_active() -> bool:
    """
    Returns True if free system RAM drops below 2 GB,
    unless the circuit breaker has been tripped by a failed
    eviction pipeline (in which case we revert to standard mode
    to prevent infinite retry loops).
    """
    if CIRCUIT_BREAKER_TRIPPED:
        return False
    free_ram_mb = psutil.virtual_memory().available / (1024 * 1024)
    return free_ram_mb < 2048