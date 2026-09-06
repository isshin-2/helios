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
            import mss
            import numpy as np
            from PIL import Image
            
            with mss.mss() as sct:
                # monitor 1 is the primary monitor
                sct_img = sct.grab(sct.monitors[1])
                # Convert to PIL Image
                screenshot = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            
            element_map = {}
            grid_map = {}
            from config import SOM_ENABLED, SOM_MIN_ELEMENT_THRESHOLD
            if SOM_ENABLED:
                from tools.som_overlay import get_ui_elements, draw_marks, draw_grid_overlay
                elements = get_ui_elements()
                if len(elements) >= SOM_MIN_ELEMENT_THRESHOLD:
                    screenshot, element_map = draw_marks(screenshot, elements)
                else:
                    screenshot, grid_map = draw_grid_overlay(screenshot)
            # Store for computer_control to reference
            ScreenVisionTool._last_element_map = element_map
            ScreenVisionTool._last_grid_map = grid_map
            
            # Downscale image to save tokens while keeping it legible for the vision model
            screenshot.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
            
            # Convert to base64 with moderate compression
            buffered = io.BytesIO()
            screenshot.save(buffered, format="JPEG", quality=60)
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to capture screen: {e}")
            return (f"Error: Failed to capture screen: {e}", self.name)

        if element_map:
            legend = "\n".join([f"[{eid}] {e.name} ({e.control_type})" for eid, e in element_map.items()])
            query = f"{query}\n\nVisible UI Elements (use element ID for clicks):\n{legend}"
        elif grid_map:
            query = f"{query}\n\nA 4x4 grid overlay (A1-D4) has been drawn. Reference grid cells for locations."

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
                
            # Use Local Vision Model (moondream)
            if hasattr(self.provider, "_post"):
                res = await self.provider._post("generate", {
                    "model": VISION_MODEL,
                    "prompt": query,
                    "images": [img_str],
                    "stream": False,
                    "keep_alive": 0  # FORCE UNLOAD: Prevents concurrent model OOM BSODs
                })
                response_text = res.get("response", "No response from vision model.")
                return (img_markdown + response_text.strip(), self.name)
            else:
                return (f"Error: Provider does not support local vision.", self.name)
                
        except Exception as e:
            logger.error(f"Vision model error: {e}")
            return (f"Error from vision model: {e}", self.name)
