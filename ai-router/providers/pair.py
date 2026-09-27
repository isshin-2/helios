import logging
from config import PAIR_HOST
from providers.ollama import OllamaProvider

logger = logging.getLogger(__name__)

class PairProvider(OllamaProvider):
    """
    Provider for NVIDIA PAIR (Personal AI Router).
    PAIR acts as a transparent proxy for Ollama/OpenAI endpoints.
    By inheriting from OllamaProvider, we use the native Ollama API which PAIR proxies seamlessly.
    """
    def __init__(self, host: str = PAIR_HOST):
        super().__init__(host=host)
        logger.info(f"Initialized NVIDIA PAIR Provider routing to {host}")
