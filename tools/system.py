import asyncio
from pydantic import BaseModel, Field
from typing import Tuple, Optional
from tools.base import BaseTool
from providers.base import BaseProvider
from health.monitor import SystemMonitor

class SystemInput(BaseModel):
    action: str = Field(description="The system action to perform. Options: 'status', 'list_models', 'deep_sleep'")
    model_name: Optional[str] = Field(None, description="Optional model name if the action requires it")

class SystemTool(BaseTool):
    name: str = "system_management"
    description: str = "Manage the local AI system state, check health, list models, or put the system into deep sleep to free VRAM."
    input_schema: type[BaseModel] = SystemInput

    def __init__(self, provider: BaseProvider, monitor: SystemMonitor):
        self.provider = provider
        self.monitor = monitor

    async def execute(self, user_id: int, action: str, model_name: Optional[str] = None) -> Tuple[str, str]:
        if action == "status":
            status = await self.monitor.get_full_status()
            return (f"System Status:\n{status}", self.name)
        
        elif action == "list_models":
            try:
                models = await self.provider.list_models()
                return (f"Available Models:\n{models}", self.name)
            except Exception as e:
                return (f"Failed to list models: {e}", self.name)
                
        elif action == "deep_sleep":
            try:
                # We need to access ModelManager. But SystemTool only gets Provider and Monitor.
                # Since ModelManager has evict_from_vram, let's just unload all loaded models directly via provider and monitor.
                status = await self.monitor.get_full_status()
                loaded = status.get("loaded_models", [])
                evicted = []
                for m in loaded:
                    name = m if isinstance(m, str) else m.get("name")
                    if name:
                        await self.provider.unload_model(name)
                        evicted.append(name)
                return (f"Deep Sleep engaged. Evicted models: {', '.join(evicted) if evicted else 'None'}", self.name)
            except Exception as e:
                return (f"Failed to engage deep sleep: {e}", self.name)
        
        return (f"Unknown action: {action}", self.name)
