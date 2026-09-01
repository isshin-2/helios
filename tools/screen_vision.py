import asyncio
from typing import Tuple, Optional
from pydantic import BaseModel, Field
import io
import base64
import logging

try:
    from PIL import ImageGrab
except ImportError:
    ImageGrab = None

from tools.base import BaseTool
from providers.base import BaseProvider
from health.monitor import SystemMonitor
from config import VISION_MODEL, LLM_PROVIDER

logger = logging.getLogger(__name__)

class ScreenVisionInput(BaseModel):
    query: str = Field(description="The question or task regarding the current screen contents.")

class ScreenVisionTool(BaseTool):
    name: str = "screen_vision"
    description: str = "Takes a screenshot of the main display and uses a local vision model to analyze it and answer your query."
    input_schema: type[BaseModel] = ScreenVisionInput

    def __init__(self, provider: BaseProvider, monitor: SystemMonitor):
        self.provider = provider
        self.monitor = monitor

    async def execute(self, user_id: int, query: str) -> Tuple[str, str]:
        if ImageGrab is None:
            return ("Error: Pillow is not installed. Run `pip install Pillow` to use screen vision.", self.name)
            
        try:
            # Capture the screen
            screenshot = ImageGrab.grab()
            
            # Convert to base64
            buffered = io.BytesIO()
            screenshot.save(buffered, format="JPEG", quality=80)
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to capture screen: {e}")
            return (f"Error: Failed to capture screen: {e}", self.name)

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": query},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_str}"}}
                ]
            }
        ]

        try:
            from models.gemini_client import GeminiClient
            gc = GeminiClient()
            response_text = ""
            async for chunk in gc.stream_chat(messages=messages, model="antigravity"):
                if chunk["type"] == "text":
                    response_text += chunk["content"]
                elif chunk["type"] == "error":
                    return (f"Cloud Vision Error: {chunk['content']}", self.name)
            
            # Save screenshot for Web UI
            try:
                import time
                import os
                timestamp = int(time.time())
                filename = f"screenshot_{timestamp}.jpg"
                filepath = os.path.join("static", "media", filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                screenshot.save(filepath, format="JPEG", quality=80)
                img_markdown = f"![Screenshot](/static/media/{filename})\n\n"
            except Exception as e:
                logger.error(f"Failed to save screenshot for UI: {e}")
                img_markdown = ""
                
            return (img_markdown + (response_text.strip() if response_text else "No response from vision model."), self.name)
        except Exception as e:
            logger.error(f"Vision model error: {e}")
            return (f"Error from vision model: {e}", self.name)
