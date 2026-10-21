"""
HELIOS — Computer Tool
Integrates desktop automation with the HELIOS tool execution architecture and permission layer.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field, model_validator

from computer.actions import (
    ActionResult,
    ComputerAction,
    ComputerActionType,
)
from computer.controller import ComputerController, computer_controller
from computer.safety import ComputerSafety, emergency_stop
from tools.base import BaseTool

logger = logging.getLogger("helios.tools.computer")


# ─── Input Schema ────────────────────────────────────────────────────────────

class ComputerToolInput(BaseModel):
    action: str = Field(
        default="click",
        description=(
            "Action to perform: 'screenshot', 'click', 'double_click', 'right_click', "
            "'move', 'drag', 'scroll', 'type', 'press', 'hotkey', 'wait', "
            "'focus_window', 'launch_application', 'close_window', 'stop'."
        )
    )
    x: Optional[int] = Field(default=None, description="X coordinate for click or move.")
    y: Optional[int] = Field(default=None, description="Y coordinate for click or move.")
    start_x: Optional[int] = Field(default=None, description="Starting X for drag.")
    start_y: Optional[int] = Field(default=None, description="Starting Y for drag.")
    end_x: Optional[int] = Field(default=None, description="Ending X for drag.")
    end_y: Optional[int] = Field(default=None, description="Ending Y for drag.")
    text: Optional[str] = Field(default=None, description="Text string to type.")
    keys: Optional[Union[List[str], str]] = Field(default=None, description="Key or key combination to press.")
    key: Optional[str] = Field(default=None, description="Single key alias for keys.")
    amount: Optional[int] = Field(default=None, description="Scroll amount.")
    direction: Optional[str] = Field(default="down", description="Scroll direction: 'up', 'down', 'left', 'right'.")
    app_name: Optional[str] = Field(default=None, description="Application executable or name to launch.")
    window_title: Optional[str] = Field(default=None, description="Window title to focus or close.")
    element_query: Optional[str] = Field(default=None, description="Semantic description of UI target.")
    element_id: Optional[int] = Field(default=None, description="Pre-grounded element ID from SoM.")
    duration: Optional[float] = Field(default=None, description="Wait or drag duration in seconds.")
    monitor_id: Optional[int] = Field(default=None, description="Monitor index (default=1).")
    target_env: str = Field(default="local", description="Target environment: 'local', 'remote', or 'sidecar'.")

    @model_validator(mode="before")
    def map_aliases(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values

        # Normalize prefix if present: "computer.click" -> "click"
        if "action" in values and isinstance(values["action"], str):
            act = values["action"].strip()
            if act.startswith("computer."):
                values["action"] = act.split(".", 1)[1]

        # Infer action if missing
        if "action" not in values or not values["action"]:
            if values.get("app_name") or values.get("app"):
                values["action"] = "launch_application"
            elif values.get("text"):
                values["action"] = "type"
            elif values.get("keys") or values.get("key"):
                values["action"] = "press"
            elif values.get("window_title") or values.get("title"):
                values["action"] = "focus_window"
            elif values.get("amount") or values.get("direction"):
                values["action"] = "scroll"

        # Map 'open_app' -> 'launch_application'
        if values.get("action") in ("open_app", "open", "launch"):
            values["action"] = "launch_application"
            if not values.get("app_name") and values.get("text"):
                values["app_name"] = values["text"]
        elif values.get("action") == "click" and (values.get("app_name") or values.get("app")):
            values["action"] = "launch_application"

        # Map click_type -> action
        if "click_type" in values and "action" not in values:
            values["action"] = values["click_type"]

        # Map key -> keys
        if "key" in values and "keys" not in values:
            values["keys"] = [values["key"]]

        return values


# Compatibility alias
ComputerInput = ComputerToolInput


# ─── Tool Implementation ─────────────────────────────────────────────────────

class ComputerControlTool(BaseTool):
    """
    HELIOS Computer Control Tool.
    Exposes desktop automation with closed-loop verification and permission governance.
    """

    def __init__(
        self,
        provider: Any = None,
        monitor: Any = None,
        controller: Optional[ComputerController] = None,
        permission_manager: Any = None,
        *args,
        **kwargs,
    ):
        self.provider = provider
        self.monitor = monitor
        self.controller = controller or computer_controller
        self.permission_manager = permission_manager

    @property
    def name(self) -> str:
        return "computer_control"

    @property
    def description(self) -> str:
        return (
            "Interact with the computer (mouse, keyboard, windows, applications). "
            "Supports: screenshot, click, double_click, right_click, move, drag, "
            "scroll, type, press, hotkey, wait, focus_window, launch_application, "
            "close_window, and stop."
        )

    @property
    def input_schema(self) -> type[BaseModel]:
        return ComputerToolInput

    @property
    def requires_permission(self) -> bool:
        # Permission checks are enforced via PermissionManager
        return True

    async def execute(self, user_id: int = 0, **kwargs) -> Tuple[str, str]:
        # 1. Parse into ComputerAction
        try:
            action_obj = ComputerAction(**kwargs)
        except Exception as e:
            err_res = ActionResult(
                success=False,
                action=str(kwargs.get("action", "unknown")),
                target=kwargs,
                error=f"Invalid action parameters: {e}"
            )
            return json.dumps(err_res.to_dict()), self.name

        # 2. Permission and Safety Check
        target_name = action_obj.app_name or action_obj.window_title or action_obj.element_query or action_obj.text
        risk_level = ComputerSafety.classify_risk(action_obj)

        if self.permission_manager:
            perm_res = self.permission_manager.can_control_computer(
                user_id=user_id,
                action=action_obj.action_type.value,
                target=target_name,
                details=kwargs
            )
            if not perm_res.allowed:
                err_res = ActionResult(
                    success=False,
                    action=action_obj.action_type.value,
                    target={"target": target_name},
                    error=f"Permission denied: {perm_res.reason}"
                )
                return json.dumps(err_res.to_dict()), self.name

            # Check if privileged approval is required
            if "approval" in perm_res.reason.lower() or risk_level.value in ("high", "critical"):
                # Check if session already approved
                if not self.permission_manager.approval_manager.has_session_approval(
                    user_id, "computer_control", action_obj.action_type.value
                ):
                    return f"APPROVAL_REQUIRED::computer_control::{action_obj.action_type.value}", self.name

        # 3. Execute via ComputerController
        result = await self.controller.execute_action(action_obj)
        return json.dumps(result.to_dict()), self.name


# Alias for clean modular access
ComputerTool = ComputerControlTool
