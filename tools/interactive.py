from typing import Dict, Any, Tuple, List, Optional
from pydantic import BaseModel, Field
from .base import BaseTool
import json

class AskUserSchema(BaseModel):
    question: str = Field(..., description="The specific question you want to ask the user. Be clear about what you need to know to proceed.")
    options: Optional[List[str]] = Field(None, description="Optional list of choices for the user to select from (e.g. ['Gmail', 'Outlook']). If provided, the UI will present these as buttons.")

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
        return "Stops your execution and displays an interactive prompt asking the user a question. Use this whenever you are unsure about parameters, paths, or intent, rather than guessing. You can optionally provide a list of options for the user to choose from."

    @property
    def input_schema(self) -> type[BaseModel]:
        return AskUserSchema

    async def execute(self, user_id: int, question: str = "Please provide input:", options: Optional[List[str]] = None, **kwargs) -> Tuple[str, str]:
        import asyncio
        import os
        import sys
        import config
        
        # If running headlessly or disabled via config, fallback to CLI signaling
        if not getattr(config, "ENABLE_TENSURA_OVERLAY", True) or os.environ.get("DOCKER_ENV"):
            if options and len(options) > 0:
                options_str = "|".join(options)
                return (f"INPUT_REQUIRED::{question} [OPTIONS:{options_str}]", self.name)
            return (f"INPUT_REQUIRED::{question}", self.name)
        
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "overlays", "tensura_popup.py")
        
        # Prepare arguments
        args = [sys.executable, script_path, question]
        if options and len(options) > 0:
            args.append(",".join(options))
            
        try:
            # Run the popup as a non-blocking subprocess
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            result = stdout.decode().strip()
            
            if not result or result == "CANCELLED":
                return ("User cancelled the prompt or provided no input.", self.name)
                
            return (f"User replied: {result}", self.name)
            
        except Exception as e:
            # Fallback on crash (e.g. no display server)
            if options and len(options) > 0:
                options_str = "|".join(options)
                return (f"INPUT_REQUIRED::{question} [OPTIONS:{options_str}]", self.name)
            return (f"INPUT_REQUIRED::{question}", self.name)
