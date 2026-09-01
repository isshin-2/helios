import asyncio
import time
import psutil
from typing import Dict, Any, List, Optional
import httpx
from providers.base import BaseProvider
from health.monitor import SystemMonitor
import config
from config import KEEP_ALIVE, MODEL_CONFIG, RAM_MIN_FREE_MB, MODEL_CONTEXT_BUFFER_MB, is_budget_mode_active
import logging

logger = logging.getLogger(__name__)

# How long (seconds) to trust that a model is still loaded without re-checking Ollama
_MODEL_CACHE_TTL = 60.0

# ─── MUTEX: Prevents concurrent model load/unload race conditions ────
_model_lock = asyncio.Lock()

class ModelManager:
    def __init__(self, provider: BaseProvider, monitor: SystemMonitor):
        self.provider = provider
        self.monitor = monitor
        # Cache: {model_name: timestamp_when_confirmed_loaded}
        self._loaded_cache: Dict[str, float] = {}
        
    async def ensure_model_loaded(self, target_model: str, required_context: int) -> bool:
        """
        Memory-aware loading algorithm with mutex lock, retry logic, and circuit breaker.
        Under budget pressure: enforces strict 1-model-in-RAM with telemetry.
        """
        async with _model_lock:
            # ─── BUDGET MODE: Aggressive Pre-Eviction ─────────────────
            if is_budget_mode_active():
                running = await self.provider.list_running()
                for rm in running.get('models', []):
                    running_name = rm.get('name', '')
                    if running_name and running_name != target_model:
                        logger.info(f"[BUDGET] Targeting {running_name} for eviction to load {target_model}")
                        
                        start_ram = psutil.virtual_memory().available
                        evict_start = time.time()
                        eviction_success = False
                        
                        for attempt in range(3):
                            try:
                                await asyncio.wait_for(
                                    self.provider.unload_model(running_name), 
                                    timeout=5.0
                                )
                                eviction_success = True
                                break
                            except asyncio.TimeoutError:
                                logger.warning(f"[BUDGET] Eviction timeout attempt {attempt+1}/3 for {running_name}")
                            except Exception as e:
                                logger.error(f"[BUDGET] Eviction error: {str(e)}")
                            await asyncio.sleep(1)  # Backoff between retries
                            
                        if not eviction_success:
                            config.CIRCUIT_BREAKER_TRIPPED = True
                            logger.error("[CRITICAL] Eviction pipeline failed 3x. Circuit Breaker TRIPPED. Reverting to standard mode.")
                            return False
                            
                        await asyncio.sleep(1.0)  # Yield for Windows memory reclaim
                        
                        reclaimed_mb = (psutil.virtual_memory().available - start_ram) / (1024 * 1024)
                        evict_time = time.time() - evict_start
                        logger.info(f"[TELEMETRY] Evicted: {running_name} | Reclaimed: {reclaimed_mb:.2f} MB | Time: {evict_time:.2f}s")
                        
                        # Invalidate cache for the evicted model
                        self._loaded_cache.pop(running_name, None)
            # ──────────────────────────────────────────────────────────

            # Fast path: if we confirmed this model was loaded recently, skip all HTTP checks
            cached_time = self._loaded_cache.get(target_model)
            if cached_time and (time.monotonic() - cached_time) < _MODEL_CACHE_TTL:
                return True

            # Step 1: Check if already loaded
            status = await self.monitor.get_full_status()
            loaded = status.get("loaded_models", [])
            
            # In case the monitor still returns old strings, handle gracefully
            if loaded and isinstance(loaded[0], str):
                if target_model in loaded:
                    self._loaded_cache[target_model] = time.monotonic()
                    return True
            else:
                if any(m.get("name") == target_model for m in loaded):
                    self._loaded_cache[target_model] = time.monotonic()
                    return True

            # Step 2: Estimate required memory
            tags = await self.provider.list_models()
            target_size_bytes = 0
            for m in tags.get("models", []):
                if m.get("name") == target_model:
                    target_size_bytes = m.get("size", 0)
                    break
                    
            target_size_mb = target_size_bytes / (1024 * 1024)
            required_memory_mb = target_size_mb + MODEL_CONTEXT_BUFFER_MB
            
            # Step 3 & 4: Targeted unloading loop
            while True:
                status = await self.monitor.get_full_status()
                available_ram_mb = status.get("available_ram_mb", 0)
                
                if available_ram_mb >= required_memory_mb + RAM_MIN_FREE_MB:
                    break
                    
                loaded = status.get("loaded_models", [])
                candidates = []
                for m in loaded:
                    if isinstance(m, str):
                        if m != target_model:
                            candidates.append({"name": m, "size_vram": 0})
                    else:
                        if m.get("name") != target_model:
                            candidates.append(m)
                            
                if not candidates:
                    raise MemoryError(
                        f"Insufficient memory to load '{target_model}'. "
                        f"Required: {required_memory_mb:.2f} MB, "
                        f"Available: {available_ram_mb:.2f} MB. "
                        "No safe unload candidates remain."
                    )
                    
                candidates.sort(key=lambda x: x.get("size_vram", 0), reverse=True)
                largest = candidates[0]
                
                logger.info(f"Insufficient memory. Unloading {largest.get('name')} to free up space for {target_model}")
                await self.provider.unload_model(largest.get("name"))
                self._loaded_cache.pop(largest.get("name"), None)

            # Model is confirmed loaded — cache it
            self._loaded_cache[target_model] = time.monotonic()
            return True
        
    async def execute_request(self, 
                              target_model: str, 
                              messages: List[Dict[str, Any]], 
                              context_size: int,
                              stream: bool = False,
                              **kwargs) -> Any:
        """
        Executes a request with automatic fallback handling.
        """
        current_model = target_model
        attempted = set()
        
        while current_model:
            attempted.add(current_model)
            try:
                logger.info(f"Attempting execution with model: {current_model}")
                if current_model.startswith("gemini") or current_model == "antigravity":
                    if not hasattr(self, "gemini"):
                        from models.gemini_client import GeminiClient
                        self.gemini = GeminiClient()
                    
                    raw_stream = await self.gemini.chat(
                        model=current_model,
                        messages=messages,
                        stream=stream,
                        **kwargs
                    )
                    
                    if stream:
                        raw_iter = raw_stream.__aiter__()
                        try:
                            first_chunk = await raw_iter.__anext__()
                        except StopAsyncIteration:
                            first_chunk = None
                            
                        if first_chunk and first_chunk["type"] == "error":
                            raise RuntimeError(f"Cloud API Error: {first_chunk['content']}")

                        async def adapted_stream():
                            if first_chunk:
                                if first_chunk["type"] == "text":
                                    yield {"message": {"content": first_chunk["content"]}}
                                elif first_chunk["type"] == "tool_call":
                                    yield {"message": {"tool_calls": [{
                                        "function": {
                                            "name": first_chunk["content"]["name"],
                                            "arguments": first_chunk["content"].get("args", {})
                                        }
                                    }]}}
                            async for chunk in raw_iter:
                                if chunk["type"] == "text":
                                    yield {"message": {"content": chunk["content"]}}
                                elif chunk["type"] == "tool_call":
                                    yield {"message": {"tool_calls": [{
                                        "function": {
                                            "name": chunk["content"]["name"],
                                            "arguments": chunk["content"].get("args", {})
                                        }
                                    }]}}
                                elif chunk["type"] == "error":
                                    yield {"message": {"content": f"\n\n[System: {chunk['content']}]"}}
                        return adapted_stream()
                    else:
                        if isinstance(raw_stream, dict) and "429" in str(raw_stream.get("content", "")):
                            raise RuntimeError(f"Cloud API Error: {raw_stream['content']}")
                        return raw_stream
                else:
                    # Ensure RAM is okay for local models
                    await self.ensure_model_loaded(current_model, context_size)
                    
                    # Execute
                    options = {"num_ctx": context_size}
                    
                    # We return the raw response or stream
                    return await self.provider.chat(
                        model=current_model,
                        messages=messages,
                        options=options,
                        keep_alive=KEEP_ALIVE["default"],
                        stream=stream,
                        **kwargs
                    )
                
            except httpx.RequestError as e:
                logger.error(f"Request failed for {current_model}: {e}")
                
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                logger.warning(f"Model {current_model} failed:\n{tb}")
            
            config_data = MODEL_CONFIG.get(current_model, {})
            next_model = config_data.get("fallback")
            
            if next_model and next_model not in attempted:
                logger.warning(f"Falling back to {next_model}...")
                current_model = next_model
            else:
                raise RuntimeError(f"All models in fallback chain failed. Last attempted: {current_model}")
