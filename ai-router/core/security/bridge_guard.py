import os
import sys
import hmac
import hashlib
import time
import json
import secrets
from typing import Dict, Any, Optional, Tuple

class IsolationViolationError(Exception):
    """Raised when an unauthorized cross-engine communication or data boundary crossing is detected."""
    pass

class BridgeGuard:
    """Zero-Trust HMAC Security Guard governing IPC between HELIOS, Hikari, and Solstice."""

    DEFAULT_CONFIG_PATH = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "bridge.json")
    )

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config = self._load_or_create_config()

    def _load_or_create_config(self) -> Dict[str, Any]:
        config_dir = os.path.dirname(self.config_path)
        os.makedirs(config_dir, exist_ok=True)

        if not os.path.exists(self.config_path):
            default_config = {
                "bridge_enabled": False,
                "bridge_secret": secrets.token_hex(32),
                "allowed_routes": {
                    "helios->hikari": ["task_dispatch", "status_query"],
                    "hikari->helios": ["task_result", "log_stream"],
                    "solstice->helios": ["user_input", "biometric_status"],
                    "helios->solstice": ["avatar_telemetry", "tts_playback"]
                },
                "token_max_age_seconds": 5,
                "log_bridge_traffic": True
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2)
            return default_config

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return {
                "bridge_enabled": False,
                "bridge_secret": secrets.token_hex(32),
                "allowed_routes": {},
                "token_max_age_seconds": 5
            }

    @property
    def is_enabled(self) -> bool:
        env_flag = os.getenv("BRIDGE_ENABLED", "").lower() in ("true", "1", "yes")
        return env_flag or bool(self.config.get("bridge_enabled", False))

    @property
    def secret(self) -> str:
        return os.getenv("BRIDGE_SECRET") or self.config.get("bridge_secret", "")

    def generate_token(self, source_engine: str, target_engine: str, action: str, timestamp: Optional[float] = None) -> Tuple[str, float]:
        """Generates an HMAC-SHA256 signature for cross-engine IPC."""
        ts = timestamp or time.time()
        message = f"{source_engine}:{target_engine}:{action}:{int(ts)}"
        sig = hmac.new(self.secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
        token = f"{int(ts)}.{sig}"
        return token, ts

    def validate_request(self, source_engine: str, target_engine: str, action: str, token: Optional[str]) -> bool:
        """Strictly validates cross-engine access. Raises IsolationViolationError if unauthorized."""
        if not self.is_enabled:
            raise IsolationViolationError(
                f"[HARD ISOLATION ENFORCED] Cross-engine IPC between '{source_engine}' and '{target_engine}' is blocked. "
                "Bridge is disabled. Set BRIDGE_ENABLED=true in .env or config/bridge.json to permit."
            )

        if not token:
            raise IsolationViolationError(
                f"[UNAUTHORIZED] Missing bridge authorization token for '{source_engine}' -> '{target_engine}'."
            )

        parts = token.split(".")
        if len(parts) != 2:
            raise IsolationViolationError("[MALFORMED TOKEN] Bridge token format must be '<timestamp>.<signature>'.")

        try:
            ts_int = int(parts[0])
            provided_sig = parts[1]
        except ValueError:
            raise IsolationViolationError("[MALFORMED TOKEN] Invalid timestamp in bridge token.")

        # Replay drift check
        now = int(time.time())
        max_age = self.config.get("token_max_age_seconds", 5)
        if abs(now - ts_int) > max_age:
            raise IsolationViolationError(
                f"[REPLAY / EXPIRED TOKEN] Token age {abs(now - ts_int)}s exceeds allowable drift ({max_age}s)."
            )

        # Route whitelist check
        route_key = f"{source_engine}->{target_engine}"
        allowed_actions = self.config.get("allowed_routes", {}).get(route_key, [])
        if action not in allowed_actions:
            raise IsolationViolationError(
                f"[FORBIDDEN ROUTE] Action '{action}' on route '{route_key}' is not declared in bridge.json manifest."
            )

        # HMAC signature verification
        expected_message = f"{source_engine}:{target_engine}:{action}:{ts_int}"
        expected_sig = hmac.new(self.secret.encode("utf-8"), expected_message.encode("utf-8"), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(provided_sig, expected_sig):
            raise IsolationViolationError("[SIGNATURE MISMATCH] Invalid HMAC bridge signature.")

        return True

_global_bridge_guard = None

def get_bridge_guard() -> BridgeGuard:
    global _global_bridge_guard
    if _global_bridge_guard is None:
        _global_bridge_guard = BridgeGuard()
    return _global_bridge_guard
