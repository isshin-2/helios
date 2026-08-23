import json
from typing import Tuple
from pydantic import BaseModel, Field
from .base import BaseSkill

class AskUserSchema(BaseModel):
    question: str = Field(..., description="The specific question you want to ask the user. Be clear about what you need to know to proceed.")

class AskUserSkill(BaseSkill):
    """
    Skill for asking the user a question in the middle of a task instead of guessing.
    """
    def __init__(self, permission_manager):
        self.permission_manager = permission_manager

    def get_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "AskUserTool",
                "description": "Stops your execution and displays an interactive prompt asking the user a question. Use this whenever you are unsure about parameters, paths, or intent, rather than guessing.",
                "parameters": AskUserSchema.schema()
            }
        }

    def match(self, prompt: str) -> bool:
        # Since this is primarily LLM-driven through schema routing, we just return False for regex matching
        return False

    async def execute(self, prompt: str, **kwargs) -> Tuple[str, str]:
        # Handle case where LLM called it as a tool via router
        if "{" in prompt and "}" in prompt:
            try:
                data = json.loads(prompt)
                question = data.get("question", "Please provide input:")
                return (f"INPUT_REQUIRED::{question}", "ask_user")
            except Exception:
                pass
        
        return (f"INPUT_REQUIRED::{prompt}", "ask_user")
