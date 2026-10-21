"""
HELIOS — Stateful Vision-Language-Action (VLA) Computer Control Framework (vla_engine.py)
Implements:
1. High-speed in-memory MSS frame capture with Lanczos downsampling to 1080p and base64 encoding.
2. Coordinate normalization (bounding-box centroiding, native scaling, OS DPI division).
3. 500ms visual settlement buffer.
4. Deadlock & infinite-loop detection (rolling window of 3 actions within +-5px radius).
5. Ollama local VLA model execution loop (Qwen-VL, UI-TARS, Moondream).
"""

from __future__ import annotations

import asyncio
import base64
import collections
from collections import deque
import dataclasses
from dataclasses import dataclass, field
from enum import Enum
import io
import json
import logging
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple, Union

from PIL import Image

# Import system audit module
try:
    from system_audit import (
        AuditReport,
        AuditSyncManager,
        DisplayMetrics,
        HostEnvironmentInspector,
        get_audit_manager,
    )
except ImportError:
    # If running from different CWD
    from ai_router.system_audit import (  # type: ignore
        AuditReport,
        AuditSyncManager,
        DisplayMetrics,
        HostEnvironmentInspector,
        get_audit_manager,
    )

logger = logging.getLogger("helios.vla.engine")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


# ─── Exceptions & Enums ───────────────────────────────────────────────────────

class DeadlockDetectedError(RuntimeError):
    """Raised when 3 consecutive actions target coordinates within a +-5px radius."""
    def __init__(self, message: str, action_history: List[Tuple[float, float, str]]):
        super().__init__(message)
        self.action_history = action_history


class ActionType(str, Enum):
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    MOVE = "move"
    DRAG = "drag"
    TYPE = "type"
    PRESS = "press"
    HOTKEY = "hotkey"
    SCROLL = "scroll"
    WAIT = "wait"
    DONE = "done"
    FAIL = "fail"


class LoopStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    DEADLOCK_DETECTED = "deadlock_detected"
    ERROR = "error"
    MANUAL_INTERVENTION_REQUIRED = "manual_intervention_required"


# ─── Frame Capture Contracts ──────────────────────────────────────────────────

@dataclass
class CapturedFrame:
    """Represents a screen capture downsampled in-memory for VLA inference."""
    original_width: int
    original_height: int
    downsampled_width: int
    downsampled_height: int
    scale_x: float                   # original_w / downsampled_w
    scale_y: float                   # original_h / downsampled_h
    base64_jpeg: str
    raw_pil_image: Image.Image
    capture_time_ms: float
    monitor_left: int
    monitor_top: int


@dataclass
class NormalizedCoordinate:
    """Stores coordinate resolution steps for total auditability."""
    raw_input: Any
    center_downsampled: Tuple[float, float]
    native_pixel: Tuple[float, float]
    os_dpi_divided: Tuple[int, int]
    dpi_scaling_factor: float


@dataclass
class VLAAction:
    action_type: ActionType
    target_coord: Optional[NormalizedCoordinate] = None
    drag_end_coord: Optional[NormalizedCoordinate] = None
    text: Optional[str] = None
    keys: Optional[List[str]] = None
    scroll_amount: Optional[int] = None
    thought: Optional[str] = None
    raw_response: Optional[str] = None


# ─── High-Speed In-Memory Frame Capturer ──────────────────────────────────────

