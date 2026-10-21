import re
import os
from typing import Dict, Any, List, Tuple

class ZeroLeakFilter:
    """HELIOS Zero-Leak Protocol: Sanitizes outbound prompts, logs, and tool parameters to prevent PII and secret leaks."""

    REDACTION_PATTERNS = [
        # Secret Keys & Tokens
        (re.compile(r"sk-[a-zA-Z0-9_\-]{20,}", re.IGNORECASE), "[REDACTED_API_KEY]"),
        (re.compile(r"ghp_[a-zA-Z0-9]{30,}", re.IGNORECASE), "[REDACTED_GH_TOKEN]"),
        (re.compile(r"AIza[0-9A-Za-z\-_]{35}", re.IGNORECASE), "[REDACTED_GOOGLE_KEY]"),
        (re.compile(r"HELIOS_SECRET_[a-zA-Z0-9]{16,}", re.IGNORECASE), "[REDACTED_HELIOS_SECRET]"),
        # Environment Variable Declarations & System Secrets
        (re.compile(r"(?:export|set|env)\s+([A-Za-z0-9_]*(?:KEY|SECRET|TOKEN|PASS|PASSWORD|AUTH|CRED)[A-Za-z0-9_]*)\s*=\s*[^\s\r\n'\"]+", re.IGNORECASE), "[REDACTED_ENV_VAR]"),
        (re.compile(r"(?:api[_-]?key|secret|password|passwd|auth[_-]?token)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-~]{8,})['\"]?", re.IGNORECASE), "[REDACTED_CREDENTIAL]"),
        
        # Local Windows & Unix Absolute File Paths
        (re.compile(r"[A-Za-z]:\\(?:Users|Documents|AppData|Windows|Program Files)[^\s\"'<>|?*]+", re.IGNORECASE), "[REDACTED_LOCAL_PATH]"),
        (re.compile(r"/(?:home|Users|root)/[^\s\"'<>|?*]+", re.IGNORECASE), "[REDACTED_LOCAL_PATH]"),

        # Private Local Subnet IPv4 Addresses
        (re.compile(r"\b192\.168\.\d{1,3}\.\d{1,3}\b"), "[REDACTED_LOCAL_IP]"),
        (re.compile(r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "[REDACTED_LOCAL_IP]"),
        (re.compile(r"\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b"), "[REDACTED_LOCAL_IP]"),

        # Personal Contact Information
        (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"), "[REDACTED_EMAIL]"),
        (re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[REDACTED_PHONE]")
    ]

    @classmethod
    def sanitize_text(cls, text: str) -> Tuple[str, int]:
        """Scrubs text for sensitive credentials and paths. Returns (sanitized_text, count_redactions)."""
        if not text:
            return text, 0

        sanitized = text
        total_redactions = 0
        for pattern, replacement in cls.REDACTION_PATTERNS:
            matches = len(pattern.findall(sanitized))
            if matches > 0:
                sanitized = pattern.sub(replacement, sanitized)
                total_redactions += matches

        return sanitized, total_redactions

    @classmethod
    def sanitize_dict(cls, data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        """Recursively sanitizes dictionary strings."""
        sanitized_dict = {}
        total = 0
        for k, v in data.items():
            if isinstance(v, str):
                s_val, c = cls.sanitize_text(v)
                sanitized_dict[k] = s_val
                total += c
            elif isinstance(v, dict):
                s_val, c = cls.sanitize_dict(v)
                sanitized_dict[k] = s_val
                total += c
            elif isinstance(v, list):
                s_list = []
                for item in v:
                    if isinstance(item, str):
                        s_item, c = cls.sanitize_text(item)
                        s_list.append(s_item)
                        total += c
                    else:
                        s_list.append(item)
                sanitized_dict[k] = s_list
            else:
                sanitized_dict[k] = v
        return sanitized_dict, total

    @staticmethod
    def enforce_local_telemetry_block():
        """Locks down third-party libraries from transmitting outbound telemetry."""
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        os.environ["ANONYMIZED_TELEMETRY"] = "False"
        os.environ["DO_NOT_TRACK"] = "1"
        os.environ["SCARF_NO_ANALYTICS"] = "true"
        os.environ["POSTHOG_DISABLED"] = "1"
        os.environ["OLLAMA_ORIGINS"] = "http://localhost:*,http://127.0.0.1:*"
