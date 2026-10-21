"""
HELIOS Addon Registry & Dynamic Proxy Helper.
Discovers and manages connectivity to optional out-of-process addons:
  - Hikari (:8001): Autonomous Coding Swarm Engine
  - Solstice (:8080): Airi & Ren VRM / Character Studio Engine
  - Astraea (:8085): Tactical Autonomous Gaming Engine
HELIOS Core operates 100% autonomously without requiring any addon to be active.
"""

import os
import logging
import asyncio
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger("helios.addon_registry")

DEFAULT_ADDONS = {
    "hikari": {
        "name": "Hikari Coding Swarm",
        "port": int(os.getenv("HIKARI_PORT", "8001")),
        "health_path": "/health",
        "ws_path": "/ws/hikari",
    },
    "solstice": {
        "name": "Solstice Character Engine",
        "port": int(os.getenv("SOLSTICE_PORT", "8080")),
        "health_path": "/api/status",
        "ws_path": "/ws",
    },
    "astraea": {
        "name": "Astraea Gaming Operative",
        "port": int(os.getenv("ASTRAEA_PORT", "8085")),
        "health_path": "/health",
        "ws_path": "/stream",
    },
}


class AddonRegistry:
    """Manages zero-dependency discovery and health checking of external HELIOS addons."""

    def __init__(self, host: str = "127.0.0.1"):
        self.host = host
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._last_check: Dict[str, float] = {}

    def get_addon_info(self, name: str) -> Optional[Dict[str, Any]]:
        return DEFAULT_ADDONS.get(name.lower())

    async def is_addon_online(self, name: str, timeout: float = 0.5) -> bool:
        """Non-blocking async probe to check if an addon service is responding on localhost."""
        info = self.get_addon_info(name)
        if not info:
            return False

        port = info["port"]
        health_url = f"http://{self.host}:{port}{info['health_path']}"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(health_url)
                return resp.status_code == 200
        except Exception:
            return False

    async def get_all_addon_statuses(self, timeout: float = 0.5) -> Dict[str, Dict[str, Any]]:
        """Queries health status for all known addons concurrently."""
        tasks = []
        addon_names = list(DEFAULT_ADDONS.keys())

        for name in addon_names:
            tasks.append(self.is_addon_online(name, timeout=timeout))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        statuses = {}
        for name, is_online in zip(addon_names, results):
            info = DEFAULT_ADDONS[name]
            statuses[name] = {
                "name": info["name"],
                "port": info["port"],
                "online": bool(is_online) if not isinstance(is_online, Exception) else False,
            }
        return statuses


addon_registry = AddonRegistry()
