"""
HELIOS — Computer Actions
Typed action specifications, risk levels, coordinate validation, and execution results.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger("helios.computer.actions")


# ─── Action Types ────────────────────────────────────────────────────────────

class ComputerActionType(str, Enum):
    SCREENSHOT = "screenshot"
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    MOVE = "move"
    DRAG = "drag"
    SCROLL = "scroll"
    TYPE = "type"
    PRESS = "press"
    HOTKEY = "hotkey"
    WAIT = "wait"
    FOCUS_WINDOW = "focus_window"
    LAUNCH_APPLICATION = "launch_application"
    CLOSE_WINDOW = "close_window"
    STOP = "stop"


# ─── Risk Levels ─────────────────────────────────────────────────────────────

class ActionRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ─── Computer Action Model ───────────────────────────────────────────────────

class ComputerAction(BaseModel):
    """
    Specification for a single computer operation.
    No blind multi-action sequences allowed; exactly one action is executed and verified at a time.
    """
    action_type: ComputerActionType = Field(
        default=ComputerActionType.CLICK,
        description="The specific action to perform."
    )
    
    # Target Coordinates
    x: Optional[int] = Field(default=None, description="Target X screen coordinate.")
    y: Optional[int] = Field(default=None, description="Target Y screen coordinate.")
    
    # Drag Coordinates
    start_x: Optional[int] = Field(default=None, description="Drag start X coordinate.")
    start_y: Optional[int] = Field(default=None, description="Drag start Y coordinate.")
    end_x: Optional[int] = Field(default=None, description="Drag end X coordinate.")

    end_y: Optional[int] = Field(default=None, description="Drag end Y coordinate.")
    
    # Text and Keystrokes
    text: Optional[str] = Field(default=None, description="Text to type.")
    keys: Optional[List[str]] = Field(default=None, description="Keys to press or hotkey sequence.")
    
    # Scrolling
    amount: Optional[int] = Field(default=None, description="Scroll amount (positive=up, negative=down).")
    direction: Optional[str] = Field(default="down", description="Scroll direction: 'up', 'down', 'left', 'right'.")
    
    # Application / Window Targets
    app_name: Optional[str] = Field(default=None, description="Application executable or alias to launch.")
    window_title: Optional[str] = Field(default=None, description="Title pattern of window to focus or close.")
    element_query: Optional[str] = Field(default=None, description="Descriptive query for UI grounding (e.g. 'Run button').")
    element_id: Optional[int] = Field(default=None, description="Structured UI element ID if available.")
    
    # Timing & Display
    duration: Optional[float] = Field(default=None, ge=0.0, description="Duration in seconds for wait or drag.")
    monitor_id: Optional[int] = Field(default=None, description="Monitor index (default=primary).")
    
    # Target environment
    target_env: str = Field(default="local", description="'local', 'remote', or 'sidecar'.")
    sidecar_id: Optional[str] = Field(default=None, description="Sidecar ID if target_env is 'sidecar'.")

    @model_validator(mode="before")
    def normalize_aliases(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values

        # Normalize action alias (e.g. 'action' key from tools)
        raw_act = values.get("action_type") or values.get("action")
        # If no explicit action was specified, infer from parameters
        if not raw_act:
            if values.get("app_name") or values.get("app"):
                raw_act = "launch_application"
            elif values.get("text"):
                raw_act = "type"
            elif values.get("keys") or values.get("key"):
                raw_act = "press"
            elif values.get("window_title") or values.get("title"):
                raw_act = "focus_window"
            elif values.get("amount") or values.get("direction"):
                raw_act = "scroll"
            else:
                raw_act = "click"

        if isinstance(raw_act, str):
            clean_act = raw_act.lower().strip().replace(" ", "_")
            if clean_act in ("open_app", "open", "launch"):
                clean_act = "launch_application"
            elif clean_act in ("focus", "switch_window"):
                clean_act = "focus_window"
            elif clean_act in ("close", "quit"):
                clean_act = "close_window"
            elif clean_act in ("type_text", "write"):
                clean_act = "type"
            elif clean_act == "click" and (values.get("app_name") or values.get("app")):
                # Correct model confusion: passed click with app_name
                clean_act = "launch_application"
            values["action_type"] = clean_act

        # Map 'key' -> 'keys'
        if "key" in values and "keys" not in values:
            values["keys"] = [values["key"]] if isinstance(values["key"], str) else values["key"]
        
        # Split string hotkeys like "ctrl+c" into list ["ctrl", "c"]
        if "keys" in values and isinstance(values["keys"], str):
            k_str = values["keys"].strip()
            if "+" in k_str:
                values["keys"] = [k.strip() for k in k_str.split("+")]
            else:
                values["keys"] = [k_str]

        # Map 'app' -> 'app_name'
        if "app" in values and "app_name" not in values:
            values["app_name"] = values["app"]

        # Map 'title' -> 'window_title'
        if "title" in values and "window_title" not in values:
            values["window_title"] = values["title"]

        return values

    def validate_bounds(self, screen_width: int, screen_height: int) -> Optional[str]:
        """
        Validate that target coordinates are within the screen boundaries.
        Returns None if valid, or an error message if out of bounds.
        """
        if self.x is not None:
            if self.x < 0 or self.x >= screen_width:
                return f"Coordinate X={self.x} is out of screen bounds [0, {screen_width - 1}]."
        if self.y is not None:
            if self.y < 0 or self.y >= screen_height:
                return f"Coordinate Y={self.y} is out of screen bounds [0, {screen_height - 1}]."
        if self.start_x is not None:
            if self.start_x < 0 or self.start_x >= screen_width:
                return f"Drag start_x={self.start_x} is out of screen bounds [0, {screen_width - 1}]."
        if self.start_y is not None:
            if self.start_y < 0 or self.start_y >= screen_height:
                return f"Drag start_y={self.start_y} is out of screen bounds [0, {screen_height - 1}]."
        if self.end_x is not None:
            if self.end_x < 0 or self.end_x >= screen_width:
                return f"Drag end_x={self.end_x} is out of screen bounds [0, {screen_width - 1}]."
        if self.end_y is not None:
            if self.end_y < 0 or self.end_y >= screen_height:
                return f"Drag end_y={self.end_y} is out of screen bounds [0, {screen_height - 1}]."
        return None


# ─── Action Result Model ─────────────────────────────────────────────────────

class ActionResult(BaseModel):
    """
    Standard structured response returned from every computer execution.
    """
    success: bool
    action: str
    target: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    backend: str = "windows"
    details: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