class HighSpeedFrameCapturer:
    """
    Captures primary display directly into RAM via `mss`, performs
    high-quality Lanczos downsampling (max height 1080p), and encodes
    directly to Base64 without touching disk.
    """

    MAX_HEIGHT: int = 1080
    JPEG_QUALITY: int = 90

    def __init__(self, display_metrics: Optional[DisplayMetrics] = None):
        self.display_metrics = display_metrics
        self._sct_instance = None

    def _get_sct(self):
        import mss
        sct_cls = getattr(mss, "MSS", getattr(mss, "mss", None))
        return sct_cls()

    def capture_frame(self) -> CapturedFrame:
        """Captures primary display, downsamples with Lanczos to max 1080p, returns CapturedFrame."""
        t0 = time.perf_counter()

        # Determine monitor bounds
        left, top, orig_w, orig_h = 0, 0, 1920, 1080
        if self.display_metrics:
            left = self.display_metrics.primary_monitor.left
            top = self.display_metrics.primary_monitor.top
            orig_w = self.display_metrics.primary_monitor.width
            orig_h = self.display_metrics.primary_monitor.height

        orig_pil = None
        try:
            with self._get_sct() as sct:
                # Monitor 1 is typically primary, or use exact bounding dict
                bounds = {"left": left, "top": top, "width": orig_w, "height": orig_h}
                sct_img = sct.grab(bounds)
                orig_pil = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        except Exception as e:
            logger.warning("MSS screen grab failed (%s); trying fallback capture", e)
            try:
                from PIL import ImageGrab
                orig_pil = ImageGrab.grab(bbox=(left, top, left + orig_w, top + orig_h))
            except Exception:
                # Synthetic fallback for headless/service test environments
                orig_pil = Image.new("RGB", (orig_w, orig_h), color=(35, 35, 35))

        actual_w, actual_h = orig_pil.size

        # Downsample with Lanczos filtering to max height of 1080p
        if actual_h > self.MAX_HEIGHT:
            new_h = self.MAX_HEIGHT
            new_w = int(round(actual_w * (float(self.MAX_HEIGHT) / float(actual_h))))
            downsampled_pil = orig_pil.resize((new_w, new_h), resample=Image.Resampling.LANCZOS)
        else:
            new_w, new_h = actual_w, actual_h
            downsampled_pil = orig_pil

        scale_x = actual_w / float(new_w) if new_w > 0 else 1.0
        scale_y = actual_h / float(new_h) if new_h > 0 else 1.0

        # In-memory JPEG encoding to base64
        buf = io.BytesIO()
        downsampled_pil.save(buf, format="JPEG", quality=self.JPEG_QUALITY, optimize=True)
        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        return CapturedFrame(
            original_width=actual_w,
            original_height=actual_h,
            downsampled_width=new_w,
            downsampled_height=new_h,
            scale_x=scale_x,
            scale_y=scale_y,
            base64_jpeg=b64_str,
            raw_pil_image=downsampled_pil,
            capture_time_ms=elapsed_ms,
            monitor_left=left,
            monitor_top=top,
        )


# ─── Coordinate Normalizer ────────────────────────────────────────────────────

