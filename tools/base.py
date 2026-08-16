from abc import ABC, abstractmethod
from typing import Tuple
from pydantic import BaseModel

class BaseTool(ABC):
    """
    Abstract base class for all tools in HELIOS.
    Tools differ from the old skills by having explicit input schemas
    and declaring their permission requirements.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the tool, used for routing."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """A detailed description of what the tool does."""
        pass
        
    @property
    @abstractmethod
    def input_schema(self) -> type[BaseModel]:
        """Pydantic model representing the expected inputs."""
        pass

    @property
    def requires_permission(self) -> bool:
        """Whether this tool requires security approval before execution."""
        return False

    @abstractmethod
    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        """
        Execute the tool.
        Returns: (result_text, tool_name)
        """
        pass
