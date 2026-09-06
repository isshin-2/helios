import json
import httpx
from typing import Dict, Any, List, Optional, AsyncGenerator, Union
from .base import BaseProvider
import config

class OpenRouterProvider(BaseProvider):
    """
    Provider for OpenRouter API via HTTPX.
    """
    def __init__(self):
        self.api_key = config.OPENROUTER_API_KEY
        self.base_url = "https://openrouter.ai/api/v1"

    async def chat(self, model: str, messages: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None, stream: bool = False, **kwargs) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        payload = {
            "model": model,
            "messages": messages
        }
        
        if options and "temperature" in options:
            payload["temperature"] = options["temperature"]
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "Helios AI Router"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers, timeout=60.0)
            response.raise_for_status()
            data = response.json()
            
            try:
                text = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError):
                text = ""
                
            return {
                "message": {
                    "role": "assistant",
                    "content": text
                }
            }

    async def generate(self, model: str, prompt: str, options: Optional[Dict[str, Any]] = None, stream: bool = False, **kwargs) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        return await self.chat(model, [{"role": "user", "content": prompt}], options, stream, **kwargs)

    async def get_embeddings(self, model: str, prompt: str) -> List[float]:
        # OpenRouter supports some embedding models depending on the route
        return []

    async def list_models(self) -> Dict[str, Any]:
        return {"models": []}

    async def list_running(self) -> Dict[str, Any]:
        return {}

    async def unload_model(self, model: str) -> Dict[str, Any]:
        return {"status": "ok"}
