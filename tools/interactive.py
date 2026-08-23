from typing import Dict, Any, Tuple
from pydantic import BaseModel, Field
from .base import BaseTool
import json

class AskUserSchema(BaseModel):
    question: str = Field(..., description="The specific question you want to ask the user. Be clear about what you need to know to proceed.")

class AskUserTool(BaseTool):
    """
    Tool for asking the user a question in the middle of a task instead of guessing.
    """
    def __init__(self, permission_manager):
        self.permission_manager = permission_manager

    @property
    def name(self) -> str:
        return "AskUserTool"

    @property
    def description(self) -> str:
        return "Stops your execution and displays an interactive prompt asking the user a question. Use this whenever you are unsure about parameters, paths, or intent, rather than guessing."

    @property
    def input_schema(self) -> type[BaseModel]:
        return AskUserSchema

    async def execute(self, user_id: int, question: str = "Please provide input:", **kwargs) -> Tuple[str, str]:
        return (f"INPUT_REQUIRED::{question}", self.name)
