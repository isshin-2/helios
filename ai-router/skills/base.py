from abc import ABC, abstractmethod
from typing import Any, Tuple, List
from security.capabilities import Capability

class BaseSkill(ABC):
    @property
    def name(self) -> str:
        return self.__class__.__name__
        
    @property
    def description(self) -> str:
        return "Base skill"
        
    @property
    def required_capabilities(self) -> List[Capability]:
        return []

    @abstractmethod
    def match(self, prompt: str) -> bool:
        """Return True if this skill should handle the prompt."""
        pass
        
    @abstractmethod
    async def execute(self, prompt: str, **kwargs) -> Tuple[str, str]:
        """Execute the skill and return (result_text, tool_name)"""
        pass
