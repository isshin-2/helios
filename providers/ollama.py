import httpx
import json
from typing import Dict, Any, List, Optional, AsyncGenerator, Union
from config import OLLAMA_HOST
from providers.base import BaseProvider

class OllamaProvider(BaseProvider):
    def __init__(self, host: str = OLLAMA_HOST):
        self.host = host
        self.base_url = f"{host}/api"

    async def _post(self, endpoint: str, json_data: Dict[str, Any]) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/{endpoint}", json=json_data, timeout=None)
            response.raise_for_status()
            if response.text.strip():
                return response.json()
            return {}

    async def _get(self, endpoint: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/{endpoint}", timeout=None)
            response.raise_for_status()
            if response.text.strip():
                return response.json()
            return {}

    async def chat(self, model: str, messages: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None, stream: bool = False, keep_alive: str = "5m", **kwargs) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        payload = {
            "model": model,
            "messages": messages,
            "keep_alive": keep_alive,
            "stream": stream
        }
        if options:
            payload["options"] = options
            
        if "tools" in kwargs and kwargs["tools"]:
            payload["tools"] = kwargs["tools"]
        
        if stream:
            async def stream_generator():
                import logging
                logging.getLogger("ollama_debug").info(f"Ollama Payload: {json.dumps(payload)}")
                async with httpx.AsyncClient() as client:
                    async with client.stream("POST", f"{self.base_url}/chat", json=payload, timeout=None) as response:
                        if response.status_code != 200:
                            body = await response.aread()
                            logging.getLogger("ollama_debug").error(f"Ollama Error Body: {body}")
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if line:
                                yield json.loads(line)
            return stream_generator()
        else:
            return await self._post("chat", payload)

    async def generate(self, model: str, prompt: str, options: Optional[Dict[str, Any]] = None, stream: bool = False, keep_alive: str = "5m", **kwargs) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        payload = {
            "model": model,
            "prompt": prompt,
            "keep_alive": keep_alive,
            "stream": stream
        }
        if options:
            payload["options"] = options
            
        if stream:
            async def stream_generator():
                async with httpx.AsyncClient() as client:
                    async with client.stream("POST", f"{self.base_url}/generate", json=payload, timeout=None) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if line:
                                yield json.loads(line)
            return stream_generator()
        else:
            return await self._post("generate", payload)

    async def get_embeddings(self, model: str, prompt: str) -> List[float]:
        payload = {
            "model": model,
            "prompt": prompt
        }
        res = await self._post("embeddings", payload)
        return res.get("embedding", [])

    async def list_models(self) -> Dict[str, Any]:
        return await self._get("tags")

    async def list_running(self) -> Dict[str, Any]:
        return await self._get("ps")

    async def unload_model(self, model: str) -> Dict[str, Any]:
        return await self._post("generate", {"model": model, "keep_alive": 0})
