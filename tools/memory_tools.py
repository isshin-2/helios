from typing import Tuple, Optional
from pydantic import BaseModel, Field

from tools.base import BaseTool
from router.memory import MemoryManager
import logging

logger = logging.getLogger(__name__)

# ─── CORE MEMORY TOOL ───────────────────────────────────────────

class CoreMemoryAppendInput(BaseModel):
    section: str = Field(description="The section of core memory to append to (e.g., 'user_preferences', 'current_project_context').")
    content: str = Field(description="The factual information to store in this section.")

class CoreMemoryAppendTool(BaseTool):
    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager

    @property
    def name(self) -> str:
        return "CoreMemoryAppendTool"

    @property
    def description(self) -> str:
        return "Appends critical context to your Core Memory. This memory is ALWAYS present in your prompt, so only use it for absolute essentials."

    @property
    def input_schema(self) -> type[BaseModel]:
        return CoreMemoryAppendInput

    @property
    def requires_permission(self) -> bool:
        return False

    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        section = kwargs.get("section")
        content = kwargs.get("content")
        if not section or not content:
            return ("Error: Missing section or content.", self.name)
            
        success = await self.memory.append_core_memory(user_id, section, content)
        if success:
            return (f"Successfully appended to core memory section '{section}'.", self.name)
        else:
            return ("Failed to append to core memory.", self.name)

# ─── ARCHIVAL MEMORY TOOL ────────────────────────────────────────

class ArchivalMemorySearchInput(BaseModel):
    query: str = Field(description="The natural language query to search for in your archival long-term memory.")

class ArchivalMemorySearchTool(BaseTool):
    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager

    @property
    def name(self) -> str:
        return "ArchivalMemorySearchTool"

    @property
    def description(self) -> str:
        return "Searches your massive archival memory (vector database) for past facts, previous conversations, or older project details."

    @property
    def input_schema(self) -> type[BaseModel]:
        return ArchivalMemorySearchInput

    @property
    def requires_permission(self) -> bool:
        return False

    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        query = kwargs.get("query")
        if not query:
            return ("Error: Missing query string.", self.name)
            
        results = await self.memory.search_memory(user_id, query)
        if results:
            formatted = "\n- ".join(results)
            return (f"Found the following facts in archival memory:\n- {formatted}", self.name)
        else:
            return ("No relevant facts found in archival memory.", self.name)
