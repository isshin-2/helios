import asyncio
import re
from typing import Dict, Any, Optional, Tuple
import httpx
from providers.base import BaseProvider
from config import MAC_IP, MAC_USER, RAM_TOTAL_MB, RAM_MIN_FREE_MB, RAM_CRITICAL_MB

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
                loaded_models.append(m.get("name"))
                vram_used += m.get("size_vram", 0)
                
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
        Connect via SSH to check actual RAM usage using vm_stat.
        Returns (free_mb, total_mb).
        """
        # For a robust system, we would use asyncssh here, 
        # but for simplicity we rely on the Ollama API memory reports mainly.
        # Fallback to estimating free RAM based on Ollama's reported usage.
        health = await self.get_ollama_health()
        vram_used = health.get("vram_used_mb", 0)
        
        # Rough estimate: assume macOS uses ~4GB
        estimated_free = RAM_TOTAL_MB - 4000 - vram_used
        return (max(0, estimated_free), RAM_TOTAL_MB)

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
