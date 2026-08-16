"""
AI Router — Configuration
All settings for the local AI model router system.
"""

# ─── Network ───────────────────────────────────────────────
OLLAMA_HOST = "http://100.75.42.67:11434"
MAC_IP = "100.75.42.67"
MAC_USER = "krithik"
OLLAMA_PATH = "/Applications/Ollama.app/Contents/Resources/ollama"

# ─── Models ────────────────────────────────────────────────
MODEL_CONFIG = {
    "qwen3:4b": {
        "roles": ["fast", "system"],
        "priority": 1,
        "fallback": None
    },
    "qwen3:8b": {
        "roles": ["general", "tool_use", "conversation"],
        "priority": 1,
        "fallback": "qwen3:4b"
    },
    "deepseek-r1:7b": {
        "roles": ["reasoning", "research"],
        "priority": 1,
        "fallback": "qwen3:8b"
    },
    "qwen2.5-coder:7b": {
        "roles": ["coding"],
        "priority": 1,
        "fallback": "qwen3:8b"
    },
    "llava:latest": {
        "roles": ["vision"],
        "priority": 1,
        "fallback": "qwen3:8b"
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
    "piper": {
        "roles": ["tts"],
        "priority": 1,
        "fallback": None
    },
    "llama3.1:8b": {
        "roles": ["experimental_tool_model"],
        "priority": 0,
        "fallback": "qwen3:8b"
    },
    "hermes3:8b": {
        "roles": ["experimental_tool_model"],
        "priority": 0,
        "fallback": "qwen3:8b"
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
RAM_TOTAL_MB = 16384          # Mac mini 16 GB
RAM_MIN_FREE_MB = 2048        # Keep at least 2 GB free
RAM_CRITICAL_MB = 1024        # Below this, force-unload everything

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
