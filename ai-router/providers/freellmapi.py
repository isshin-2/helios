import json
import logging
import httpx
from typing import Dict, Any, List, Optional, AsyncGenerator, Union
from .base import BaseProvider
import config

logger = logging.getLogger(__name__)

class FreeLLMAPIProvider(BaseProvider):
    """
    Provider for FreeLLMAPI (Unified Free-Tier Aggregator) via OpenAI-compatible endpoint.
    Aggregates 34 free providers (Groq, Cerebras, Google Gemini, Mistral, OpenRouter, etc.)
    with automatic failover, rate-limit tracking, and key rotation.
    
    Default endpoint: http://localhost:3001/v1
    """
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = (base_url or getattr(config, "FREELLMAPI_URL", "http://localhost:3001/v1")).rstrip("/")
        self.api_key = api_key or getattr(config, "FREELLMAPI_API_KEY", "freellmapi-default-key")
        self.default_model = getattr(config, "FREELLMAPI_DEFAULT_MODEL", "auto")
        self.is_connected = False

    async def check_health(self) -> bool:
        """Ping FreeLLMAPI models endpoint to check connectivity."""
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/models", headers=headers)
                self.is_connected = (res.status_code == 200)
                return self.is_connected
        except Exception:
            self.is_connected = False
            return False

    async def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False,
        **kwargs
    ) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        # Map or default model
        target_model = model or self.default_model
        if target_model in ("default", "auto", ""):
            target_model = self.default_model

        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "stream": stream,
        }

        if options:
            if "temperature" in options:
                payload["temperature"] = options["temperature"]
            if "max_tokens" in options or "num_predict" in options:
                payload["max_tokens"] = options.get("max_tokens") or options.get("num_predict")
            if "top_p" in options:
                payload["top_p"] = options["top_p"]

        # Support structured tool calls
        if "tools" in kwargs and kwargs["tools"]:
            payload["tools"] = kwargs["tools"]
        if "tool_choice" in kwargs and kwargs["tool_choice"]:
            payload["tool_choice"] = kwargs["tool_choice"]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "HELIOS Autonomous AI",
        }

        if stream:
            return self._stream_chat(payload, headers)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            choice = data.get("choices", [{}])[0]
            msg = choice.get("message", {})
            text = msg.get("content", "") or ""
            tool_calls = msg.get("tool_calls")

            result: Dict[str, Any] = {
                "message": {
                    "role": msg.get("role", "assistant"),
                    "content": text,
                }
            }
            if tool_calls:
                result["message"]["tool_calls"] = tool_calls

            return result

    async def _stream_chat(self, payload: Dict[str, Any], headers: Dict[str, str]) -> AsyncGenerator[Dict[str, Any], None]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        line_data = line[6:].strip()
                        if line_data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(line_data)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            yield {
                                "message": {
                                    "role": "assistant",
                                    "content": content,
                                },
                                "done": False,
                            }
                        except Exception:
                            continue
                yield {"message": {"role": "assistant", "content": ""}, "done": True}

    async def generate(
        self,
        model: str,
        prompt: str,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False,
        **kwargs
    ) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        return await self.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options=options,
            stream=stream,
            **kwargs
        )

    async def get_embeddings(self, model: str, prompt: str) -> List[float]:
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(
                    f"{self.base_url}/embeddings",
                    json={"model": model or "auto", "input": prompt},
                    headers=headers,
                )
                if res.status_code == 200:
                    data = res.json()
                    return data.get("data", [{}])[0].get("embedding", [])
        except Exception as e:
            logger.warning(f"FreeLLMAPI embeddings failed: {e}")
        return []

    async def list_models(self) -> Dict[str, Any]:
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{self.base_url}/models", headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    models = []
                    for item in data.get("data", []):
                        models.append({
                            "name": item.get("id"),
                            "model": item.get("id"),
                            "details": item,
                        })
                    return {"models": models}
        except Exception as e:
            logger.warning(f"Failed to list models from FreeLLMAPI: {e}")
        return {"models": []}

    async def list_running(self) -> Dict[str, Any]:
        return {"models": []}

    async def unload_model(self, model: str) -> Dict[str, Any]:
        return {"status": "ok"}

    async def close(self):
        """Cleanup on server shutdown."""
        self.is_connected = False
