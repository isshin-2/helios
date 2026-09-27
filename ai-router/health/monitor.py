import asyncio
import re
from typing import Dict, Any, Optional, Tuple
import httpx
import psutil
from providers.base import BaseProvider
from config import RAM_TOTAL_MB, RAM_MIN_FREE_MB, RAM_CRITICAL_MB

class SystemMonitor:
    def __init__(self, provider: BaseProvider):
        self.provider = provider

    async def get_ollama_health(self) -> Dict[str, Any]:
        """Check if Ollama is responsive and what's loaded."""
        try:
            running = await self.provider.list_running()
            models = running.get("models", [])
            
            loaded_models = []
            vram_used = 0
            for m in models:
                # Handle malformed or missing fields safely
                name = m.get("name", "unknown")
                size_vram = m.get("size_vram", 0)
                size = m.get("size", 0)
                
                loaded_models.append({
                    "name": name,
                    "size_vram": size_vram if isinstance(size_vram, (int, float)) else 0,
                    "size": size if isinstance(size, (int, float)) else 0
                })
                vram_used += size_vram if isinstance(size_vram, (int, float)) else 0
                
            return {
                "status": "online",
                "loaded_models": loaded_models,
                "vram_used_mb": round(vram_used / (1024 * 1024), 2)
            }
        except httpx.RequestError:
            return {
                "status": "offline",
                "loaded_models": [],
                "vram_used_mb": 0
            }

    async def get_system_ram(self) -> Tuple[float, float]:
        """
        Use psutil to get actual system RAM.
        Returns (free_mb, total_mb).
        """
        mem = psutil.virtual_memory()
        free_mb = mem.available / (1024 * 1024)
        total_mb = mem.total / (1024 * 1024)
        return (free_mb, total_mb)

    async def get_full_status(self) -> Dict[str, Any]:
        """Compile a full health report."""
        ollama_health = await self.get_ollama_health()
        free_ram, total_ram = await self.get_system_ram()
        
        status = "ready"
        if ollama_health["status"] == "offline":
            status = "error_ollama_offline"
        elif free_ram < RAM_CRITICAL_MB:
            status = "warning_critical_ram"
        elif free_ram < RAM_MIN_FREE_MB:
            status = "warning_low_ram"
            
        return {
            "ollama": ollama_health["status"],
            "available_ram_mb": round(free_ram, 2),
            "total_ram_mb": total_ram,
            "loaded_models": ollama_health["loaded_models"],
            "vram_used_mb": ollama_health["vram_used_mb"],
            "status": status
        }
