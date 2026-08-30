import httpx
import json
import logging
import time
import os
from typing import Dict, Any, List, Optional, AsyncGenerator, Union
from config import OLLAMA_HOST, BUDGET_MAX_CONTEXT, is_budget_mode_active
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

class OllamaProvider(BaseProvider):
    def __init__(self, host: str = OLLAMA_HOST):
        self.host = host
        self.base_url = f"{host}/api"
        # Single persistent client with connection pooling — reused across ALL calls.
        # This eliminates TCP connection setup/teardown on every API call.
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=None, write=None, pool=None),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    async def close(self):
        """Graceful shutdown — call on app teardown."""
        await self._client.aclose()

    async def _post(self, endpoint: str, json_data: Dict[str, Any]) -> Dict[str, Any]:
        response = await self._client.post(f"{self.base_url}/{endpoint}", json=json_data)
        response.raise_for_status()
        if response.text.strip():
            return response.json()
        return {}

    async def _get(self, endpoint: str) -> Dict[str, Any]:
        response = await self._client.get(f"{self.base_url}/{endpoint}")
        response.raise_for_status()
        if response.text.strip():
            return response.json()
        return {}

    async def chat(self, model: str, messages: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None, stream: bool = False, keep_alive: str = "5m", **kwargs) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        # ─── BUDGET MODE: Strict Payload Override ─────────────────────
        if is_budget_mode_active():
            keep_alive = 0  # Force immediate unload after generation
            options = options or {}
            options["num_ctx"] = min(options.get("num_ctx", BUDGET_MAX_CONTEXT), BUDGET_MAX_CONTEXT)
            options["num_thread"] = max(1, (os.cpu_count() or 4) - 1)  # Reserve 1 core for Windows OS
            options["num_gpu"] = min(options.get("num_gpu", 99), 10)   # Hard throttle GPU layers
            logger.info(f"[BUDGET] Enforcing: num_ctx={options['num_ctx']}, num_thread={options['num_thread']}, num_gpu={options['num_gpu']}, keep_alive=0")
        # ──────────────────────────────────────────────────────────────

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
            logger.debug(f"Ollama Payload: {json.dumps(payload)}")
            
            # Use build_request and send so we can catch 400 Bad Request immediately
            request = self._client.build_request("POST", f"{self.base_url}/chat", json=payload)
            response = await self._client.send(request, stream=True)
            
            if response.status_code != 200:
                body = await response.aread()
                body_str = body.decode(errors='ignore')
                await response.aclose()
                
                # Auto-recover if model doesn't support tools
                if response.status_code == 400 and "does not support tools" in body_str:
                    logger.warning(f"Model {model} does not support tools. Retrying without tools.")
                    if "tools" in payload:
                        del payload["tools"]
                    request = self._client.build_request("POST", f"{self.base_url}/chat", json=payload)
                    response = await self._client.send(request, stream=True)
                    if response.status_code != 200:
                        body = await response.aread()
                        logger.error(f"Ollama Error Body after retry: {body}")
                        await response.aclose()
                        response.raise_for_status()
                else:
                    logger.error(f"Ollama Error Body: {body_str}")
                    response.raise_for_status()
            async def stream_generator(res):
                start_time = time.time()
                ttft_logged = False
                try:
                    async for line in res.aiter_lines():
                        if line:
                            if not ttft_logged:
                                ttft_ms = (time.time() - start_time) * 1000
                                logger.info(f"[TELEMETRY] TTFT: {ttft_ms:.2f} ms | Model: {model}")
                                ttft_logged = True
                            yield json.loads(line)
                finally:
                    await res.aclose()
                            
            return stream_generator(response)
        else:
            return await self._post("chat", payload)

    async def generate(self, model: str, prompt: str, options: Optional[Dict[str, Any]] = None, stream: bool = False, keep_alive: str = "5m", **kwargs) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        # ─── BUDGET MODE: Strict Payload Override ─────────────────────
        if is_budget_mode_active():
            keep_alive = "2m"
            options = options or {}
            options["num_ctx"] = min(options.get("num_ctx", BUDGET_MAX_CONTEXT), BUDGET_MAX_CONTEXT)
            options["num_thread"] = max(1, (os.cpu_count() or 4) - 1)
            options["num_gpu"] = min(options.get("num_gpu", 99), 10)
        # ──────────────────────────────────────────────────────────────

        payload = {
            "model": model,
            "prompt": prompt,
            "keep_alive": keep_alive,
            "stream": stream
        }
        if options:
            payload["options"] = options
            
        if stream:
            request = self._client.build_request("POST", f"{self.base_url}/generate", json=payload)
            response = await self._client.send(request, stream=True)
            
            if response.status_code != 200:
                body = await response.aread()
                logger.error(f"Ollama Error Body: {body}")
                await response.aclose()
                response.raise_for_status()
                
            async def stream_generator(res):
                start_time = time.time()
                ttft_logged = False
                try:
                    async for line in res.aiter_lines():
                        if line:
                            if not ttft_logged:
                                ttft_ms = (time.time() - start_time) * 1000
                                logger.info(f"[TELEMETRY] TTFT: {ttft_ms:.2f} ms | Model: {model}")
                                ttft_logged = True
                            yield json.loads(line)
                finally:
                    await res.aclose()
            return stream_generator(response)
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
