import logging
import time
import json
import httpx
from typing import Dict, Any, List, Optional, AsyncGenerator, Union

from config import PAIR_HOST, AUTO_WAKE_AI_PC
from providers.ollama import OllamaProvider
from core.ai_pc_manager import ensure_ai_pc_ready, is_ai_pc_reachable

logger = logging.getLogger(__name__)


class PairProvider(OllamaProvider):
    """
    Provider for NVIDIA PAIR (Personal AI Router) / NVIDIA GPU Node.
    Distributes workloads to the dedicated NVIDIA PAIR GPU node.
    Features:
    1. Zero-downtime automatic failover to local node (127.0.0.1:11434).
    2. Resilient streaming failover with circuit-breaker protection (30s window).
    3. Headless Wake-on-LAN integration when remote node drops offline.
    4. TTFT telemetry and node latency tracking.
    """

    def __init__(self, host: str = PAIR_HOST, fallback_host: str = "http://127.0.0.1:11434"):
        super().__init__(host=host)
        self.primary_host = host.rstrip("/")
        self.fallback_host = fallback_host.rstrip("/") if fallback_host else ""
        self._primary_healthy = True
        self._last_failure_time = 0.0
        self._circuit_breaker_window = 15.0
        self._total_requests = 0
        self._total_failovers = 0

        # Dedicated client with resilient 10.0s connect timeout for NVIDIA PAIR LAN/Wi-Fi stability
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=None, write=60.0, pool=None),
            limits=httpx.Limits(max_connections=30, max_keepalive_connections=15),
        )
        logger.info(
            f"[PAIR-CLUSTER] Initialized NVIDIA PAIR Provider: Primary={self.primary_host} "
            f"| Fallback={self.fallback_host}"
        )

        if AUTO_WAKE_AI_PC:
            try:
                ensure_ai_pc_ready(wait_for_ready=False)
            except Exception as e:
                logger.warning(f"[NVIDIA-PAIR] Initial reachability check failed: {e}")

    def _is_primary_available(self) -> bool:
        """Checks if the primary NVIDIA PAIR node is considered available or within circuit-breaker cooling."""
        if not self._primary_healthy:
            elapsed = time.time() - self._last_failure_time
            if elapsed < self._circuit_breaker_window:
                return False
            # Circuit breaker window expired — attempt probe
            logger.info(f"[PAIR-CLUSTER] Circuit breaker expired ({elapsed:.1f}s). Probing primary node {self.primary_host}...")
            self._primary_healthy = True
        return True

    def _mark_primary_failed(self, error: Optional[Exception] = None):
        """Marks primary node as degraded and logs failure."""
        self._primary_healthy = False
        self._last_failure_time = time.time()
        self._total_failovers += 1
        err_msg = f"{type(error).__name__}: {error}" if (error and str(error).strip()) else (type(error).__name__ if error else "Unreachable")
        logger.warning(
            f"[PAIR-CLUSTER] Primary node {self.primary_host} marked degraded (Error: {err_msg}). "
            f"Engaging circuit breaker for {self._circuit_breaker_window}s."
        )

    def reset_circuit_breaker(self):
        """Manually or programmatically reset circuit breaker to re-enable primary node."""
        self._primary_healthy = True
        self._last_failure_time = 0.0
        logger.info(f"[PAIR-CLUSTER] Circuit breaker manually reset. Primary node {self.primary_host} re-enabled.")

    def get_cluster_telemetry(self) -> Dict[str, Any]:
        """Returns node telemetry and health statistics."""
        return {
            "primary_host": self.primary_host,
            "fallback_host": self.fallback_host,
            "primary_healthy": self._primary_healthy,
            "active_host": self.primary_host if self._is_primary_available() else self.fallback_host,
            "circuit_breaker_active": not self._is_primary_available(),
            "seconds_since_last_failure": (
                round(time.time() - self._last_failure_time, 1) if self._last_failure_time > 0 else None
            ),
            "total_requests": self._total_requests,
            "total_failovers": self._total_failovers,
        }

    async def _post(self, endpoint: str, json_data: Dict[str, Any]) -> Dict[str, Any]:
        self._total_requests += 1

        # 1. Circuit breaker: if primary is marked down, route straight to fallback
        if not self._is_primary_available() and self.fallback_host:
            fallback_url = f"{self.fallback_host}/api/{endpoint}"
            try:
                res = await self._client.post(fallback_url, json=json_data)
                res.raise_for_status()
                return res.json() if res.text.strip() else {}
            except Exception as fe:
                err_msg = f"{type(fe).__name__}: {fe}" if str(fe).strip() else type(fe).__name__
                logger.warning(f"[PAIR-CLUSTER] Fallback node {self.fallback_host} failed ({err_msg})")
                raise fe

        # 2. Try primary node
        try:
            res = await self._client.post(f"{self.primary_host}/api/{endpoint}", json=json_data)
            res.raise_for_status()
            self._primary_healthy = True
            return res.json() if res.text.strip() else {}
        except Exception as e:
            self._mark_primary_failed(e)
            if AUTO_WAKE_AI_PC and not is_ai_pc_reachable():
                logger.warning("[NVIDIA-PAIR] Primary request failed and node is unreachable. Triggering native WoL...")
                ensure_ai_pc_ready(force_check=True)

            if self.fallback_host and self.primary_host != self.fallback_host:
                err_str = f"{type(e).__name__}: {e}" if str(e).strip() else type(e).__name__
                logger.info(
                    f"[PAIR-CLUSTER] Primary node {self.primary_host} failed ({err_str}). "
                    f"Failing over to local node {self.fallback_host}..."
                )
                try:
                    fallback_url = f"{self.fallback_host}/api/{endpoint}"
                    res = await self._client.post(fallback_url, json=json_data)
                    res.raise_for_status()
                    return res.json() if res.text.strip() else {}
                except Exception as fe:
                    fe_str = f"{type(fe).__name__}: {fe}" if str(fe).strip() else type(fe).__name__
                    logger.warning(f"[PAIR-CLUSTER] Fallback node {self.fallback_host} also failed: {fe_str}")
            raise e


    async def _get(self, endpoint: str) -> Dict[str, Any]:
        self._total_requests += 1

        if not self._is_primary_available() and self.fallback_host:
            fallback_url = f"{self.fallback_host}/api/{endpoint}"
            res = await self._client.get(fallback_url)
            res.raise_for_status()
            return res.json() if res.text.strip() else {}

        try:
            res = await self._client.get(f"{self.primary_host}/api/{endpoint}")
            res.raise_for_status()
            self._primary_healthy = True
            return res.json() if res.text.strip() else {}
        except Exception as e:
            self._mark_primary_failed(e)
            if self.fallback_host and self.primary_host != self.fallback_host:
                logger.info(
                    f"[PAIR-CLUSTER] Primary node {self.primary_host} GET failed ({e}). "
                    f"Failing over to {self.fallback_host}..."
                )
                try:
                    fallback_url = f"{self.fallback_host}/api/{endpoint}"
                    res = await self._client.get(fallback_url)
                    res.raise_for_status()
                    return res.json() if res.text.strip() else {}
                except Exception as fe:
                    logger.warning(f"[PAIR-CLUSTER] Fallback GET {self.fallback_host} failed: {fe}")
            raise e

    async def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False,
        keep_alive: str = "5m",
        **kwargs,
    ) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        """
        Chat completion with resilient node failover for both streaming and non-streaming modes.
        """
        self._total_requests += 1

        if not stream:
            payload = {
                "model": model,
                "messages": messages,
                "keep_alive": keep_alive,
                "stream": False,
            }
            if options:
                payload["options"] = options
            if "tools" in kwargs and kwargs["tools"]:
                payload["tools"] = kwargs["tools"]
            if "format" in kwargs:
                payload["format"] = kwargs["format"]
            elif kwargs.get("json_mode"):
                payload["format"] = "json"
            return await self._post("chat", payload)

        payload = {
            "model": model,
            "messages": messages,
            "keep_alive": keep_alive,
            "stream": True,
        }
        if options:
            payload["options"] = options
        if "tools" in kwargs and kwargs["tools"]:
            payload["tools"] = kwargs["tools"]
        if "format" in kwargs:
            payload["format"] = kwargs["format"]
        elif kwargs.get("json_mode"):
            payload["format"] = "json"

        # Determine target host based on circuit breaker
        target_host = self.primary_host if self._is_primary_available() else self.fallback_host

        async def _connect_stream(host_to_use: str):
            req = self._client.build_request("POST", f"{host_to_use}/api/chat", json=payload)
            resp = await self._client.send(req, stream=True)
            if resp.status_code == 400 and "does not support tools" in (await resp.aread()).decode(errors="ignore"):
                await resp.aclose()
                if "tools" in payload:
                    del payload["tools"]
                req = self._client.build_request("POST", f"{host_to_use}/api/chat", json=payload)
                resp = await self._client.send(req, stream=True)
            if resp.status_code != 200:
                body_err = (await resp.aread()).decode(errors="ignore")
                await resp.aclose()
                raise httpx.HTTPStatusError(f"HTTP {resp.status_code}: {body_err}", request=req, response=resp)
            return resp

        # Attempt to open streaming connection
        response = None
        active_host = target_host

        try:
            response = await _connect_stream(target_host)
            if target_host == self.primary_host:
                self._primary_healthy = True
        except Exception as e:
            if target_host == self.primary_host and self.fallback_host and self.primary_host != self.fallback_host:
                self._mark_primary_failed(e)
                if AUTO_WAKE_AI_PC and not is_ai_pc_reachable():
                    ensure_ai_pc_ready(force_check=True)
                logger.info(
                    f"[PAIR-CLUSTER] Streaming chat to primary {self.primary_host} failed ({e}). "
                    f"Seamlessly failing over to local node {self.fallback_host}..."
                )
                try:
                    response = await _connect_stream(self.fallback_host)
                    active_host = self.fallback_host
                except Exception as fe:
                    logger.error(f"[PAIR-CLUSTER] Fallback stream to {self.fallback_host} also failed: {fe}")
                    raise fe
            else:
                raise e

        # Generator that yields chunks and protects against immediate disconnects
        async def resilient_stream_generator(res, host_used):
            start_time = time.time()
            ttft_logged = False
            chunks_yielded = 0
            try:
                async for line in res.aiter_lines():
                    if line:
                        if not ttft_logged:
                            ttft_ms = (time.time() - start_time) * 1000
                            logger.info(f"[TELEMETRY] Node: {host_used} | Model: {model} | TTFT: {ttft_ms:.1f}ms")
                            ttft_logged = True
                        chunks_yielded += 1
                        yield json.loads(line)
            except Exception as stream_err:
                # If stream broke before yielding any tokens and we were on primary, attempt fallback
                if chunks_yielded == 0 and host_used == self.primary_host and self.fallback_host:
                    logger.warning(
                        f"[PAIR-CLUSTER] Stream broken at 0 tokens from {host_used} ({stream_err}). "
                        f"Retrying on fallback {self.fallback_host}..."
                    )
                    self._mark_primary_failed(stream_err)
                    try:
                        fallback_res = await _connect_stream(self.fallback_host)
                        async for line in fallback_res.aiter_lines():
                            if line:
                                yield json.loads(line)
                        return
                    except Exception as fe:
                        logger.error(f"[PAIR-CLUSTER] Fallback retry failed: {fe}")
                raise stream_err
            finally:
                await res.aclose()

        return resilient_stream_generator(response, active_host)

    async def generate(
        self,
        model: str,
        prompt: str,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False,
        keep_alive: str = "5m",
        **kwargs,
    ) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        """
        Text generation with resilient node failover for both streaming and non-streaming modes.
        """
        self._total_requests += 1

        if not stream:
            payload = {
                "model": model,
                "prompt": prompt,
                "keep_alive": keep_alive,
                "stream": False,
            }
            if options:
                payload["options"] = options
            return await self._post("generate", payload)

        payload = {
            "model": model,
            "prompt": prompt,
            "keep_alive": keep_alive,
            "stream": True,
        }
        if options:
            payload["options"] = options

        target_host = self.primary_host if self._is_primary_available() else self.fallback_host

        async def _connect_stream(host_to_use: str):
            req = self._client.build_request("POST", f"{host_to_use}/api/generate", json=payload)
            resp = await self._client.send(req, stream=True)
            if resp.status_code != 200:
                body_err = (await resp.aread()).decode(errors="ignore")
                await resp.aclose()
                raise httpx.HTTPStatusError(f"HTTP {resp.status_code}: {body_err}", request=req, response=resp)
            return resp

        response = None
        active_host = target_host

        try:
            response = await _connect_stream(target_host)
            if target_host == self.primary_host:
                self._primary_healthy = True
        except Exception as e:
            if target_host == self.primary_host and self.fallback_host and self.primary_host != self.fallback_host:
                self._mark_primary_failed(e)
                if AUTO_WAKE_AI_PC and not is_ai_pc_reachable():
                    ensure_ai_pc_ready(force_check=True)
                logger.info(
                    f"[PAIR-CLUSTER] Streaming generate to primary {self.primary_host} failed ({e}). "
                    f"Seamlessly failing over to local node {self.fallback_host}..."
                )
                try:
                    response = await _connect_stream(self.fallback_host)
                    active_host = self.fallback_host
                except Exception as fe:
                    logger.error(f"[PAIR-CLUSTER] Fallback stream to {self.fallback_host} failed: {fe}")
                    raise fe
            else:
                raise e

        async def resilient_stream_generator(res, host_used):
            start_time = time.time()
            ttft_logged = False
            chunks_yielded = 0
            try:
                async for line in res.aiter_lines():
                    if line:
                        if not ttft_logged:
                            ttft_ms = (time.time() - start_time) * 1000
                            logger.info(f"[TELEMETRY] Node: {host_used} | Model: {model} | TTFT: {ttft_ms:.1f}ms")
                            ttft_logged = True
                        chunks_yielded += 1
                        yield json.loads(line)
            except Exception as stream_err:
                if chunks_yielded == 0 and host_used == self.primary_host and self.fallback_host:
                    logger.warning(
                        f"[PAIR-CLUSTER] Generate stream broken at 0 tokens ({stream_err}). "
                        f"Retrying on fallback {self.fallback_host}..."
                    )
                    self._mark_primary_failed(stream_err)
                    try:
                        fallback_res = await _connect_stream(self.fallback_host)
                        async for line in fallback_res.aiter_lines():
                            if line:
                                yield json.loads(line)
                        return
                    except Exception as fe:
                        logger.error(f"[PAIR-CLUSTER] Fallback retry failed: {fe}")
                raise stream_err
            finally:
                await res.aclose()

        return resilient_stream_generator(response, active_host)
