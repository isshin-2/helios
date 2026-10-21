"""
HELIOS Client — API Client Library
High-level REST and WebSocket client communicating with HELIOS Core server.
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.request
import urllib.error
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import httpx
import websockets

try:
    from .config import check_server_health, get_server_url, get_ws_url
except ImportError:
    from config import check_server_health, get_server_url, get_ws_url

logger = logging.getLogger("helios.client.api")


class HeliosAPIClient:
    """Async & sync HTTP/WebSocket client for HELIOS Core."""

    def __init__(self, server_url: Optional[str] = None, timeout: float = 15.0):
        self.server_url = (server_url or get_server_url()).rstrip("/")
        self.timeout = timeout
        self.default_user_id = 1
        self._cached_session_id: Optional[str] = None

    # ── Status & Cluster Endpoints ──────────────────────────────────────────

    def check_health(self) -> Dict[str, Any]:
        """Synchronously check server reachability and latency."""
        return check_server_health(self.server_url, timeout=min(3.0, self.timeout))

    async def get_health_async(self) -> Dict[str, Any]:
        """Asynchronously query /health endpoint."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(f"{self.server_url}/health")
                return {
                    "online": resp.status_code == 200,
                    "status_code": resp.status_code,
                    "data": resp.json() if resp.status_code == 200 else {},
                }
            except Exception as e:
                return {"online": False, "error": str(e)}

    async def get_cluster_status(self) -> Dict[str, Any]:
        """Query /api/cluster/status for GPU, VRAM, and AI PC state."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(f"{self.server_url}/api/cluster/status")
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                logger.debug(f"Failed to query cluster status: {e}")
        return {"reachable": False}

    async def wake_cluster(self, wait: bool = False) -> Dict[str, Any]:
        """Call server cluster wake API."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(
                    f"{self.server_url}/api/cluster/wake",
                    params={"wait": wait}
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False}

    # ── Sessions & Chat ─────────────────────────────────────────────────────

    async def get_or_create_session(self, user_id: Optional[int] = None) -> str:
        """Get or initialize a chat session ID on the server."""
        if self._cached_session_id:
            return self._cached_session_id

        uid = user_id or self.default_user_id
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Check existing sessions
            try:
                resp = await client.get(f"{self.server_url}/api/users/{uid}/sessions")
                if resp.status_code == 200:
                    sessions = resp.json()
                    if sessions and isinstance(sessions, list) and len(sessions) > 0:
                        sid = sessions[0]["id"]
                        self._cached_session_id = sid
                        return sid
            except Exception:
                pass

            # Create a new session
            try:
                resp = await client.post(f"{self.server_url}/api/users/{uid}/sessions")
                if resp.status_code == 200:
                    data = resp.json()
                    sid = data["id"]
                    self._cached_session_id = sid
                    return sid
            except Exception as e:
                logger.error(f"Failed to create session on {self.server_url}: {e}")
                fallback = "client-session-1"
                self._cached_session_id = fallback
                return fallback

        return "client-session-1"

    async def send_headless_chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Send chat request via REST /api/chat/headless."""
        uid = user_id or self.default_user_id
        sid = session_id or await self.get_or_create_session(uid)

        payload = {
            "user_id": uid,
            "session_id": sid,
            "message": message,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self.server_url}/api/chat/headless", json=payload)
            if resp.status_code == 200:
                return resp.json()
            else:
                return {
                    "response": f"Server returned error {resp.status_code}: {resp.text}",
                    "tools_used": [],
                    "error": True
                }

    # ── WebSocket Hikari Terminal Streaming ─────────────────────────────────

    async def connect_hikari_stream(self) -> websockets.WebSocketClientProtocol:
        """Connect to /ws/hikari WebSocket for interactive terminal streaming."""
        ws_url = get_ws_url("/ws/hikari", base_url=self.server_url)
        return await websockets.connect(ws_url)

    async def connect_chat_stream(self) -> websockets.WebSocketClientProtocol:
        """Connect to /ws WebSocket for main system events."""
        ws_url = get_ws_url("/ws", base_url=self.server_url)
        return await websockets.connect(ws_url)
