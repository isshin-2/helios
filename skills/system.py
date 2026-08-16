import re
from typing import Tuple
from .base import BaseSkill
from providers.base import BaseProvider
from health.monitor import SystemMonitor

class SystemSkill(BaseSkill):
    def __init__(self, provider: BaseProvider, monitor: SystemMonitor):
        self.provider = provider
        self.monitor = monitor
        
    def match(self, prompt: str) -> bool:
        prompt = prompt.lower().strip()
        patterns = [
            r"^check ollama status", r"^ollama status",
            r"^list models", r"^show models",
            r"^check ram", r"^check memory",
            r"^unload model"
        ]
        return any(re.search(p, prompt) for p in patterns)
        
    async def execute(self, prompt: str, **kwargs) -> Tuple[str, str]:
        prompt = prompt.lower().strip()
        
        if re.search(r"^check ollama status", prompt) or re.search(r"^ollama status", prompt):
            health = await self.monitor.get_full_status()
            return (f"Ollama Status:\n{health}", "system_status")
            
        if re.search(r"^list models", prompt) or re.search(r"^show models", prompt):
            try:
                models_data = await self.provider.list_models()
                models = [m.get("name") for m in models_data.get("models", [])]
                return (f"Installed models: {', '.join(models)}", "list_models")
            except Exception as e:
                return (f"Error connecting to Ollama: {e}", "list_models")
                
        if re.search(r"^check ram", prompt) or re.search(r"^check memory", prompt):
            free, total = await self.monitor.get_system_ram()
            return (f"RAM: {free:.2f} MB free out of {total} MB", "check_ram")
            
        if re.search(r"^unload model", prompt):
            words = prompt.split()
            if len(words) > 2:
                model = words[2]
                await self.provider.unload_model(model)
                return (f"Sent unload request for {model}.", "unload_model")
            else:
                return ("Please specify a model to unload.", "unload_model")
                
        return ("Unknown system command.", "system_error")
