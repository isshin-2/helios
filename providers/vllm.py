import httpx
import json
import logging
from typing import Dict, Any, List, Optional, AsyncGenerator, Union
from config import VLLM_API_BASE, VLLM_API_KEY
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

class VLLMProvider(BaseProvider):
    def __init__(self, host: str = VLLM_API_BASE, api_key: str = VLLM_API_KEY):
        self.host = host
        self.api_key = api_key
        # Single persistent client with connection pooling
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=None, write=None, pool=None),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            headers={"Authorization": f"Bearer {self.api_key}"}
        )

    async def close(self):
        """Graceful shutdown — call on app teardown."""
        await self._client.aclose()

    async def chat(self, model: str, messages: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None, stream: bool = False, keep_alive: str = "5m", **kwargs) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        # Map Ollama-style options to OpenAI spec if present
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream
        }
        
        if options:
            if "temperature" in options: payload["temperature"] = options["temperature"]
            if "top_p" in options: payload["top_p"] = options["top_p"]
            if "num_predict" in options: payload["max_tokens"] = options["num_predict"]
            
        if "tools" in kwargs and kwargs["tools"]:
            # Basic mapping from Ollama tools to OpenAI tools (usually identical JSON schema)
            payload["tools"] = kwargs["tools"]
        
        if stream:
            async def stream_generator():
                logger.debug(f"OpenAI Payload: {json.dumps(payload)}")
                async with self._client.stream("POST", f"{self.host}/chat/completions", json=payload) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        logger.error(f"OpenAI Error Body: {body}")
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line or line == "data: [DONE]":
                            continue
                        if line.startswith("data: "):
                            try:
                                chunk = json.loads(line[6:])
                                # Map back to Ollama format for internal router compatibility
                                delta = chunk["choices"][0].get("delta", {})
                                yield {
                                    "model": model,
                                    "message": delta,
                                    "done": chunk["choices"][0].get("finish_reason") is not None
                                }
                            except json.JSONDecodeError:
                                logger.warning(f"Could not parse chunk: {line}")
            return stream_generator()
        else:
            response = await self._client.post(f"{self.host}/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            return {
                "model": model,
                "message": data["choices"][0]["message"],
                "done": True
            }

    async def generate(self, model: str, prompt: str, options: Optional[Dict[str, Any]] = None, stream: bool = False, keep_alive: str = "5m", **kwargs) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream
        }
        if options:
            if "temperature" in options: payload["temperature"] = options["temperature"]
            if "num_predict" in options: payload["max_tokens"] = options["num_predict"]
            
        if stream:
            async def stream_generator():
                async with self._client.stream("POST", f"{self.host}/completions", json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line or line == "data: [DONE]":
                            continue
                        if line.startswith("data: "):
                            chunk = json.loads(line[6:])
                            yield {
                                "model": model,
                                "response": chunk["choices"][0].get("text", ""),
                                "done": chunk["choices"][0].get("finish_reason") is not None
                            }
            return stream_generator()
        else:
            response = await self._client.post(f"{self.host}/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            return {
                "model": model,
                "response": data["choices"][0].get("text", ""),
                "done": True
            }

    async def get_embeddings(self, model: str, prompt: str) -> List[float]:
        payload = {
            "model": model,
            "input": prompt
        }
        response = await self._client.post(f"{self.host}/embeddings", json=payload)
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]

    async def list_models(self) -> Dict[str, Any]:
        response = await self._client.get(f"{self.host}/models")
        response.raise_for_status()
        data = response.json()
        return {"models": [{"name": m["id"]} for m in data.get("data", [])]}

    async def list_running(self) -> Dict[str, Any]:
        return await self.list_models()

    async def unload_model(self, model: str) -> Dict[str, Any]:
        return {}