class CoordinateNormalizer:
    """
    Transforms predicted coordinates or bounding boxes from local VLA models:
    1. Parses box [x1, y1, x2, y2] or points [x, y]
    2. Calculates center point ((x1+x2)/2, (y1+y2)/2)
    3. Maps downsampled coordinates back to native display coordinates
    4. Divides by exact OS DPI scaling factor before dispatching inputs.
    """

    def __init__(self, dpi_scaling_factor: float = 1.0, primary_offset: Tuple[int, int] = (0, 0)):
        self.dpi_scaling_factor = max(0.25, float(dpi_scaling_factor))
        self.primary_left, self.primary_top = primary_offset

    def update_scaling_factor(self, factor: float):
        self.dpi_scaling_factor = max(0.25, float(factor))

    def update_offset(self, left: int, top: int):
        self.primary_left = left
        self.primary_top = top

    def normalize(
        self,
        raw_coords: Union[List[float], Tuple[float, ...], Dict[str, Any], str, NormalizedCoordinate],
        frame: CapturedFrame,
        is_thousand_scale: bool = False,
    ) -> NormalizedCoordinate:
        """
        Calculates center point, converts from downsampled space to native display,
        and divides by OS DPI scaling factor.
        """
        if isinstance(raw_coords, NormalizedCoordinate):
            return raw_coords

        cx_down, cy_down = self._extract_center_point(raw_coords, frame, is_thousand_scale=is_thousand_scale)

        # Step 2: Convert downsampled coordinates back to native display coordinates
        native_x = (cx_down * frame.scale_x) + frame.monitor_left
        native_y = (cy_down * frame.scale_y) + frame.monitor_top

        # Step 3: Divide by exact OS scaling factor retrieved from SYSTEM_AUDIT
        # PyAutoGUI on scaled Windows displays requires coordinates divided by the DPI scale
        final_x = int(round(native_x / self.dpi_scaling_factor))
        final_y = int(round(native_y / self.dpi_scaling_factor))

        return NormalizedCoordinate(
            raw_input=raw_coords,
            center_downsampled=(round(cx_down, 2), round(cy_down, 2)),
            native_pixel=(round(native_x, 2), round(native_y, 2)),
            os_dpi_divided=(final_x, final_y),
            dpi_scaling_factor=self.dpi_scaling_factor,
        )

    def _extract_center_point(
        self,
        raw_coords: Union[List[float], Tuple[float, ...], Dict[str, Any], str, NormalizedCoordinate],
        frame: CapturedFrame,
        is_thousand_scale: bool = False,
    ) -> Tuple[float, float]:
        """Extracts (center_x, center_y) in downsampled frame pixel space."""
        if isinstance(raw_coords, NormalizedCoordinate):
            return raw_coords.center_downsampled

        # Handle string inputs like "[100, 200, 300, 400]" or "point=[100, 200]"
        if isinstance(raw_coords, str):
            nums = [float(n) for n in re.findall(r"[-+]?\d*\.?\d+", raw_coords)]
            if not nums:
                raise ValueError(f"Could not parse numerical coordinates from string: {raw_coords}")
            raw_coords = nums

        # Handle Dict inputs
        if isinstance(raw_coords, dict):
            if "scale" in raw_coords and str(raw_coords["scale"]) == "1000":
                is_thousand_scale = True
            if "box" in raw_coords:
                raw_coords = raw_coords["box"]
            elif "bbox" in raw_coords:
                raw_coords = raw_coords["bbox"]
            elif "point" in raw_coords:
                raw_coords = raw_coords["point"]
            elif "x" in raw_coords and "y" in raw_coords:
                raw_coords = [raw_coords["x"], raw_coords["y"]]

        coords = list(raw_coords)

        # Case A: Bounding box [x1, y1, x2, y2]
        if len(coords) == 4:
            x1, y1, x2, y2 = float(coords[0]), float(coords[1]), float(coords[2]), float(coords[3])

            # Check if normalized [0, 1] (all numbers <= 1.0)
            if max(x1, y1, x2, y2) <= 1.0:
                x1 *= frame.downsampled_width
                x2 *= frame.downsampled_width
                y1 *= frame.downsampled_height
                y2 *= frame.downsampled_height
            # Explicit 1000-scale
            elif is_thousand_scale:
                x1 = (x1 / 1000.0) * frame.downsampled_width
                x2 = (x2 / 1000.0) * frame.downsampled_width
                y1 = (y1 / 1000.0) * frame.downsampled_height
                y2 = (y2 / 1000.0) * frame.downsampled_height

            center_x = (x1 + x2) / 2.0
            center_y = (y1 + y2) / 2.0
            return center_x, center_y

        # Case B: Point [x, y]
        elif len(coords) == 2:
            x, y = float(coords[0]), float(coords[1])
            # Check if normalized [0, 1]
            if max(x, y) <= 1.0:
                x *= frame.downsampled_width
                y *= frame.downsampled_height
            elif is_thousand_scale:
                x = (x / 1000.0) * frame.downsampled_width
                y = (y / 1000.0) * frame.downsampled_height
            return x, y

        else:
            raise ValueError(f"Invalid coordinate dimensions: expected 2 or 4 numbers, got {coords}")


