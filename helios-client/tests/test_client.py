"""
HELIOS Client Automated Test Suite
Validates client configuration, sidecar safety policies, local action handlers,
registration handshake, and API client routines.
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure helios-client directory is in sys.path
CLIENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CLIENT_DIR))

from config import (
    DEFAULT_SERVER_URL,
    SERVER_PRESETS,
    get_server_url,
    get_ws_url,
    load_client_config,
    save_client_config,
)
from sidecar import ClientSidecarDaemon, is_safe_command
from api_client import HeliosAPIClient


def test_client_config_defaults_and_presets():
    """Verify default server endpoint and preset definitions."""
    url = get_server_url()
    assert url.startswith("http://") or url.startswith("https://")

    presets = {p["id"]: p for p in SERVER_PRESETS}
    assert "ai_pc" in presets
    assert "localhost" in presets
    assert presets["ai_pc"]["url"] == "http://192.168.100.254:8000"
    assert presets["localhost"]["url"] == "http://127.0.0.1:8000"


def test_ws_url_derivation():
    """Verify HTTP/HTTPS to WS/WSS conversion."""
    ws = get_ws_url("/ws", base_url="http://192.168.100.254:8000")
    assert ws == "ws://192.168.100.254:8000/ws"

    wss = get_ws_url("/ws/hikari", base_url="https://cloud.helios.ai")
    assert wss == "wss://cloud.helios.ai/ws/hikari"


def test_sidecar_safety_policy():
    """Verify destructive commands are intercepted and blocked."""
    # Dangerous commands
    blocked_commands = [
        "format c:",
        "diskpart",
        "shutdown -s -t 0",
        "poweroff",
        "rm -rf /",
        "rmdir /s /q c:\\",
        "mkfs.ext4 /dev/sda",
    ]
    for cmd in blocked_commands:
        safe, reason = is_safe_command(cmd)
        assert safe is False, f"Expected '{cmd}' to be blocked, but it passed."

    # Safe commands
    safe_commands = [
        "pytest --version",
        "git status",
        "python -V",
        "echo HELIOS Client Online",
        "npm test",
        "cargo test",
    ]
    for cmd in safe_commands:
        safe, _ = is_safe_command(cmd)
        assert safe is True, f"Expected '{cmd}' to be safe, but got blocked."


def test_sidecar_registration_metadata():
    """Verify client handshake includes required hardware & capability fields."""
    daemon = ClientSidecarDaemon(server_url="http://192.168.100.254:8000")
    reg = daemon.get_registration_payload()

    assert reg["type"] == "register"
    meta = reg["metadata"]
    assert "hostname" in meta
    assert "os" in meta
    assert "screen_width" in meta
    assert "screen_height" in meta
    assert "cwd" in meta
    assert "capabilities" in meta
    assert "run_command" in meta["capabilities"]
    assert "computer_action" in meta["capabilities"]
    assert "capture_screen" in meta["capabilities"]


@pytest.mark.asyncio
async def test_sidecar_command_execution():
    """Verify local command execution in client environment."""
    daemon = ClientSidecarDaemon()
    res = await daemon.handle_run_command({
        "command": "python -c \"print('HELIOS_CLIENT_VERIFIED')\"",
        "timeout": 10.0
    })
    assert res["success"] is True
    assert "HELIOS_CLIENT_VERIFIED" in res["output"]


@pytest.mark.asyncio
async def test_sidecar_file_operations():
    """Verify file read, write, exists, and list operations."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        daemon = ClientSidecarDaemon(workspace_dir=tmp_dir)

        # 1. Write file
        w_res = await daemon.handle_file_op({
            "op": "write",
            "path": "test_note.txt",
            "content": "Helios Client Sidecar Test Payload"
        })
        assert w_res["success"] is True

        # 2. Check exists
        e_res = await daemon.handle_file_op({
            "op": "exists",
            "path": "test_note.txt"
        })
        assert e_res["success"] is True
        assert e_res["exists"] is True

        # 3. Read file
        r_res = await daemon.handle_file_op({
            "op": "read",
            "path": "test_note.txt"
        })
        assert r_res["success"] is True
        assert "Helios Client Sidecar Test Payload" in r_res["content"]

        # 4. List directory
        l_res = await daemon.handle_file_op({
            "op": "list",
            "path": "."
        })
        assert l_res["success"] is True
        assert "test_note.txt" in l_res["items"]


@pytest.mark.asyncio
async def test_sidecar_ping():
    """Verify ping-pong heartbeat response."""
    daemon = ClientSidecarDaemon()
    res = await daemon.dispatch_request("ping", {})
    assert res["success"] is True
    assert res["pong"] is True
    assert "time" in res


def test_api_client_initialization():
    """Verify API client resolves URLs and default session IDs."""
    api = HeliosAPIClient(server_url="http://192.168.100.254:8000")
    assert api.server_url == "http://192.168.100.254:8000"
    health = api.check_health()
    assert "online" in health
    assert "latency_ms" in health
