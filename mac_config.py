"""
AI Router — Configuration
All settings for the local AI model router system.
"""

# ─── Network ───────────────────────────────────────────────
OLLAMA_HOST = "http://192.168.100.111:11434"
MAC_IP = "192.168.100.111"
MAC_USER = "krithik"
OLLAMA_PATH = "/Applications/Ollama.app/Contents/Resources/ollama"

# ─── Models ────────────────────────────────────────────────
MODELS = {
    "fast": "qwen3:4b",
    "general": "qwen3:8b",
    "coding": "qwen2.5-coder:7b",
    "reasoning": "deepseek-r1:7b",
    "vision": "llava",
    "embedding": "nomic-embed-text",
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

# ─── Fallback Chains ──────────────────────────────────────
# If primary model fails, try these in order
FALLBACK_CHAINS = {
    "qwen2.5-coder:7b": ["qwen3:8b", "qwen3:4b"],
    "deepseek-r1:7b": ["qwen3:8b", "qwen3:4b"],
    "qwen3:8b": ["qwen3:4b"],
    "llava": ["qwen3:8b", "qwen3:4b"],
    "qwen3:4b": [],
    "nomic-embed-text": [],
}

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
