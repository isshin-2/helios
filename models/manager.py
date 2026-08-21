import asyncio
from typing import Dict, Any, List, Optional
import httpx
from providers.base import BaseProvider
from health.monitor import SystemMonitor
from config import KEEP_ALIVE, MODEL_CONFIG, RAM_MIN_FREE_MB, MODEL_CONTEXT_BUFFER_MB
import logging

logger = logging.getLogger(__name__)

class ModelManager:
    def __init__(self, provider: BaseProvider, monitor: SystemMonitor):
        self.provider = provider
        self.monitor = monitor
        
    async def ensure_model_loaded(self, target_model: str, required_context: int) -> bool:
        """
        Memory-aware loading algorithm. Only unloads models if memory is constrained.
        """
        # Step 1: Check if already loaded
        status = await self.monitor.get_full_status()
        loaded = status.get("loaded_models", [])
        
        # In case the monitor still returns old strings, handle gracefully
        if loaded and isinstance(loaded[0], str):
            if target_model in loaded:
                return True
        else:
            if any(m.get("name") == target_model for m in loaded):
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
                # Enough capacity
                break
                
            loaded = status.get("loaded_models", [])
            # Filter out target_model just in case, and normalize elements to dicts
            candidates = []
            for m in loaded:
                if isinstance(m, str):
                    if m != target_model:
                        candidates.append({"name": m, "size_vram": 0})
                else:
                    if m.get("name") != target_model:
                        candidates.append(m)
                        
            if not candidates:
                # Step 5: Failure handling
                raise MemoryError(
                    f"Insufficient memory to load '{target_model}'. "
                    f"Required: {required_memory_mb:.2f} MB, "
                    f"Available: {available_ram_mb:.2f} MB. "
                    "No safe unload candidates remain."
                )
                
            # Sort by size_vram descending
            candidates.sort(key=lambda x: x.get("size_vram", 0), reverse=True)
            largest = candidates[0]
            
            logger.info(f"Insufficient memory. Unloading {largest.get('name')} to free up space for {target_model}")
            await self.provider.unload_model(largest.get("name"))
            
            # Loop back and get_full_status() to refresh memory values

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
                # Ensure RAM is okay
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
                logger.error(f"Unexpected error for {current_model}: {e}")
                
            # If we get here, it failed. Try fallback.
            config = MODEL_CONFIG.get(current_model, {})
            next_model = config.get("fallback")
            
            if next_model and next_model not in attempted:
                logger.warning(f"Falling back to {next_model}...")
                current_model = next_model
            else:
                raise RuntimeError(f"All models in fallback chain failed. Last attempted: {current_model}")