# ─── Deadlock & Infinite-Loop Detector ────────────────────────────────────────

class DeadlockDetector:
    """
    Tracks a rolling window of the last three actions:
    [(x1, y1, action1), (x2, y2, action2), (x3, y3, action3)].
    If three consecutive actions target coordinates within a +-5px radius,
    breaks the loop immediately, flags an unhandled UI state, and prompts the user.
    """

    RADIUS_PX: float = 5.0

    def __init__(self, radius_px: float = 5.0):
        self.radius_px = radius_px
        self.action_history: deque[Tuple[float, float, str]] = deque(maxlen=3)

    def record_and_check(self, x: float, y: float, action_name: str) -> bool:
        """
        Records the candidate action and checks if the last 3 actions are all within +-5px.
        Returns:
            True if deadlock detected, False otherwise.
        """
        self.action_history.append((x, y, action_name))

        if len(self.action_history) == 3:
            # Check pairwise distance among all 3 points
            pts = list(self.action_history)
            p1, p2, p3 = pts[0], pts[1], pts[2]

            def within_radius(a: Tuple[float, float, str], b: Tuple[float, float, str]) -> bool:
                dx = abs(a[0] - b[0])
                dy = abs(a[1] - b[1])
                euclidean = math.hypot(dx, dy)
                # Adhere to +-5px radius check
                return dx <= self.radius_px and dy <= self.radius_px and euclidean <= (self.radius_px * math.sqrt(2))

            if within_radius(p1, p2) and within_radius(p2, p3) and within_radius(p1, p3):
                logger.error(
                    "DEADLOCK DETECTED! 3 consecutive actions within +-%.1fpx: %s",
                    self.radius_px,
                    [(round(p[0], 1), round(p[1], 1), p[2]) for p in pts]
                )
                return True

        return False

    def clear(self):
        self.action_history.clear()


# ─── Local VLA Ollama Client ──────────────────────────────────────────────────

class LocalVLAOllamaClient:
    """Sends encoded frames and goals to local Ollama vision models (e.g. Qwen3-VL, UI-TARS)."""

    SYSTEM_PROMPT = """You are a precise Computer Control Vision-Language-Action (VLA) agent.
Analyze the user's goal and the current screen image.
Output your reasoning and exact next action in JSON format:
{
  "thought": "brief description of what is seen and the next action",
  "action": "click" | "double_click" | "right_click" | "type" | "press" | "scroll" | "wait" | "done",
  "box": [x1, y1, x2, y2],       // bounding box of UI target if clicking (either pixel coords or [0-1000])
  "point": [x, y],               // or single point [x, y]
  "text": "text to type",        // if action is type
  "keys": ["enter"],             // if action is press
  "scroll_amount": -300          // if action is scroll (negative down, positive up)
}
Return ONLY valid JSON. If the task is finished, return action: "done"."""

    def __init__(self, model_name: str, ollama_url: str = "http://localhost:11434", timeout_seconds: float = 120.0):
        self.model_name = model_name
        self.ollama_url = ollama_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def predict_action(self, goal: str, frame: CapturedFrame) -> VLAAction:
        """Calls local Ollama model with image and parses action response."""
        url = f"{self.ollama_url}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Task Goal: {goal}\nScreen Resolution: {frame.downsampled_width}x{frame.downsampled_height}.",
                    "images": [frame.base64_jpeg]
                }
            ],
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 512
            }
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            # Run blocking urllib request in asyncio thread
            loop = asyncio.get_running_loop()
            resp_data = await loop.run_in_executor(None, self._send_request, req)
            raw_text = resp_data.get("message", {}).get("content", "").strip()
            return self._parse_model_output(raw_text)
        except Exception as e:
            logger.error("VLA Model inference error: %s", e)
            return VLAAction(
                action_type=ActionType.FAIL,
                thought=f"Ollama API request error: {e}",
                raw_response=str(e)
            )

    def _send_request(self, req: urllib.request.Request) -> Dict[str, Any]:
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _parse_model_output(self, raw_text: str) -> VLAAction:
        """Parses model response into VLAAction, supporting JSON and UI-TARS syntax."""
        # Try JSON extraction
        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                act_str = data.get("action", "click").lower()
                coord = data.get("box") or data.get("point")
                return VLAAction(
                    action_type=ActionType(act_str) if act_str in ActionType._value2member_map_ else ActionType.CLICK,
                    target_coord=coord,  # Will be normalized by CoordinateNormalizer
                    text=data.get("text"),
                    keys=data.get("keys"),
                    scroll_amount=data.get("scroll_amount"),
                    thought=data.get("thought", ""),
                    raw_response=raw_text,
                )
            except Exception:
                pass

        # Try UI-TARS action syntax: Action: click(point='[x, y]') or click(start_box='[y1,x1,y2,x2]')
        click_match = re.search(r"(click|double_click|right_click)\s*\((.*?)\)", raw_text, re.IGNORECASE)
        if click_match:
            act_type = click_match.group(1).lower()
            inner = click_match.group(2)
            coords = [float(n) for n in re.findall(r"[-+]?\d*\.?\d+", inner)]
            return VLAAction(
                action_type=ActionType(act_type),
                target_coord=coords if coords else None,
                thought="Parsed UI-TARS style command",
                raw_response=raw_text
            )

        if "done" in raw_text.lower():
            return VLAAction(action_type=ActionType.DONE, thought="Task finished", raw_response=raw_text)

        return VLAAction(
            action_type=ActionType.WAIT,
            thought=f"Unrecognized response: {raw_text[:100]}",
            raw_response=raw_text
        )


