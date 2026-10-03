import logging
from typing import Dict, Any, List, Optional, AsyncGenerator, Union
from config import PAIR_HOST, AUTO_WAKE_AI_PC
from providers.ollama import OllamaProvider
from core.ai_pc_manager import ensure_ai_pc_ready, is_ai_pc_reachable

logger = logging.getLogger(__name__)

class PairProvider(OllamaProvider):
    """
    Provider for NVIDIA PAIR (Personal AI Router).
    PAIR acts as a transparent proxy for Ollama/OpenAI endpoints.
    Distributes workloads to the dedicated AI PC GPU node via mTLS.
    Automatically checks AI PC reachability and runs wake script if offline.
    """
    def __init__(self, host: str = PAIR_HOST):
        super().__init__(host=host)
        logger.info(f"Initialized NVIDIA PAIR Provider routing to {host}")
        
        # Verify AI PC status if auto-wake is enabled
        if AUTO_WAKE_AI_PC:
            try:
                ensure_ai_pc_ready()
            except Exception as e:
                logger.warning(f"[AI-PC] Initial reachability check failed: {e}")

    async def _post(self, endpoint: str, json_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return await super()._post(endpoint, json_data)
        except Exception as e:
            # If request fails, verify if AI PC became unreachable
            if AUTO_WAKE_AI_PC and not is_ai_pc_reachable():
                logger.warning("[AI-PC] Request failed and AI PC is unreachable. Triggering wake script...")
                ensure_ai_pc_ready(force_check=True)
            raise e
