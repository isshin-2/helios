"""
HELIOS Client — Device Sidecar Daemon
Connects to remote HELIOS server to execute local commands, desktop automation,
screen capture, and file operations directly on the user's client machine.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import platform
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import websockets

try:
    from .config import get_server_url, get_ws_url, load_client_config
except ImportError:
    from config import get_server_url, get_ws_url, load_client_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("HELIOS.ClientSidecar")

# Safety policy: block catastrophic commands
DANGEROUS_COMMANDS = [
    "format", "diskpart", "shutdown", "poweroff", "init 0", "init 6",
    "mkfs", ":(){ :|:& };:", "dd if="
]


def is_safe_command(command: str) -> Tuple[bool, str]:
    """Validate command against destructive pattern blacklist."""
    cmd_lower = command.lower().strip()
    if not cmd_lower:
        return False, "Empty command"
    
    parts = cmd_lower.split()
    for dangerous in DANGEROUS_COMMANDS:
        if dangerous in cmd_lower:
            return False, f"Command contains blacklisted phrase: '{dangerous}'"

    # Block recursive root deletions
    if ("rm -rf /" in cmd_lower) or ("rmdir /s /q c:\\" in cmd_lower) or ("del /f /s /q c:\\" in cmd_lower):
        return False, "Command targets filesystem root"

    return True, ""


class ClientSidecarDaemon:
    """Persistent agent that links the client device to the remote HELIOS server."""

    def __init__(
        self,
        server_url: Optional[str] = None,
        workspace_dir: Optional[str] = None,
        auto_reconnect: bool = True
    ):
        self.server_url = (server_url or get_server_url()).rstrip("/")
        self.workspace_dir = os.path.abspath(workspace_dir or os.getcwd())
        self.auto_reconnect = auto_reconnect
        self.is_running = False
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._screen_size: Tuple[int, int] = (1920, 1080)

        # Detect native display size
        try:
            import pyautogui
            sz = pyautogui.size()
            self._screen_size = (sz.width, sz.height)
            pyautogui.FAILSAFE = True
        except Exception:
            pass

    def get_registration_payload(self) -> Dict[str, Any]:
        """Handshake metadata sent to HELIOS server upon connection."""
        return {
            "type": "register",
            "metadata": {
                "hostname": socket.gethostname(),
                "os": f"{platform.system()} {platform.release()} ({platform.architecture()[0]})",
                "screen_width": self._screen_size[0],
                "screen_height": self._screen_size[1],
                "cwd": self.workspace_dir,
                "python_version": platform.python_version(),
                "client_version": "2.1.0",
                "capabilities": [
                    "run_command",
                    "computer_action",
                    "capture_screen",
                    "file_op",
                    "ping"
                ]
            }
        }

    # ── Action Handlers ──────────────────────────────────────────────────────

    async def handle_run_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute local shell command inside client workspace."""
        cmd = payload.get("command", "").strip()
        cwd = payload.get("cwd") or self.workspace_dir
        timeout = float(payload.get("timeout", 60.0))

        safe, reason = is_safe_command(cmd)
        if not safe:
            logger.warning(f"Blocked unsafe command: {cmd} ({reason})")
            return {"success": False, "error": f"Security Policy Blocked: {reason}"}

        logger.info(f"Executing local command: {cmd} [cwd: {cwd}]")
        try:
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            out_str = stdout.decode("utf-8", errors="replace")
            err_str = stderr.decode("utf-8", errors="replace")

            full_output = out_str
            if err_str:
                full_output += f"\n[STDERR]:\n{err_str}" if full_output else err_str

            return {
                "success": process.returncode == 0,
                "exit_code": process.returncode,
                "output": full_output,
            }
        except asyncio.TimeoutError:
            return {"success": False, "error": f"Command timed out after {timeout} seconds."}
        except Exception as e:
            return {"success": False, "error": f"Command execution failed: {e}"}

    async def handle_capture_screen(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Capture screenshot from client display and return compressed base64."""
        max_dim = int(payload.get("max_dimension", 1280))
        quality = int(payload.get("quality", 80))
        img_fmt = payload.get("image_format", "jpeg").lower()

        try:
            raw_img = None
            try:
                import mss
                from PIL import Image
                with mss.mss() as sct:
                    mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                    sct_img = sct.grab(mon)
                    raw_img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            except Exception:
                from PIL import ImageGrab
                raw_img = ImageGrab.grab()

            if raw_img is None:
                return {"success": False, "error": "Screen capture returned empty image."}

            orig_w, orig_h = raw_img.size
            if orig_w > max_dim or orig_h > max_dim:
                from PIL import Image
                raw_img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

            cur_w, cur_h = raw_img.size
            buf = io.BytesIO()
            if img_fmt in ("jpeg", "jpg"):
                raw_img.convert("RGB").save(buf, format="JPEG", quality=quality, optimize=True)
                fmt = "jpeg"
            else:
                raw_img.save(buf, format="PNG", optimize=True)
                fmt = "png"

            b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
            return {
                "success": True,
                "image_base64": b64_str,
                "format": fmt,
                "width": cur_w,
                "height": cur_h,
                "original_width": orig_w,
                "original_height": orig_h,
            }
        except Exception as e:
            logger.error(f"Screen capture failed: {e}")
            return {"success": False, "error": f"Screen capture error: {e}"}

    async def handle_computer_action(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Perform desktop automation on the client machine."""
        try:
            import pyautogui
        except ImportError:
            return {"success": False, "error": "pyautogui is not installed on client."}

        action_type = payload.get("action_type") or payload.get("action")
        x = payload.get("x")
        y = payload.get("y")
        text = payload.get("text", "")
        key = payload.get("key", "")
        keys = payload.get("keys", [])
        button = payload.get("button", "left").lower()

        logger.info(f"Client executing desktop action: {action_type} (x={x}, y={y}, key={key})")

        try:
            if action_type == "move":
                if x is not None and y is not None:
                    pyautogui.moveTo(int(x), int(y))
                    return {"success": True, "result": f"Moved to ({x}, {y})"}

            elif action_type == "click":
                if x is not None and y is not None:
                    pyautogui.click(int(x), int(y), button=button)
                else:
                    pyautogui.click(button=button)
                return {"success": True, "result": f"Clicked at ({x}, {y}) with {button}"}

            elif action_type == "double_click":
                if x is not None and y is not None:
                    pyautogui.doubleClick(int(x), int(y))
                else:
                    pyautogui.doubleClick()
                return {"success": True, "result": f"Double clicked at ({x}, {y})"}

            elif action_type == "right_click":
                if x is not None and y is not None:
                    pyautogui.rightClick(int(x), int(y))
                else:
                    pyautogui.rightClick()
                return {"success": True, "result": f"Right clicked at ({x}, {y})"}

            elif action_type == "type_text" or action_type == "type":
                pyautogui.write(text, interval=0.01)
                return {"success": True, "result": f"Typed text ({len(text)} chars)"}

            elif action_type == "press_key" or action_type == "key":
                target_key = key or (keys[0] if keys else "")
                if target_key:
                    pyautogui.press(target_key)
                    return {"success": True, "result": f"Pressed key '{target_key}'"}

            elif action_type == "hotkey":
                target_keys = keys or ([k.strip() for k in key.split("+")] if key else [])
                if target_keys:
                    pyautogui.hotkey(*target_keys)
                    return {"success": True, "result": f"Pressed hotkey: {'+'.join(target_keys)}"}

            elif action_type == "scroll":
                amount = int(payload.get("amount") or payload.get("clicks") or 3)
                direction = payload.get("direction", "down").lower()
                clicks = -amount if direction == "down" else amount
                pyautogui.scroll(clicks)
                return {"success": True, "result": f"Scrolled {direction} by {amount}"}

            elif action_type == "launch_application":
                app_name = payload.get("app_name", "").strip()
                if app_name:
                    subprocess.Popen(app_name, shell=True)
                    return {"success": True, "result": f"Launched application '{app_name}'"}

            elif action_type == "screenshot":
                return await self.handle_capture_screen(payload)

            return {"success": False, "error": f"Unsupported action_type: '{action_type}'"}

        except Exception as e:
            logger.error(f"Error executing computer action '{action_type}': {e}")
            return {"success": False, "error": str(e)}

    async def handle_file_op(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Perform local file operations on the client workspace."""
        op = payload.get("op", "read").lower()
        file_path = payload.get("path", "")
        if not file_path:
            return {"success": False, "error": "Path is required"}

        # Resolve relative to client workspace
        target = Path(self.workspace_dir) / file_path if not os.path.isabs(file_path) else Path(file_path)

        try:
            if op == "read":
                if not target.exists():
                    return {"success": False, "error": f"File not found: {file_path}"}
                content = target.read_text(encoding="utf-8", errors="replace")
                return {"success": True, "content": content}

            elif op == "write":
                target.parent.mkdir(parents=True, exist_ok=True)
                content = payload.get("content", "")
                target.write_text(content, encoding="utf-8")
                return {"success": True, "bytes_written": len(content)}

            elif op == "list":
                if not target.exists():
                    return {"success": False, "error": f"Directory not found: {file_path}"}
                items = [p.name for p in target.iterdir()]
                return {"success": True, "items": items}

            elif op == "exists":
                return {"success": True, "exists": target.exists()}

            return {"success": False, "error": f"Unknown file operation: {op}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Main WebSocket Loop ──────────────────────────────────────────────────

    async def dispatch_request(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Route request by action name."""
        if action == "run_command":
            return await self.handle_run_command(payload)
        elif action == "capture_screen" or action == "screenshot":
            return await self.handle_capture_screen(payload)
        elif action == "computer_action":
            return await self.handle_computer_action(payload)
        elif action == "file_op":
            return await self.handle_file_op(payload)
        elif action == "ping":
            return {"success": True, "pong": True, "time": time.time()}
        else:
            return {"success": False, "error": f"Unrecognized action '{action}'"}

    async def run(self):
        """Run the persistent sidecar connection loop."""
        self.is_running = True
        ws_url = get_ws_url("/sidecar/ws", base_url=self.server_url)
        logger.info(f"Connecting HELIOS Client Sidecar to {ws_url}...")

        backoff = 2.0
        while self.is_running:
            try:
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
                    self._ws = ws
                    backoff = 2.0
                    logger.info("Successfully connected to HELIOS Server Sidecar bridge.")

                    # Send client device metadata handshake
                    reg = self.get_registration_payload()
                    await ws.send(json.dumps(reg))

                    while self.is_running:
                        raw_msg = await ws.recv()
                        try:
                            msg_data = json.loads(raw_msg)
                        except Exception as parse_err:
                            logger.error(f"Malformed JSON from server: {parse_err}")
                            continue

                        req_id = msg_data.get("request_id")
                        action = msg_data.get("action", "")
                        payload = msg_data.get("payload", {})

                        # Dispatch action
                        result = await self.dispatch_request(action, payload)

                        # Send response back to server
                        response = {
                            "request_id": req_id,
                            **result
                        }
                        await ws.send(json.dumps(response))

            except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError, OSError) as e:
                logger.warning(f"Connection to HELIOS server lost ({e}). Retrying in {backoff:.1f}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 1.5, 30.0)
            except Exception as e:
                logger.error(f"Unexpected sidecar error: {e}. Retrying in {backoff:.1f}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 1.5, 30.0)

    def stop(self):
        """Stop the sidecar daemon loop."""
        self.is_running = False
        if self._ws:
            asyncio.create_task(self._ws.close())


def start_sidecar_standalone(server_url: Optional[str] = None):
    """Entry point to run sidecar as standalone script."""
    daemon = ClientSidecarDaemon(server_url=server_url)
    print("=" * 65)
    print("  HELIOS CLIENT SIDECAR DAEMON")
    print(f"  Target Server: {daemon.server_url}")
    print(f"  Local Workspace: {daemon.workspace_dir}")
    print("  Status: Connecting...")
    print("  Press Ctrl+C to terminate.")
    print("=" * 65)
    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        print("\n[*] Sidecar shut down cleanly.")


if __name__ == "__main__":
    url_arg = sys.argv[1] if len(sys.argv) > 1 else None
    start_sidecar_standalone(url_arg)
