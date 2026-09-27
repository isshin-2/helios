from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, AsyncGenerator, Union

class BaseProvider(ABC):
    """
    Abstract base class for all LLM providers (e.g., Ollama, OpenAI, Anthropic).
    """

    @abstractmethod
    async def chat(self, model: str, messages: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None, stream: bool = False, **kwargs) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        pass

    @abstractmethod
    async def generate(self, model: str, prompt: str, options: Optional[Dict[str, Any]] = None, stream: bool = False, **kwargs) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        pass

    @abstractmethod
    async def get_embeddings(self, model: str, prompt: str) -> List[float]:
        pass

    @abstractmethod
    async def list_models(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def list_running(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def unload_model(self, model: str) -> Dict[str, Any]:
        pass
