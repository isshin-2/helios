"""
HELIOS — High-Level Computer Controller
Unified execution interface for desktop automation.
Supports pluggable backends: Windows (native), Mock (testing), Sidecar (remote).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from computer.actions import (
    ActionRiskLevel,
    ActionResult,
    ComputerAction,
    ComputerActionType,
)
from computer.safety import ComputerSafety, emergency_stop
from computer.screenshot import (
    BaseScreenshotBackend,
    MockScreenshotBackend,
    ScreenshotData,
    ScreenshotManager,
    WindowsScreenshotBackend,
)
from computer.windows import (
    BaseWindowBackend,
    MockWindowBackend,
    WindowInfo,
    WindowsWindowBackend,
)

logger = logging.getLogger("helios.computer.controller")


# ─── Abstract Low-Level Computer Backend ──────────────────────────────────────

class BaseComputerBackend(ABC):
    @abstractmethod
    async def move(self, x: int, y: int) -> None: ...

    @abstractmethod
    async def click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = "left") -> None: ...

    @abstractmethod
    async def double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> None: ...

    @abstractmethod
    async def right_click(self, x: Optional[int] = None, y: Optional[int] = None) -> None: ...

    @abstractmethod
    async def drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5) -> None: ...

    @abstractmethod
    async def scroll(self, amount: int, direction: str = "down") -> None: ...

    @abstractmethod
    async def type_text(self, text: str) -> None: ...

    @abstractmethod
    async def press(self, keys: List[str]) -> None: ...

    @abstractmethod
    async def hotkey(self, keys: List[str]) -> None: ...

    @abstractmethod
    async def get_screen_size(self) -> Tuple[int, int]: ...


# ─── Windows PyAutoGUI / ctypes Backend ───────────────────────────────────────

class WindowsComputerBackend(BaseComputerBackend):
    """
    Production Windows backend.
    Executes all blocking desktop calls inside asyncio.to_thread with safety checks.
    """

    def __init__(self):
        self._ensure_access()

    def _ensure_access(self):
        try:
            from tools.desktop_utils import ensure_desktop_access
            ensure_desktop_access()
        except Exception:
            pass

    def _sync_move(self, x: int, y: int):
        self._ensure_access()
        import pyautogui
        pyautogui.moveTo(x, y)

    async def move(self, x: int, y: int) -> None:
        await asyncio.to_thread(self._sync_move, x, y)

    def _sync_click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = "left"):
        self._ensure_access()
        import pyautogui
        if x is not None and y is not None:
            pyautogui.click(x=x, y=y, button=button)
        else:
            pyautogui.click(button=button)

    async def click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = "left") -> None:
        await asyncio.to_thread(self._sync_click, x, y, button)

    def _sync_double_click(self, x: Optional[int] = None, y: Optional[int] = None):
        self._ensure_access()
        import pyautogui
        if x is not None and y is not None:
            pyautogui.doubleClick(x=x, y=y)
        else:
            pyautogui.doubleClick()

    async def double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> None:
        await asyncio.to_thread(self._sync_double_click, x, y)

    def _sync_right_click(self, x: Optional[int] = None, y: Optional[int] = None):
        self._ensure_access()
        import pyautogui
        if x is not None and y is not None:
            pyautogui.rightClick(x=x, y=y)
        else:
            pyautogui.rightClick()

    async def right_click(self, x: Optional[int] = None, y: Optional[int] = None) -> None:
        await asyncio.to_thread(self._sync_right_click, x, y)

    def _sync_drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5):
        self._ensure_access()
        import pyautogui
        pyautogui.moveTo(start_x, start_y)
        pyautogui.dragTo(end_x, end_y, duration=duration, button="left")

    async def drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5) -> None:
        await asyncio.to_thread(self._sync_drag, start_x, start_y, end_x, end_y, duration)

    def _sync_scroll(self, amount: int, direction: str = "down"):
        self._ensure_access()
        import pyautogui
        val = amount if direction == "up" else -abs(amount)
        pyautogui.scroll(val)

    async def scroll(self, amount: int, direction: str = "down") -> None:
        await asyncio.to_thread(self._sync_scroll, amount, direction)

    def _sync_type(self, text: str):
        self._ensure_access()
        import pyautogui
        pyautogui.write(text, interval=0.01)

    async def type_text(self, text: str) -> None:
        await asyncio.to_thread(self._sync_type, text)

    def _sync_press(self, keys: List[str]):
        self._ensure_access()
        import pyautogui
        for k in keys:
            pyautogui.press(k)

    async def press(self, keys: List[str]) -> None:
        await asyncio.to_thread(self._sync_press, keys)

    def _sync_hotkey(self, keys: List[str]):
        self._ensure_access()
        import pyautogui
        pyautogui.hotkey(*keys)

    async def hotkey(self, keys: List[str]) -> None:
        await asyncio.to_thread(self._sync_hotkey, keys)

    def _sync_get_screen_size(self) -> Tuple[int, int]:
        self._ensure_access()
        import pyautogui
        return pyautogui.size()

    async def get_screen_size(self) -> Tuple[int, int]:
        return await asyncio.to_thread(self._sync_get_screen_size)


# ─── Mock Computer Backend (for Testing) ──────────────────────────────────────

class MockComputerBackend(BaseComputerBackend):
    """
    In-memory mock backend that logs operations and maintains virtual mouse/keyboard state.
    """

    def __init__(self, width: int = 1920, height: int = 1080):
        self.width = width
        self.height = height
        self.cursor_pos = (width // 2, height // 2)
        self.typed_text: List[str] = []
        self.pressed_keys: List[str] = []
        self.history: List[Dict[str, Any]] = []

    async def move(self, x: int, y: int) -> None:
        self.cursor_pos = (x, y)
        self.history.append({"action": "move", "x": x, "y": y})

    async def click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = "left") -> None:
        if x is not None and y is not None:
            self.cursor_pos = (x, y)
        self.history.append({"action": "click", "x": self.cursor_pos[0], "y": self.cursor_pos[1], "button": button})

    async def double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> None:
        if x is not None and y is not None:
            self.cursor_pos = (x, y)
        self.history.append({"action": "double_click", "x": self.cursor_pos[0], "y": self.cursor_pos[1]})

    async def right_click(self, x: Optional[int] = None, y: Optional[int] = None) -> None:
        if x is not None and y is not None:
            self.cursor_pos = (x, y)
        self.history.append({"action": "right_click", "x": self.cursor_pos[0], "y": self.cursor_pos[1]})

    async def drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5) -> None:
        self.cursor_pos = (end_x, end_y)
        self.history.append({"action": "drag", "from": (start_x, start_y), "to": (end_x, end_y), "duration": duration})

    async def scroll(self, amount: int, direction: str = "down") -> None:
        self.history.append({"action": "scroll", "amount": amount, "direction": direction})

    async def type_text(self, text: str) -> None:
        self.typed_text.append(text)
        self.history.append({"action": "type", "text": text})

    async def press(self, keys: List[str]) -> None:
        self.pressed_keys.extend(keys)
        self.history.append({"action": "press", "keys": keys})

    async def hotkey(self, keys: List[str]) -> None:
        self.pressed_keys.extend(keys)
        self.history.append({"action": "hotkey", "keys": keys})

    async def get_screen_size(self) -> Tuple[int, int]:
        return (self.width, self.height)


# ─── High-Level Computer Controller ──────────────────────────────────────────

class ComputerController:
    """
    Central controller for desktop automation.
    Coordinates backend actions, safety verification, emergency stop, screenshots, and window focus.
    """

    def __init__(
        self,
        backend: Optional[BaseComputerBackend] = None,
        screenshot_backend: Optional[BaseScreenshotBackend] = None,
        window_backend: Optional[BaseWindowBackend] = None,
    ):
        if backend is not None:
            self.backend = backend
        else:
            try:
                self.backend = WindowsComputerBackend() if sys.platform == "win32" else MockComputerBackend()
            except Exception as e:
                logger.warning(f"Native computer backend initialization failed ({e}), using mock backend.")
                self.backend = MockComputerBackend()

        if screenshot_backend is not None:
            s_backend = screenshot_backend
        elif isinstance(self.backend, MockComputerBackend):
            s_backend = MockScreenshotBackend()
        else:
            try:
                s_backend = WindowsScreenshotBackend() if sys.platform == "win32" else MockScreenshotBackend()
            except Exception as e:
                logger.warning(f"Native screenshot backend initialization failed ({e}), using mock backend.")
                s_backend = MockScreenshotBackend()
        self.screenshot_manager = ScreenshotManager(backend=s_backend)

        if window_backend is not None:
            self.window_backend = window_backend
        elif isinstance(self.backend, MockComputerBackend):
            self.window_backend = MockWindowBackend()
        else:
            try:
                self.window_backend = WindowsWindowBackend() if sys.platform == "win32" else MockWindowBackend()
            except Exception as e:
                logger.warning(f"Native window backend initialization failed ({e}), using mock backend.")
                self.window_backend = MockWindowBackend()
        self._overlay_process = None
        self._overlay_ref_count = 0

    # ── Autonomous Overlay HUD Integration ─────────────────────────────────────

    def show_hands_off_overlay(self) -> None:
        """Launch the small top HUD banner alerting user to take hands off keyboard."""
        try:
            self._overlay_ref_count += 1
            if self._overlay_process is not None and self._overlay_process.poll() is None:
                return  # already running

            import subprocess
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            script_path = os.path.join(base_dir, "scripts", "autonomous_overlay.py")
            if os.path.exists(script_path):
                self._overlay_process = subprocess.Popen(
                    [sys.executable, script_path],
                    cwd=base_dir
                )
                logger.info("Autonomous hands-off overlay HUD launched.")
                try:
                    from core.audio_chimes import chime_engine
                    chime_engine.play_chime("thinking")
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Failed to show hands-off overlay: {e}")

    def dismiss_hands_off_overlay(self, force: bool = False) -> None:
        """Dismiss the autonomous overlay HUD when control finishes."""
        try:
            if force:
                self._overlay_ref_count = 0
            else:
                self._overlay_ref_count = max(0, self._overlay_ref_count - 1)

            if self._overlay_ref_count == 0 and self._overlay_process is not None:
                if self._overlay_process.poll() is None:
                    self._overlay_process.terminate()
                    try:
                        self._overlay_process.wait(timeout=1.0)
                    except Exception:
                        self._overlay_process.kill()
                self._overlay_process = None
                logger.info("Autonomous hands-off overlay HUD dismissed.")
                try:
                    from core.audio_chimes import chime_engine
                    chime_engine.play_chime("complete")
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Failed to dismiss hands-off overlay: {e}")

    # ── Emergency Stop Integration ───────────────────────────────────────────

    def stop(self, reason: str = "Manual stop requested") -> None:
        """Trigger immediate emergency stop."""
        self.dismiss_hands_off_overlay(force=True)
        try:
            from core.audio_chimes import chime_engine
            chime_engine.play_chime("abort")
        except Exception:
            pass
        emergency_stop.trigger(reason)

    def reset_stop(self) -> None:
        """Clear emergency stop."""
        emergency_stop.reset()

    # ── Primary Dispatcher ───────────────────────────────────────────────────

    async def execute_action(self, action: ComputerAction, timeout: float = 15.0) -> ActionResult:
        """
        Execute a single ComputerAction with bounds checking, emergency stop checks, and timeouts.
        """
        # 1. Check emergency stop
        if emergency_stop.is_stopped:
            return ActionResult(
                success=False,
                action=action.action_type.value,
                target={"reason": emergency_stop.reason},
                backend=type(self.backend).__name__,
                error=f"Emergency stop engaged: {emergency_stop.reason}",
            )

        # 2. Check for stop action
        if action.action_type == ComputerActionType.STOP:
            self.stop("Stop action requested")
            return ActionResult(
                success=True,
                action="stop",
                target={"status": "stopped"},
                backend=type(self.backend).__name__,
                details={"message": "Emergency stop triggered successfully."},
            )

        # 3. Validate coordinate bounds
        screen_w, screen_h = await self.backend.get_screen_size()
        bounds_err = action.validate_bounds(screen_w, screen_h)
        if bounds_err:
            return ActionResult(
                success=False,
                action=action.action_type.value,
                target={"x": action.x, "y": action.y},
                backend=type(self.backend).__name__,
                error=bounds_err,
            )

        # 4. Route remote / sidecar actions
        from core.sidecar_manager import sidecar_manager
        if action.target_env == "sidecar" or (os.environ.get("DEPLOYMENT_MODE") == "server" and sidecar_manager.has_active_sidecars()):
            return await self._execute_on_sidecar(action, timeout=timeout)

        # 5. Execute locally with timeout
        active_physical_action = action.action_type not in (
            ComputerActionType.SCREENSHOT,
            ComputerActionType.WAIT,
            ComputerActionType.STOP
        )
        if active_physical_action:
            self.show_hands_off_overlay()

        try:
            res = await asyncio.wait_for(
                self._dispatch_local(action),
                timeout=timeout
            )
            return res
        except asyncio.TimeoutError:
            return ActionResult(
                success=False,
                action=action.action_type.value,
                target=action.model_dump(exclude_none=True),
                backend=type(self.backend).__name__,
                error=f"Action '{action.action_type.value}' timed out after {timeout}s",
            )
        except Exception as e:
            logger.error(f"Action execution error: {e}", exc_info=True)
            return ActionResult(
                success=False,
                action=action.action_type.value,
                target=action.model_dump(exclude_none=True),
                backend=type(self.backend).__name__,
                error=str(e),
            )
        finally:
            if active_physical_action:
                self.dismiss_hands_off_overlay()

    async def _dispatch_local(self, action: ComputerAction) -> ActionResult:
        act = action.action_type

        if act == ComputerActionType.SCREENSHOT:
            shot = await self.screenshot(monitor_id=action.monitor_id)
            return ActionResult(
                success=True,
                action="screenshot",
                target={"monitor_id": action.monitor_id or 1},
                backend=type(self.backend).__name__,
                details={
                    "width": shot.width,
                    "height": shot.height,
                    "format": shot.format,
                    "timestamp": shot.timestamp,
                }
            )

        elif act == ComputerActionType.MOVE:
            if action.x is None or action.y is None:
                raise ValueError("X and Y coordinates required for move")
            await self.backend.move(action.x, action.y)
            return ActionResult(
                success=True,
                action="move",
                target={"x": action.x, "y": action.y},
                backend=type(self.backend).__name__,
            )

        elif act == ComputerActionType.CLICK:
            await self.backend.click(x=action.x, y=action.y, button="left")
            self.screenshot_manager.invalidate_cache()
            return ActionResult(
                success=True,
                action="click",
                target={"x": action.x, "y": action.y},
                backend=type(self.backend).__name__,
            )

        elif act == ComputerActionType.DOUBLE_CLICK:
            await self.backend.double_click(x=action.x, y=action.y)
            self.screenshot_manager.invalidate_cache()
            return ActionResult(
                success=True,
                action="double_click",
                target={"x": action.x, "y": action.y},
                backend=type(self.backend).__name__,
            )

        elif act == ComputerActionType.RIGHT_CLICK:
            await self.backend.right_click(x=action.x, y=action.y)
            self.screenshot_manager.invalidate_cache()
            return ActionResult(
                success=True,
                action="right_click",
                target={"x": action.x, "y": action.y},
                backend=type(self.backend).__name__,
            )

        elif act == ComputerActionType.DRAG:
            if None in (action.start_x, action.start_y, action.end_x, action.end_y):
                raise ValueError("start_x, start_y, end_x, end_y are all required for drag")
            await self.backend.drag(
                action.start_x, action.start_y, action.end_x, action.end_y,
                duration=action.duration or 0.5
            )
            self.screenshot_manager.invalidate_cache()
            return ActionResult(
                success=True,
                action="drag",
                target={"from": [action.start_x, action.start_y], "to": [action.end_x, action.end_y]},
                backend=type(self.backend).__name__,
            )

        elif act == ComputerActionType.SCROLL:
            amount = action.amount or 300
            await self.backend.scroll(amount=amount, direction=action.direction or "down")
            self.screenshot_manager.invalidate_cache()
            return ActionResult(
                success=True,
                action="scroll",
                target={"amount": amount, "direction": action.direction},
                backend=type(self.backend).__name__,
            )

        elif act == ComputerActionType.TYPE:
            text = action.text or ""
            await self.backend.type_text(text)
            self.screenshot_manager.invalidate_cache()
            return ActionResult(
                success=True,
                action="type",
                target={"length": len(text)},
                backend=type(self.backend).__name__,
            )

        elif act == ComputerActionType.PRESS:
            keys = action.keys or []
            await self.backend.press(keys)
            self.screenshot_manager.invalidate_cache()
            return ActionResult(
                success=True,
                action="press",
                target={"keys": keys},
                backend=type(self.backend).__name__,
            )

        elif act == ComputerActionType.HOTKEY:
            keys = action.keys or []
            await self.backend.hotkey(keys)
            self.screenshot_manager.invalidate_cache()
            return ActionResult(
                success=True,
                action="hotkey",
                target={"keys": keys},
                backend=type(self.backend).__name__,
            )

        elif act == ComputerActionType.WAIT:
            dur = action.duration or 1.0
            await asyncio.sleep(dur)
            return ActionResult(
                success=True,
                action="wait",
                target={"duration": dur},
                backend=type(self.backend).__name__,
            )

        elif act == ComputerActionType.FOCUS_WINDOW:
            target = action.window_title or action.app_name or ""
            ok = await self.window_backend.focus_window(target)
            self.screenshot_manager.invalidate_cache()
            return ActionResult(
                success=ok,
                action="focus_window",
                target={"target": target},
                backend=type(self.window_backend).__name__,
                error=None if ok else f"Window matching '{target}' not found.",
            )

        elif act == ComputerActionType.LAUNCH_APPLICATION:
            app = action.app_name or ""
            ok = await self.window_backend.launch_application(app)
            self.screenshot_manager.invalidate_cache()
            return ActionResult(
                success=ok,
                action="launch_application",
                target={"app_name": app},
                backend=type(self.window_backend).__name__,
                error=None if ok else f"Failed to launch application '{app}'.",
            )

        elif act == ComputerActionType.CLOSE_WINDOW:
            target = action.window_title or action.app_name or ""
            ok = await self.window_backend.close_window(target)
            self.screenshot_manager.invalidate_cache()
            return ActionResult(
                success=ok,
                action="close_window",
                target={"target": target},
                backend=type(self.window_backend).__name__,
                error=None if ok else f"Failed to close window '{target}'.",
            )

        else:
            return ActionResult(
                success=False,
                action=str(act),
                target={},
                backend=type(self.backend).__name__,
                error=f"Unsupported action type: {act}",
            )

    # ── Convenience Methods ──────────────────────────────────────────────────

    async def screenshot(self, monitor_id: Optional[int] = None, force_fresh: bool = True) -> ScreenshotData:
        return await self.screenshot_manager.capture_screen(monitor_id=monitor_id, force_fresh=force_fresh)

    async def click(self, x: Optional[int] = None, y: Optional[int] = None) -> ActionResult:
        return await self.execute_action(ComputerAction(action_type=ComputerActionType.CLICK, x=x, y=y))

    async def double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> ActionResult:
        return await self.execute_action(ComputerAction(action_type=ComputerActionType.DOUBLE_CLICK, x=x, y=y))

    async def right_click(self, x: Optional[int] = None, y: Optional[int] = None) -> ActionResult:
        return await self.execute_action(ComputerAction(action_type=ComputerActionType.RIGHT_CLICK, x=x, y=y))

    async def move(self, x: int, y: int) -> ActionResult:
        return await self.execute_action(ComputerAction(action_type=ComputerActionType.MOVE, x=x, y=y))

    async def drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5) -> ActionResult:
        return await self.execute_action(ComputerAction(
            action_type=ComputerActionType.DRAG, start_x=start_x, start_y=start_y, end_x=end_x, end_y=end_y, duration=duration
        ))

    async def scroll(self, amount: int = 300, direction: str = "down") -> ActionResult:
        return await self.execute_action(ComputerAction(
            action_type=ComputerActionType.SCROLL, amount=amount, direction=direction
        ))

    async def type_text(self, text: str) -> ActionResult:
        return await self.execute_action(ComputerAction(action_type=ComputerActionType.TYPE, text=text))

    async def press(self, keys: List[str] | str) -> ActionResult:
        k_list = [keys] if isinstance(keys, str) else keys
        return await self.execute_action(ComputerAction(action_type=ComputerActionType.PRESS, keys=k_list))

    async def hotkey(self, keys: List[str] | str) -> ActionResult:
        k_list = [keys] if isinstance(keys, str) else keys
        return await self.execute_action(ComputerAction(action_type=ComputerActionType.HOTKEY, keys=k_list))

    async def wait(self, duration: float = 1.0) -> ActionResult:
        return await self.execute_action(ComputerAction(action_type=ComputerActionType.WAIT, duration=duration))

    async def focus_window(self, title: str) -> ActionResult:
        return await self.execute_action(ComputerAction(action_type=ComputerActionType.FOCUS_WINDOW, window_title=title))

    async def launch_application(self, app_name: str) -> ActionResult:
        return await self.execute_action(ComputerAction(action_type=ComputerActionType.LAUNCH_APPLICATION, app_name=app_name))

    async def close_window(self, title: str) -> ActionResult:
        return await self.execute_action(ComputerAction(action_type=ComputerActionType.CLOSE_WINDOW, window_title=title))

    # ── Remote / Sidecar Dispatch ────────────────────────────────────────────

    async def _execute_on_sidecar(self, action: ComputerAction, timeout: float = 30.0) -> ActionResult:
        try:
            from core.sidecar_manager import sidecar_manager
            payload = action.model_dump(exclude_none=True)
            res = await sidecar_manager.execute_on_sidecar("computer_action", payload, timeout=int(timeout))
            if "error" in res:
                return ActionResult(
                    success=False,
                    action=action.action_type.value,
                    target={"env": "sidecar", "sidecar_id": action.sidecar_id},
                    backend="sidecar",
                    error=res["error"]
                )
            return ActionResult(
                success=res.get("success", True),
                action=action.action_type.value,
                target={"env": "sidecar"},
                backend="sidecar",
                details=res.get("result", res),
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action=action.action_type.value,
                target={"env": "sidecar"},
                backend="sidecar",
                error=f"Sidecar dispatch failed: {e}",
            )


# Global default controller
computer_controller = ComputerController()
