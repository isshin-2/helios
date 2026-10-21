"""
HELIOS Client — Configuration & Server Discovery
Manages server endpoint resolution, active presets, latency checks, and Wake-on-LAN.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import socket
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import urllib.request
import urllib.error

logger = logging.getLogger("helios.client.config")

CLIENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CLIENT_DIR.parent
CONFIG_FILE = CLIENT_DIR / "client_config.json"
AI_ROUTER_ENV = REPO_ROOT / "ai-router" / ".env"

# Server presets
SERVER_PRESETS: List[Dict[str, str]] = [
    {
        "id": "ai_pc",
        "name": "Dedicated AI PC (RTX 5060 Ti · 16GB)",
        "url": "http://192.168.100.254:8000",
        "ip": "192.168.100.254",
        "mac": "30:56:0F:A8:76:05",
        "broadcast": "192.168.100.255",
    },
    {
        "id": "localhost",
        "name": "Localhost Server (127.0.0.1:8000)",
        "url": "http://127.0.0.1:8000",
        "ip": "127.0.0.1",
        "mac": "",
        "broadcast": "127.0.0.1",
    },
]

DEFAULT_SERVER_URL = "http://192.168.100.254:8000"


def _read_env_ai_pc_ip() -> Optional[str]:
    """Inspect ai-router/.env if present on client machine."""
    if AI_ROUTER_ENV.exists():
        try:
            with open(AI_ROUTER_ENV, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("AI_PC_IP="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return f"http://{val}:8000"
        except Exception:
            pass
    return None


def load_client_config() -> Dict[str, Any]:
    """Load configuration dictionary from client_config.json."""
    data: Dict[str, Any] = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"Could not parse {CONFIG_FILE}: {e}")

    # Fallback to env or ai-router/.env
    if "server_url" not in data:
        env_url = os.environ.get("HELIOS_SERVER_URL")
        if env_url:
            data["server_url"] = env_url
        else:
            detected = _read_env_ai_pc_ip()
            data["server_url"] = detected or DEFAULT_SERVER_URL

    if "auto_connect_sidecar" not in data:
        data["auto_connect_sidecar"] = True
    if "client_name" not in data:
        data["client_name"] = socket.gethostname() or "HELIOS-Client"
    if "timeout" not in data:
        data["timeout"] = 15.0

    return data


def save_client_config(config: Dict[str, Any]) -> None:
    """Save configuration dictionary to client_config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write {CONFIG_FILE}: {e}")


def get_server_url() -> str:
    """Get active server URL, respecting env vars and configuration with automatic localhost fallback."""
    if os.environ.get("HELIOS_SERVER_URL"):
        return os.environ["HELIOS_SERVER_URL"].rstrip("/")
    cfg = load_client_config()
    configured = cfg.get("server_url", DEFAULT_SERVER_URL).rstrip("/")
    # If the target is a remote node that is offline, test if local HELIOS is running
    if "127.0.0.1" not in configured and "localhost" not in configured:
        try:
            h = check_server_health(configured, timeout=0.8)
            if not h["online"]:
                lh_check = check_server_health("http://127.0.0.1:8000", timeout=0.4)
                if lh_check["online"]:
                    logger.info(f"[CLIENT-DISCOVERY] Remote server ({configured}) unreachable; using active local server (http://127.0.0.1:8000)")
                    return "http://127.0.0.1:8000"
        except Exception:
            pass
    return configured


def set_server_url(url: str) -> None:
    """Update active server URL in client_config.json."""
    clean_url = url.strip().rstrip("/")
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = f"http://{clean_url}"
    cfg = load_client_config()
    cfg["server_url"] = clean_url
    save_client_config(cfg)
    os.environ["HELIOS_SERVER_URL"] = clean_url


def get_ws_url(path: str = "/ws", base_url: Optional[str] = None) -> str:
    """Derive WebSocket URL from HTTP server URL."""
    base = (base_url or get_server_url()).rstrip("/")
    if base.startswith("https://"):
        ws_base = "wss://" + base[8:]
    elif base.startswith("http://"):
        ws_base = "ws://" + base[7:]
    else:
        ws_base = f"ws://{base}"

    if not path.startswith("/"):
        path = f"/{path}"
    return f"{ws_base}{path}"


def check_server_health(
    url: Optional[str] = None,
    timeout: float = 2.0
) -> Dict[str, Any]:
    """
    Check if the HELIOS Server is reachable.
    Returns:
        {
            "online": bool,
            "url": str,
            "latency_ms": float,
            "status_code": int,
            "info": dict,
            "error": str | None
        }
    """
    target = (url or get_server_url()).rstrip("/")
    health_endpoint = f"{target}/health"
    t0 = time.monotonic()
    
    try:
        req = urllib.request.Request(
            health_endpoint,
            headers={"User-Agent": "HELIOS-Client/2.1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            latency = round((time.monotonic() - t0) * 1000, 1)
            raw = response.read().decode("utf-8")
            try:
                info = json.loads(raw)
            except Exception:
                info = {"raw": raw}
            return {
                "online": True,
                "url": target,
                "latency_ms": latency,
                "status_code": response.status,
                "info": info,
                "error": None,
            }
    except urllib.error.HTTPError as e:
        latency = round((time.monotonic() - t0) * 1000, 1)
        return {
            "online": False,
            "url": target,
            "latency_ms": latency,
            "status_code": e.code,
            "info": {},
            "error": f"HTTP Error {e.code}: {e.reason}",
        }
    except Exception as e:
        latency = round((time.monotonic() - t0) * 1000, 1)
        return {
            "online": False,
            "url": target,
            "latency_ms": latency,
            "status_code": 0,
            "info": {},
            "error": str(e),
        }


def wake_server_wol(
    mac_address: str = "30:56:0F:A8:76:05",
    broadcast_ip: str = "192.168.100.255",
    port: int = 9,
    repeat: int = 3,
) -> bool:
    """Send native UDP Wake-on-LAN packet to wake sleeping AI PC."""
    try:
        clean_mac = mac_address.replace(":", "").replace("-", "").replace(".", "").strip()
        if len(clean_mac) != 12:
            return False
        mac_bytes = bytes.fromhex(clean_mac)
        packet = b"\xff" * 6 + mac_bytes * 16
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            for _ in range(repeat):
                sock.sendto(packet, (broadcast_ip, port))
                time.sleep(0.01)
        return True
    except Exception as e:
        logger.error(f"Failed to send WoL packet: {e}")
        return False
