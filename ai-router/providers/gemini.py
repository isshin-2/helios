import json
import httpx
from typing import Dict, Any, List, Optional, AsyncGenerator, Union
from .base import BaseProvider
import config

class GeminiProvider(BaseProvider):
    """
    Provider for Google's Gemini API via HTTPX.
    """
    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    async def chat(self, model: str, messages: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None, stream: bool = False, **kwargs) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            if role == "assistant":
                role = "model"
            elif role == "system":
                # System prompt mapped to user for basic compatibility
                role = "user"
            
            contents.append({
                "role": role,
                "parts": [{"text": msg.get("content", "")}]
            })
            
        payload = {"contents": contents}
        if options and "temperature" in options:
            payload["generationConfig"] = {"temperature": options["temperature"]}
            
        url = f"{self.base_url}/{model}:generateContent?key={self.api_key}"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=60.0)
            response.raise_for_status()
            data = response.json()
            
            try:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
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
        url = f"{self.base_url}/{model}:embedContent?key={self.api_key}"
        payload = {
            "model": f"models/{model}",
            "content": {"parts": [{"text": prompt}]}
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            data = response.json()
            return data.get("embedding", {}).get("values", [])

    async def list_models(self) -> Dict[str, Any]:
        return {"models": [{"name": "gemini-1.5-pro"}, {"name": "gemini-1.5-flash"}]}

    async def list_running(self) -> Dict[str, Any]:
        return {}

    async def unload_model(self, model: str) -> Dict[str, Any]:
        return {"status": "ok", "message": "Cloud models do not require unloading."}
