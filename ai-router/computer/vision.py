"""
HELIOS — Computer Vision Provider Interface
Separable VLM abstraction supporting Local VLMs (Ollama/vLLM), Cloud models (Gemini/Claude), and Mocking.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger("helios.computer.vision")


# ─── Abstract Vision Provider ────────────────────────────────────────────────

class ComputerVisionProvider(ABC):
    """
    Abstract interface for vision-based desktop reasoning.
    Separates the high-level agent reasoning model from the low-level vision model.
    """

    @abstractmethod
    async def analyze_screenshot(
        self,
        screenshot_base64: str,
        query: str,
        structured_context: Optional[str] = None
    ) -> str:
        """
        Analyze the screenshot in response to a user/agent query.
        Returns textual reasoning or findings.
        """
        ...

    @abstractmethod
    async def locate_element(
        self,
        screenshot_base64: str,
        element_description: str,
        screen_size: tuple[int, int]
    ) -> Optional[Dict[str, Any]]:
        """
        Locate a UI element visually on screen.
        Returns dict with: {"x": int, "y": int, "bounds": [l, t, r, b], "confidence": float} or None.
        """
        ...

    @abstractmethod
    async def describe_screen(
        self,
        screenshot_base64: str,
        focus_region: Optional[tuple[int, int, int, int]] = None
    ) -> str:
        """Provide a structured overview of what is currently on the screen."""
        ...


# ─── Local VLM Implementation (e.g. Moondream, Qwen2-VL, Ollama) ──────────────

class LocalComputerVisionProvider(ComputerVisionProvider):
    """
    Local vision inference provider running on Ollama, vLLM, or local PAIR node.
    """

    def __init__(self, provider: Any = None, model_name: str = "moondream"):
        self.provider = provider
        self.model_name = model_name

    async def analyze_screenshot(
        self,
        screenshot_base64: str,
        query: str,
        structured_context: Optional[str] = None
    ) -> str:
        prompt = query
        if structured_context:
            prompt = f"{query}\n\nKnown UI Context:\n{structured_context}"

        if self.provider and hasattr(self.provider, "_post"):
            try:
                res = await self.provider._post("generate", {
                    "model": self.model_name,
                    "prompt": prompt,
                    "images": [screenshot_base64],
                    "stream": False,
                    "keep_alive": 0  # Avoid VRAM retention if GPU memory is constrained
                })
                return str(res.get("response", "")).strip()
            except Exception as e:
                logger.error(f"Local vision analysis error: {e}")
                return f"Vision analysis failed: {e}"

        return f"[LocalVision {self.model_name}] Visual analysis completed for query: {query}"

    async def locate_element(
        self,
        screenshot_base64: str,
        element_description: str,
        screen_size: tuple[int, int]
    ) -> Optional[Dict[str, Any]]:
        query = (
            f"Locate the following UI element on screen: '{element_description}'.\n"
            f"Return JSON strictly in this format: {{\"x\": int, \"y\": int, \"confidence\": float}} "
            f"representing the pixel coordinates on a {screen_size[0]}x{screen_size[1]} screen."
        )
        res_text = await self.analyze_screenshot(screenshot_base64, query)
        
        # Parse JSON from response
        try:
            m = re.search(r'\{[^{}]*"x"\s*:\s*\d+.*\}', res_text, re.DOTALL)
            if m:
                data = json.loads(m.group(0))
                x = int(data.get("x", 0))
                y = int(data.get("y", 0))
                conf = float(data.get("confidence", 0.7))
                return {
                    "x": x,
                    "y": y,
                    "bounds": (max(0, x - 10), max(0, y - 10), min(screen_size[0], x + 10), min(screen_size[1], y + 10)),
                    "confidence": conf
                }
        except Exception:
            pass
        return None

    async def describe_screen(
        self,
        screenshot_base64: str,
        focus_region: Optional[tuple[int, int, int, int]] = None
    ) -> str:
        query = "Describe the active window and main UI elements visible on screen in concise bullet points."
        return await self.analyze_screenshot(screenshot_base64, query)


# ─── Cloud Vision Implementation (Gemini / Anthropic / OpenAI) ─────────────────

class CloudComputerVisionProvider(ComputerVisionProvider):
    """
    Cloud-based multimodal provider using Gemini or OpenAI format.
    """

    def __init__(self, provider: Any = None, model_name: str = "gemini-2.0-flash"):
        self.provider = provider
        self.model_name = model_name

    async def analyze_screenshot(
        self,
        screenshot_base64: str,
        query: str,
        structured_context: Optional[str] = None
    ) -> str:
        full_query = query
        if structured_context:
            full_query = f"{query}\n\nAccessibility & UI Tree Context:\n{structured_context}"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": full_query},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{screenshot_base64}"}}
                ]
            }
        ]

        if self.provider and hasattr(self.provider, "generate_chat"):
            try:
                res = await self.provider.generate_chat(
                    model=self.model_name,
                    messages=messages,
                    stream=False
                )
                return str(res.get("response", "")).strip()
            except Exception as e:
                logger.error(f"Cloud vision analysis failed: {e}")
                return f"Cloud vision error: {e}"

        return f"[CloudVision {self.model_name}] Screen analyzed for query: {query}"

    async def locate_element(
        self,
        screenshot_base64: str,
        element_description: str,
        screen_size: tuple[int, int]
    ) -> Optional[Dict[str, Any]]:
        query = (
            f"Locate the UI element: '{element_description}'.\n"
            f"Return JSON only: {{\"x\": int, \"y\": int, \"confidence\": float}} "
            f"where x is in [0, {screen_size[0]}] and y is in [0, {screen_size[1]}]."
        )
        ans = await self.analyze_screenshot(screenshot_base64, query)
        try:
            m = re.search(r'\{[^{}]*"x"\s*:\s*\d+.*\}', ans, re.DOTALL)
            if m:
                data = json.loads(m.group(0))
                x = int(data.get("x", 0))
                y = int(data.get("y", 0))
                return {
                    "x": x,
                    "y": y,
                    "bounds": (max(0, x - 10), max(0, y - 10), min(screen_size[0], x + 10), min(screen_size[1], y + 10)),
                    "confidence": float(data.get("confidence", 0.8))
                }
        except Exception:
            pass
        return None

    async def describe_screen(
        self,
        screenshot_base64: str,
        focus_region: Optional[tuple[int, int, int, int]] = None
    ) -> str:
        return await self.analyze_screenshot(
            screenshot_base64,
            "Provide a concise summary of all visible windows, buttons, and open applications."
        )


# ─── Mock Vision Provider (for testing) ───────────────────────────────────────

class MockVisionProvider(ComputerVisionProvider):
    """
    Deterministic mock vision provider for tests.
    Allows registering preset locations and responses.
    """

    def __init__(self):
        self.preset_locations: Dict[str, Dict[str, Any]] = {
            "run": {"x": 500, "y": 300, "bounds": (480, 285, 520, 315), "confidence": 0.95},
            "test": {"x": 500, "y": 300, "bounds": (480, 285, 520, 315), "confidence": 0.95},
            "vs code": {"x": 100, "y": 50, "bounds": (80, 40, 120, 60), "confidence": 0.98},
            "terminal": {"x": 300, "y": 600, "bounds": (200, 500, 600, 700), "confidence": 0.92},
            "file": {"x": 50, "y": 20, "bounds": (30, 10, 70, 30), "confidence": 0.90},
        }
        self.analysis_responses: Dict[str, str] = {}
        self.call_history: List[Dict[str, Any]] = []

    def set_location(self, query: str, location: Dict[str, Any]):
        self.preset_locations[query.lower()] = location

    def set_response(self, query_substr: str, response: str):
        self.analysis_responses[query_substr.lower()] = response

    async def analyze_screenshot(
        self,
        screenshot_base64: str,
        query: str,
        structured_context: Optional[str] = None
    ) -> str:
        self.call_history.append({"method": "analyze", "query": query})
        q_lower = query.lower()
        for k, v in self.analysis_responses.items():
            if k in q_lower:
                return v
        return f"Mock analysis: screenshot analyzed successfully for '{query}'."

    async def locate_element(
        self,
        screenshot_base64: str,
        element_description: str,
        screen_size: tuple[int, int]
    ) -> Optional[Dict[str, Any]]:
        self.call_history.append({"method": "locate", "query": element_description})
        desc = element_description.lower()
        for key, loc in self.preset_locations.items():
            if key in desc:
                return loc
        return None

    async def describe_screen(
        self,
        screenshot_base64: str,
        focus_region: Optional[tuple[int, int, int, int]] = None
    ) -> str:
        self.call_history.append({"method": "describe"})
        return "Screen contains VS Code workspace and terminal showing test results."
