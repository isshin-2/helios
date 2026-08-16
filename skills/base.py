from abc import ABC, abstractmethod
from typing import Any, Tuple

class BaseSkill(ABC):
    @abstractmethod
    def match(self, prompt: str) -> bool:
        """Return True if this skill should handle the prompt."""
        pass
        
    @abstractmethod
    async def execute(self, prompt: str, **kwargs) -> Tuple[str, str]:
        """Execute the skill and return (result_text, tool_name)"""
        pass
