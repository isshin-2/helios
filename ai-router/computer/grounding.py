"""
HELIOS — UI Grounding Subsystem
Resolves semantic target instructions ("Click Run", "Open terminal") into precise coordinates.
Follows strict priority:
1. Native Accessibility / Windows UI Automation (UIA)
2. Application / UI Tree
3. OCR / Text Detection
4. Vision-based Grounding
5. Fallback Coordinate / Grid Grounding
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from computer.screenshot import ScreenshotData
from computer.vision import ComputerVisionProvider

logger = logging.getLogger("helios.computer.grounding")


# ─── Data Structures ─────────────────────────────────────────────────────────

@dataclass
class UIElement:
    """
    Structured representation of a detected, grounded UI element.
    """
    role: str                       # e.g., 'Button', 'MenuItem', 'Edit', 'Text'
    name: str                       # Element label, text, or accessibility name
    bounds: Tuple[int, int, int, int]  # (left, top, right, bottom) in screen coordinates
    confidence: float               # Confidence score in [0.0, 1.0]
    source: str                     # 'uia', 'tree', 'ocr', 'vision', 'fallback'
    element_id: Optional[int] = None
    is_enabled: bool = True
    is_visible: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def centroid(self) -> Tuple[int, int]:
        """Center coordinate (cx, cy) suitable for clicks."""
        left, top, right, bottom = self.bounds
        return ((left + right) // 2, (top + bottom) // 2)

    @property
    def width(self) -> int:
        return self.bounds[2] - self.bounds[0]

    @property
    def height(self) -> int:
        return self.bounds[3] - self.bounds[1]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "name": self.name,
            "bounds": list(self.bounds),
            "centroid": list(self.centroid),
            "confidence": self.confidence,
            "source": self.source,
            "element_id": self.element_id,
            "is_enabled": self.is_enabled,
            "is_visible": self.is_visible,
        }


# ─── UI Grounding Engine ─────────────────────────────────────────────────────

class UIGroundingEngine:
    """
    Resolves target queries to UI elements using the multi-tier priority grounding pipeline.
    """

    def __init__(
        self,
        vision_provider: Optional[ComputerVisionProvider] = None,
        use_uia: bool = True,
    ):
        self.vision_provider = vision_provider
        self.use_uia = use_uia
        self._mock_elements: List[UIElement] = []

    def set_mock_elements(self, elements: List[UIElement]):
        """For unit tests: inject deterministic mock UI elements."""
        self._mock_elements = elements

    async def ground_query(
        self,
        query: str,
        screenshot: ScreenshotData,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[UIElement]:
        """
        Execute the 5-stage priority grounding pipeline.
        Returns the highest-priority, highest-confidence matching UIElement.
        """
        clean_q = str(query).strip().lower()

        # Check mock elements if provided (test environment)
        if self._mock_elements:
            for el in self._mock_elements:
                if clean_q in el.name.lower() or el.name.lower() in clean_q:
                    return el

        # Stage 1: Native Windows Accessibility / UI Automation (UIA)
        if self.use_uia:
            uia_el = await self._ground_via_uia(clean_q)
            if uia_el and uia_el.confidence >= 0.8:
                logger.info(f"Grounding resolved '{query}' via UIA: {uia_el.name} at {uia_el.centroid}")
                return uia_el

        # Stage 2: Application / UI Tree Traversal
        tree_el = await self._ground_via_ui_tree(clean_q)
        if tree_el and tree_el.confidence >= 0.75:
            logger.info(f"Grounding resolved '{query}' via UI Tree: {tree_el.name} at {tree_el.centroid}")
            return tree_el

        # Stage 3: OCR / Text Detection
        ocr_el = await self._ground_via_ocr(clean_q, screenshot)
        if ocr_el and ocr_el.confidence >= 0.7:
            logger.info(f"Grounding resolved '{query}' via OCR: {ocr_el.name} at {ocr_el.centroid}")
            return ocr_el

        # Stage 4: Vision-based Grounding (VLM)
        if self.vision_provider:
            vision_el = await self._ground_via_vision(clean_q, screenshot)
            if vision_el:
                logger.info(f"Grounding resolved '{query}' via Vision: at {vision_el.centroid}")
                return vision_el

        # Stage 5: Coordinate-based fallback
        fallback_el = self._ground_fallback(clean_q, screenshot)
        if fallback_el:
            logger.info(f"Grounding resolved '{query}' via Fallback at {fallback_el.centroid}")
            return fallback_el

        return None

    # ── Stage 1: Windows UI Automation ───────────────────────────────────────

    def _sync_uia_search(self, query: str) -> Optional[UIElement]:
        """Search the active window using pywinauto UIA tree."""
        try:
            import pywinauto
            from tools.desktop_utils import ensure_desktop_access
            ensure_desktop_access()

            desktop = pywinauto.Desktop(backend="uia")
            windows = desktop.windows()
            if not windows:
                return None

            active_win = windows[0]
            words = set(query.split())

            # Find matching controls
            for ctrl in active_win.descendants():
                try:
                    info = ctrl.element_info
                    name = (info.name or "").strip()
                    if not name:
                        continue
                    
                    name_lower = name.lower()
                    if query in name_lower or any(w in name_lower for w in words if len(w) > 2):
                        rect = ctrl.rectangle()
                        width = rect.width()
                        height = rect.height()
                        if 10 <= width <= 4000 and 10 <= height <= 4000:
                            is_vis = ctrl.is_visible()
                            is_en = ctrl.is_enabled()
                            if is_vis and is_en:
                                score = 0.95 if query == name_lower else 0.85
                                return UIElement(
                                    role=info.control_type or "Control",
                                    name=name,
                                    bounds=(rect.left, rect.top, rect.right, rect.bottom),
                                    confidence=score,
                                    source="uia",
                                    is_enabled=is_en,
                                    is_visible=is_vis,
                                )
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"UIA grounding search notice: {e}")
        return None

    async def _ground_via_uia(self, query: str) -> Optional[UIElement]:
        return await asyncio.to_thread(self._sync_uia_search, query)

    # ── Stage 2: UI Tree Traversal ───────────────────────────────────────────

    async def _ground_via_ui_tree(self, query: str) -> Optional[UIElement]:
        """Inspect cached or active UI tree elements (e.g. from SoM tools)."""
        try:
            from tools.som_overlay import get_ui_elements
            elements = await asyncio.to_thread(get_ui_elements)
            for el in elements:
                name_lower = el.name.lower()
                if query in name_lower or (name_lower and name_lower in query):
                    return UIElement(
                        role=el.control_type,
                        name=el.name,
                        bounds=el.rect,
                        confidence=0.80,
                        source="tree",
                        element_id=el.id,
                        is_enabled=el.is_enabled,
                        is_visible=el.is_visible,
                    )
        except Exception as e:
            logger.debug(f"UI Tree search notice: {e}")
        return None

    # ── Stage 3: OCR / Text Detection ────────────────────────────────────────

    async def _ground_via_ocr(self, query: str, screenshot: ScreenshotData) -> Optional[UIElement]:
        """Attempt text location via OCR if an OCR engine is available."""
        # Try rapidocr or pytesseract if installed
        try:
            import pytesseract
            pil_img = screenshot.to_pil_image()
            data = await asyncio.to_thread(pytesseract.image_to_data, pil_img, output_type=pytesseract.Output.DICT)
            for i, text in enumerate(data.get("text", [])):
                t_clean = text.strip().lower()
                if query in t_clean or (t_clean and t_clean in query):
                    x = data["left"][i]
                    y = data["top"][i]
                    w = data["width"][i]
                    h = data["height"][i]
                    return UIElement(
                        role="Text",
                        name=text,
                        bounds=(x, y, x + w, y + h),
                        confidence=0.75,
                        source="ocr"
                    )
        except Exception:
            pass
        return None

    # ── Stage 4: Vision-based Grounding ──────────────────────────────────────

    async def _ground_via_vision(self, query: str, screenshot: ScreenshotData) -> Optional[UIElement]:
        """Use VLM visual grounding to locate target coordinates."""
        if not self.vision_provider:
            return None

        screen_size = (screenshot.width, screenshot.height)
        result = await self.vision_provider.locate_element(
            screenshot_base64=screenshot.base64_str,
            element_description=query,
            screen_size=screen_size
        )
        if result and "x" in result and "y" in result:
            x = int(result["x"])
            y = int(result["y"])
            bounds = result.get("bounds", (max(0, x - 15), max(0, y - 15), x + 15, y + 15))
            return UIElement(
                role="VisualTarget",
                name=query,
                bounds=bounds,
                confidence=float(result.get("confidence", 0.70)),
                source="vision"
            )
        return None

    # ── Stage 5: Fallback Coordinate Grounding ───────────────────────────────

    def _ground_fallback(self, query: str, screenshot: ScreenshotData) -> Optional[UIElement]:
        """
        Deterministic fallback: check for grid coordinates (e.g. 'A1', 'B2', 'center')
        or specific coordinate specifications.
        """
        w, h = screenshot.width, screenshot.height

        # Named screen zones
        named_zones = {
            "center": (w // 2, h // 2),
            "top_left": (w // 4, h // 4),
            "top_right": (3 * w // 4, h // 4),
            "bottom_left": (w // 4, 3 * h // 4),
            "bottom_right": (3 * w // 4, 3 * h // 4),
        }
        for name, pt in named_zones.items():
            if name in query.replace("-", "_"):
                cx, cy = pt
                return UIElement(
                    role="Zone",
                    name=name,
                    bounds=(cx - 20, cy - 20, cx + 20, cy + 20),
                    confidence=0.50,
                    source="fallback"
                )

        # Coordinate matching like (x=800, y=400)
        m = re.search(r'x\s*=\s*(\d+).*y\s*=\s*(\d+)', query)
        if m:
            x, y = int(m.group(1)), int(m.group(2))
            return UIElement(
                role="Coordinate",
                name=f"Point({x},{y})",
                bounds=(x - 5, y - 5, x + 5, y + 5),
                confidence=0.60,
                source="fallback"
            )

        return None
