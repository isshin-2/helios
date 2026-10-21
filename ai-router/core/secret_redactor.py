"""
HELIOS — Secret Redactor
========================
Scrubs API keys, bearer tokens, and other secrets from strings before they
are written to logs, telemetry, checkpoints, or exported configurations.

Usage:
    from core.secret_redactor import redact

    safe_text = redact(raw_text)

The redactor uses regex patterns that match the shapes of known secret types.
It replaces matched values with a fixed placeholder that preserves the
secret's type label for debugging without exposing the value.

IMPORTANT: This is a best-effort defence-in-depth layer.
- It cannot redact secrets in binary blobs or compressed data.
- It will not find secrets that are structurally identical to normal text.
- Providers must NEVER pass raw keys into prompts or log lines.
"""

from __future__ import annotations

import re
import logging
from typing import Any

logger = logging.getLogger("helios.secret_redactor")

# ---------------------------------------------------------------------------
# Pattern registry
# Each entry: (label, compiled_regex)
# Patterns ordered from most specific to most general to reduce false-positives.
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[str, re.Pattern]] = [
    # Google Gemini / AIStudio
    ("GEMINI_KEY", re.compile(r'AIza[0-9A-Za-z_\-]{35}', re.ASCII)),
    # OpenAI / OpenRouter / compatible  (sk-...)
    ("OPENAI_KEY", re.compile(r'sk-[A-Za-z0-9]{20,}', re.ASCII)),
    # Groq
    ("GROQ_KEY", re.compile(r'gsk_[A-Za-z0-9]{40,}', re.ASCII)),
    # Anthropic
    ("ANTHROPIC_KEY", re.compile(r'sk-ant-[A-Za-z0-9\-]{50,}', re.ASCII)),
    # NVIDIA NIM
    ("NVIDIA_KEY", re.compile(r'nvapi-[A-Za-z0-9\-_]{30,}', re.ASCII)),
    # Bearer tokens in Authorization headers
    ("BEARER_TOKEN", re.compile(
        r'(?i)(authorization\s*[:=]\s*bearer\s+)[A-Za-z0-9\-._~+/]+=*',
        re.ASCII,
    )),
    # Generic API key assignment patterns: api_key="...", "api_key": "..."
    ("API_KEY_ASSIGNMENT", re.compile(
        r'(?i)(api[_-]?key\s*[=:]\s*["\']?)([A-Za-z0-9\-._]{20,})(["\']?)',
        re.ASCII,
    )),
    # env-var style: VARIABLE_NAME=VALUE (only high-entropy values)
    # Heuristic: 30+ chars, mix of upper/lower/digit
    ("ENV_SECRET", re.compile(
        r'(?i)([A-Z_]{3,}_(?:KEY|SECRET|TOKEN|PASSWORD)\s*=\s*)([A-Za-z0-9+/]{30,}={0,2})',
        re.ASCII,
    )),
]

_PLACEHOLDER_FMT = "[REDACTED:{label}]"


def redact(text: str) -> str:
    """Return `text` with all detected secrets replaced by safe placeholders."""
    if not isinstance(text, str) or not text:
        return text

    for label, pattern in _PATTERNS:
        placeholder = _PLACEHOLDER_FMT.format(label=label)

        if label == "BEARER_TOKEN":
            # Keep "Authorization: Bearer " prefix, redact token
            text = pattern.sub(lambda m: m.group(1) + placeholder, text)
        elif label in ("API_KEY_ASSIGNMENT", "ENV_SECRET"):
            # Keep the key name, redact the value
            text = pattern.sub(lambda m, p=placeholder: m.group(1) + p, text)
        else:
            text = pattern.sub(placeholder, text)

    return text


def redact_dict(obj: Any) -> Any:
    """
    Recursively redact secrets from a dict/list/str structure.
    Returns a new object; does not mutate the original.
    """
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, dict):
        return {k: redact_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        result = [redact_dict(item) for item in obj]
        return type(obj)(result)
    return obj