# ─── Input Dispatcher (PyAutoGUI / Safe Mock) ────────────────────────────────

class InputDispatcher:
    """Dispatches physical inputs via PyAutoGUI with dry-run/mock testing mode."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    async def execute_action(self, action: VLAAction) -> bool:
        """Executes the action physically or simulates in dry-run mode."""
        if self.dry_run:
            logger.info("[DRY-RUN] Executing %s -> coord: %s", action.action_type, getattr(action.target_coord, "os_dpi_divided", None))
            return True

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_execute, action)

    def _sync_execute(self, action: VLAAction) -> bool:
        import pyautogui

        # Failsafe settings
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.05

        target = action.target_coord.os_dpi_divided if action.target_coord else None

        if action.action_type == ActionType.CLICK and target:
            pyautogui.click(target[0], target[1])
        elif action.action_type == ActionType.DOUBLE_CLICK and target:
            pyautogui.doubleClick(target[0], target[1])
        elif action.action_type == ActionType.RIGHT_CLICK and target:
            pyautogui.rightClick(target[0], target[1])
        elif action.action_type == ActionType.MOVE and target:
            pyautogui.moveTo(target[0], target[1])
        elif action.action_type == ActionType.DRAG and target:
            drag_end = action.drag_end_coord.os_dpi_divided if action.drag_end_coord else target
            pyautogui.moveTo(target[0], target[1])
            pyautogui.dragTo(drag_end[0], drag_end[1], duration=0.4)
        elif action.action_type == ActionType.TYPE and action.text:
            pyautogui.write(action.text, interval=0.02)
        elif action.action_type == ActionType.PRESS and action.keys:
            for k in action.keys:
                pyautogui.press(k)
        elif action.action_type == ActionType.SCROLL and action.scroll_amount:
            pyautogui.scroll(action.scroll_amount)
        elif action.action_type in (ActionType.WAIT, ActionType.DONE):
            pass
        return True


# ─── Stateful VLA Execution Loop ──────────────────────────────────────────────

class StatefulVLAExecutionLoop:
    """
    Modular, autonomous VLA computer control framework.
    Coordinates audit synchronization, frame capture, coordinate normalization,
    deadlock detection, visual settlement buffer, and model loop execution.
    """

    SETTLEMENT_DELAY_SECONDS: float = 0.500  # 500ms Visual Settlement Buffer

    def __init__(
        self,
        audit_file_path: Optional[Path] = None,
        model_name: Optional[str] = None,
        dry_run: bool = False,
        intervention_callback: Optional[Callable[[str, List[Tuple[float, float, str]]], Coroutine[Any, Any, None]]] = None,
    ):
        self.audit_manager = get_audit_manager(audit_file_path=audit_file_path)
        self.dry_run = dry_run
        self.intervention_callback = intervention_callback

        # Initial audit sync
        drift_detected, self.audit_report = self.audit_manager.check_and_sync()

        # Extract verified parameters from SYSTEM_AUDIT
        self.display_metrics = self.audit_report.display
        self.dpi_scaling = self.audit_report.display.dpi_scaling_factor

        # Select model
        selected_model = (
            model_name
            or self.audit_report.runtime.recommended_vla_model
            or "qwen3-vl:8b"
        )
        self.model_name = selected_model

        # Components
        self.frame_capturer = HighSpeedFrameCapturer(display_metrics=self.display_metrics)
        self.coord_normalizer = CoordinateNormalizer(
            dpi_scaling_factor=self.dpi_scaling,
            primary_offset=(self.display_metrics.primary_monitor.left, self.display_metrics.primary_monitor.top)
        )
        self.deadlock_detector = DeadlockDetector(radius_px=5.0)
        self.model_client = LocalVLAOllamaClient(
            model_name=self.model_name,
            ollama_url=self.audit_report.runtime.ollama_endpoint
        )
        self.dispatcher = InputDispatcher(dry_run=dry_run)

        logger.info(
            "StatefulVLAExecutionLoop initialized: Model=%s, Resolution=%dx%d, DPI Scale=%.2fx, DryRun=%s",
            self.model_name,
            self.display_metrics.physical_resolution[0],
            self.display_metrics.physical_resolution[1],
            self.dpi_scaling,
            self.dry_run
        )

    def refresh_environment(self) -> bool:
        """Non-blocking drift check: refreshes in-memory scaling factors if environment changed."""
        drift, report = self.audit_manager.check_and_sync()
        if drift:
            self.audit_report = report
            self.display_metrics = report.display
            self.dpi_scaling = report.display.dpi_scaling_factor
            self.coord_normalizer.update_scaling_factor(self.dpi_scaling)
            self.coord_normalizer.update_offset(
                report.display.primary_monitor.left,
                report.display.primary_monitor.top
            )
            self.frame_capturer.display_metrics = report.display
            logger.info("Environment refreshed: new scaling factor %.2fx", self.dpi_scaling)
        return drift

    async def execute_single_step(self, goal: str) -> Tuple[VLAAction, LoopStatus]:
        """
        Executes one full iteration:
        1. Capture frame (MSS + Lanczos 1080p + base64)
        2. Query local VLA model
        3. Parse & normalize coordinates (center point, native scale, DPI division)
        4. Deadlock detection (+-5px radius across 3 actions)
        5. Physical input dispatch
        6. Visual settlement buffer (500ms delay)
        """
        # Step 0: Ensure parameters are synchronized
        self.refresh_environment()

        # Step 1: High-Speed Frame Capture
        frame = self.frame_capturer.capture_frame()
        logger.debug("Captured frame in %.1fms (%dx%d)", frame.capture_time_ms, frame.downsampled_width, frame.downsampled_height)

        # Step 2: Query Local VLA Model
        action = await self.model_client.predict_action(goal=goal, frame=frame)
        action = dataclasses.replace(action)
        logger.info("VLA Predicted Action: %s (Thought: %s)", action.action_type, action.thought)

        if action.action_type == ActionType.DONE:
            return action, LoopStatus.COMPLETED

        if action.action_type == ActionType.FAIL:
            return action, LoopStatus.ERROR

        # Step 3: Coordinate Normalization
        if action.target_coord is not None:
            normalized = self.coord_normalizer.normalize(action.target_coord, frame)
            action.target_coord = normalized
            target_pt = normalized.os_dpi_divided

            # Step 4: Deadlock & Infinite-Loop Detection
            is_deadlock = self.deadlock_detector.record_and_check(
                x=float(target_pt[0]),
                y=float(target_pt[1]),
                action_name=action.action_type.value
            )

            if is_deadlock:
                msg = f"Deadlock: 3 consecutive actions within +-5px at ({target_pt[0]}, {target_pt[1]}). Breaking loop."
                logger.error(msg)

                # Prompt user for manual intervention
                if self.intervention_callback:
                    await self.intervention_callback(msg, list(self.deadlock_detector.action_history))

                return action, LoopStatus.DEADLOCK_DETECTED
        else:
            # Action without target coordinates (e.g. key press or text type)
            if action.action_type in (ActionType.TYPE, ActionType.PRESS, ActionType.WAIT):
                self.deadlock_detector.clear()

        # Step 5: Input Dispatch
        await self.dispatcher.execute_action(action)

        # Step 6: Visual Settlement Buffer (500ms post-action delay)
        logger.debug("Entering 500ms Visual Settlement Buffer...")
        await asyncio.sleep(self.SETTLEMENT_DELAY_SECONDS)

        return action, LoopStatus.RUNNING

    async def run_loop(self, goal: str, max_steps: int = 15) -> LoopStatus:
        """Runs the continuous VLA loop until goal completion, max steps, or deadlock."""
        logger.info("Starting VLA Loop for goal: '%s' (Max Steps: %d)", goal, max_steps)
        self.deadlock_detector.clear()

        for step in range(1, max_steps + 1):
            logger.info("--- Step %d/%d ---", step, max_steps)
            action, status = await self.execute_single_step(goal=goal)

            if status == LoopStatus.COMPLETED:
                logger.info("Goal reached successfully in %d steps!", step)
                return LoopStatus.COMPLETED

            if status == LoopStatus.DEADLOCK_DETECTED:
                logger.error("VLA Loop terminated: DEADLOCK_DETECTED at step %d", step)
                return LoopStatus.DEADLOCK_DETECTED

            if status == LoopStatus.ERROR:
                logger.error("VLA Loop terminated with ERROR at step %d", step)
                return LoopStatus.ERROR

        logger.warning("Reached max steps (%d) without explicit completion.", max_steps)
        return LoopStatus.RUNNING


# ─── CLI Entry Point ──────────────────────────────────────────────────────────

async def _manual_intervention_prompt(message: str, history: List[Tuple[float, float, str]]):
    print("\n" + "!" * 70)
    print(f"[!] MANUAL INTERVENTION REQUIRED: {message}")
    print(f"[!] Action history causing deadlock: {history}")
    print("!" * 70 + "\n")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="HELIOS Stateful VLA Computer Control Engine")
    parser.add_argument("--goal", "-g", default="Inspect screen and verify UI state", help="Goal prompt for the VLA model")
    parser.add_argument("--model", "-m", default=None, help="Ollama vision model to use")
    parser.add_argument("--max-steps", "-s", type=int, default=5, help="Maximum execution steps")
    parser.add_argument("--dry-run", "-d", action="store_true", help="Simulate input actions without moving real cursor")
    args = parser.parse_args()

    loop = StatefulVLAExecutionLoop(
        model_name=args.model,
        dry_run=args.dry_run,
        intervention_callback=_manual_intervention_prompt
    )

    status = await loop.run_loop(goal=args.goal, max_steps=args.max_steps)
    print(f"Final Loop Status: {status.value}")


if __name__ == "__main__":
    asyncio.run(main())
