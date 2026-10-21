"""
HELIOS — Screenshot Subsystem
Multi-monitor capture, resolution scaling, compression, caching, and pluggable backends.
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

logger = logging.getLogger("helios.computer.screenshot")


# ─── Data Structures ─────────────────────────────────────────────────────────

@dataclass
class MonitorInfo:
    monitor_id: int
    left: int
    top: int
    width: int
    height: int
    is_primary: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "monitor_id": self.monitor_id,
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
            "is_primary": self.is_primary,
        }


@dataclass
class ScreenshotData:
    image_bytes: bytes
    format: str  # "jpeg" | "png"
    width: int
    height: int
    original_width: int
    original_height: int
    monitor_id: int
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    monitor_info: Optional[MonitorInfo] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def base64_str(self) -> str:
        return base64.b64encode(self.image_bytes).decode("utf-8")

    @property
    def data_url(self) -> str:
        mime = "image/jpeg" if self.format.lower() in ("jpeg", "jpg") else "image/png"
        return f"data:{mime};base64,{self.base64_str}"

    def to_pil_image(self) -> Image.Image:
        return Image.open(io.BytesIO(self.image_bytes))


# ─── Screenshot Backend Interface ────────────────────────────────────────────

class BaseScreenshotBackend(ABC):
    @abstractmethod
    async def list_monitors(self) -> List[MonitorInfo]:
        """List all available monitors and their bounds."""
        ...

    @abstractmethod
    async def capture(
        self,
        monitor_id: Optional[int] = None,
        max_dimension: int = 1280,
        image_format: str = "jpeg",
        quality: int = 80,
    ) -> ScreenshotData:
        """Capture desktop screenshot."""
        ...


# ─── Windows Implementation ──────────────────────────────────────────────────

class WindowsScreenshotBackend(BaseScreenshotBackend):
    """
    Production Windows screenshot backend.
    Prefers `mss` for high-speed multi-monitor GDI capture, falls back to `PIL.ImageGrab`.
    Executes in a thread to never block the asyncio loop.
    """

    def __init__(self):
        self._ensure_access()

    def _ensure_access(self):
        try:
            from tools.desktop_utils import ensure_desktop_access
            ensure_desktop_access()
        except Exception as e:
            logger.debug(f"Desktop access setup notice: {e}")

    def _sync_list_monitors(self) -> List[MonitorInfo]:
        self._ensure_access()
        monitors: List[MonitorInfo] = []
        try:
            import mss
            with mss.MSS() as sct:
                # mss.monitors[0] is the virtual union of all monitors
                # mss.monitors[1..n] are individual monitors
                for idx, m in enumerate(sct.monitors[1:], start=1):
                    monitors.append(MonitorInfo(
                        monitor_id=idx,
                        left=m["left"],
                        top=m["top"],
                        width=m["width"],
                        height=m["height"],
                        is_primary=(idx == 1)
                    ))
        except Exception as e:
            logger.debug(f"mss monitor listing failed ({e}), using fallback")
            try:
                from PIL import ImageGrab
                img = ImageGrab.grab()
                w, h = img.size
                monitors.append(MonitorInfo(
                    monitor_id=1, left=0, top=0, width=w, height=h, is_primary=True
                ))
            except Exception:
                monitors.append(MonitorInfo(
                    monitor_id=1, left=0, top=0, width=1920, height=1080, is_primary=True
                ))
        return monitors

    async def list_monitors(self) -> List[MonitorInfo]:
        return await asyncio.to_thread(self._sync_list_monitors)

    def _sync_capture(
        self,
        monitor_id: Optional[int] = None,
        max_dimension: int = 1280,
        image_format: str = "jpeg",
        quality: int = 80,
    ) -> ScreenshotData:
        self._ensure_access()
        target_mon = monitor_id or 1
        raw_img: Optional[Image.Image] = None
        mon_info: Optional[MonitorInfo] = None

        try:
            import mss
            with mss.MSS() as sct:
                # Validate monitor_id
                mon_idx = target_mon if 1 <= target_mon < len(sct.monitors) else 1
                m = sct.monitors[mon_idx]
                sct_img = sct.grab(m)
                raw_img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                mon_info = MonitorInfo(
                    monitor_id=mon_idx,
                    left=m["left"],
                    top=m["top"],
                    width=m["width"],
                    height=m["height"],
                    is_primary=(mon_idx == 1)
                )
        except Exception as e:
            logger.debug(f"mss grab failed ({e}), falling back to PIL.ImageGrab")
            try:
                from PIL import ImageGrab
                raw_img = ImageGrab.grab()
                w, h = raw_img.size
                mon_info = MonitorInfo(
                    monitor_id=1, left=0, top=0, width=w, height=h, is_primary=True
                )
            except Exception as e_pil:
                raise RuntimeError(f"All screen capture methods failed: {e_pil}") from e_pil

        if raw_img is None:
            raise RuntimeError("Screen capture produced an empty frame.")

        orig_w, orig_h = raw_img.size

        # Downscale proportionally if larger than max_dimension
        if orig_w > max_dimension or orig_h > max_dimension:
            raw_img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

        cur_w, cur_h = raw_img.size

        # Encode to requested format
        buffered = io.BytesIO()
        fmt = "JPEG" if image_format.lower() in ("jpeg", "jpg") else "PNG"
        if fmt == "JPEG":
            raw_img.convert("RGB").save(buffered, format="JPEG", quality=quality, optimize=True)
        else:
            raw_img.save(buffered, format="PNG", optimize=True)

        return ScreenshotData(
            image_bytes=buffered.getvalue(),
            format=fmt.lower(),
            width=cur_w,
            height=cur_h,
            original_width=orig_w,
            original_height=orig_h,
            monitor_id=target_mon,
            monitor_info=mon_info,
            metadata={
                "max_dimension": max_dimension,
                "scale_factor_x": cur_w / orig_w if orig_w else 1.0,
                "scale_factor_y": cur_h / orig_h if orig_h else 1.0,
            }
        )

    async def capture(
        self,
        monitor_id: Optional[int] = None,
        max_dimension: int = 1280,
        image_format: str = "jpeg",
        quality: int = 80,
    ) -> ScreenshotData:
        return await asyncio.to_thread(
            self._sync_capture, monitor_id, max_dimension, image_format, quality
        )


# ─── Mock Implementation (for testing & headless environments) ───────────────

class MockScreenshotBackend(BaseScreenshotBackend):
    """
    Deterministic mock backend for tests and CI environments without a physical display.
    """

    def __init__(self, width: int = 1920, height: int = 1080):
        self.width = width
        self.height = height
        self.monitors = [
            MonitorInfo(monitor_id=1, left=0, top=0, width=width, height=height, is_primary=True),
            MonitorInfo(monitor_id=2, left=width, top=0, width=1920, height=1080, is_primary=False),
        ]
        self._custom_elements: List[Dict[str, Any]] = []

    def set_screen_elements(self, elements: List[Dict[str, Any]]):
        """Set simulated elements on screen for OCR / visual verification."""
        self._custom_elements = elements

    async def list_monitors(self) -> List[MonitorInfo]:
        return self.monitors

    async def capture(
        self,
        monitor_id: Optional[int] = None,
        max_dimension: int = 1280,
        image_format: str = "jpeg",
        quality: int = 80,
    ) -> ScreenshotData:
        target_mon = monitor_id or 1
        # Create synthetic image with gradient and test markers
        img = Image.new("RGB", (self.width, self.height), color=(30, 30, 45))
        
        buffered = io.BytesIO()
        fmt = "JPEG" if image_format.lower() in ("jpeg", "jpg") else "PNG"
        img.save(buffered, format=fmt)

        mon_info = next((m for m in self.monitors if m.monitor_id == target_mon), self.monitors[0])

        return ScreenshotData(
            image_bytes=buffered.getvalue(),
            format=fmt.lower(),
            width=self.width,
            height=self.height,
            original_width=self.width,
            original_height=self.height,
            monitor_id=target_mon,
            monitor_info=mon_info,
            metadata={"mock": True, "elements": self._custom_elements}
        )


# ─── Screenshot Manager ──────────────────────────────────────────────────────

class ScreenshotManager:
    """
    High-level screenshot manager with short TTL caching to avoid spamming
    unnecessary frame grabs within the same second of execution.
    """

    def __init__(self, backend: Optional[BaseScreenshotBackend] = None, cache_ttl_seconds: float = 0.4):
        self.backend = backend or WindowsScreenshotBackend()
        self.cache_ttl = cache_ttl_seconds
        self._last_capture: Optional[ScreenshotData] = None
        self._last_capture_time: float = 0.0

    async def capture_screen(
        self,
        monitor_id: Optional[int] = None,
        force_fresh: bool = False,
        max_dimension: int = 1280,
        image_format: str = "jpeg",
        quality: int = 80,
    ) -> ScreenshotData:
        now = time.monotonic()
        if (
            not force_fresh
            and self._last_capture is not None
            and (now - self._last_capture_time) < self.cache_ttl
            and (monitor_id is None or self._last_capture.monitor_id == monitor_id)
        ):
            return self._last_capture

        # Check if remote sidecar capture is active in server mode
        try:
            import os
            from core.sidecar_manager import sidecar_manager
            if os.environ.get("DEPLOYMENT_MODE") == "server" and sidecar_manager.has_active_sidecars():
                res = await sidecar_manager.execute_on_sidecar("capture_screen", {
                    "max_dimension": max_dimension,
                    "image_format": image_format,
                    "quality": quality,
                }, timeout=10)
                if res and res.get("success"):
                    b64_str = res.get("image_base64", "")
                    raw_bytes = base64.b64decode(b64_str)
                    w = res.get("width", 1280)
                    h = res.get("height", 720)
                    shot = ScreenshotData(
                        image_bytes=raw_bytes,
                        format=res.get("format", image_format).lower(),
                        width=w,
                        height=h,
                        original_width=res.get("original_width", w),
                        original_height=res.get("original_height", h),
                        monitor_id=1,
                        metadata={"source": "remote_sidecar"}
                    )
                    self._last_capture = shot
                    self._last_capture_time = now
                    return shot
        except Exception as e_sidecar:
            logger.debug(f"Sidecar screenshot attempt skipped: {e_sidecar}")

        shot = await self.backend.capture(
            monitor_id=monitor_id,
            max_dimension=max_dimension,
            image_format=image_format,
            quality=quality,
        )
        self._last_capture = shot
        self._last_capture_time = now
        return shot

    async def get_monitors(self) -> List[MonitorInfo]:
        return await self.backend.list_monitors()

    def invalidate_cache(self) -> None:
        self._last_capture = None
        self._last_capture_time = 0.0
