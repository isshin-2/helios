import asyncio
from typing import Dict, Any, List, Optional
import httpx
from providers.base import BaseProvider
from health.monitor import SystemMonitor
from config import KEEP_ALIVE, MODEL_CONFIG, RAM_MIN_FREE_MB
import logging

logger = logging.getLogger(__name__)

class ModelManager:
    def __init__(self, provider: BaseProvider, monitor: SystemMonitor):
        self.provider = provider
        self.monitor = monitor
        
    async def ensure_model_loaded(self, target_model: str, required_context: int) -> bool:
        """
        Checks if model is loaded. If there are other models loaded, swap them out to save RAM.
        """
        status = await self.monitor.get_full_status()
        
        loaded = status.get("loaded_models", [])
        
        # Proactively unload any models that are NOT the target model (Swap)
        other_models = [m for m in loaded if m != target_model]
        if other_models:
            logger.info(f"Swapping models: unloading {other_models} to make room for {target_model}")
            for model in other_models:
                await self.provider.unload_model(model)
                
        # Ollama will automatically load target_model on the first request.
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
