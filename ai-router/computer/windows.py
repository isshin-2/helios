"""
HELIOS — Window Management Subsystem
Window enumeration, focus, safe application launching, and protected target inspection.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("helios.computer.windows")


# ─── Data Structures ─────────────────────────────────────────────────────────

@dataclass
class WindowInfo:
    handle: int
    title: str
    process_name: str
    pid: int
    bounds: Tuple[int, int, int, int]  # (left, top, right, bottom)
    is_active: bool = False
    is_visible: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "handle": self.handle,
            "title": self.title,
            "process_name": self.process_name,
            "pid": self.pid,
            "bounds": list(self.bounds),
            "is_active": self.is_active,
            "is_visible": self.is_visible,
        }


# ─── Window Backend Interface ────────────────────────────────────────────────

class BaseWindowBackend(ABC):
    @abstractmethod
    async def list_windows(self) -> List[WindowInfo]:
        """List all visible application windows."""
        ...

    @abstractmethod
    async def get_active_window(self) -> Optional[WindowInfo]:
        """Return the currently focused foreground window."""
        ...

    @abstractmethod
    async def focus_window(self, title_or_handle: str | int) -> bool:
        """Bring a window to the foreground."""
        ...

    @abstractmethod
    async def launch_application(self, app_name: str, args: Optional[List[str]] = None) -> bool:
        """Launch an application safely."""
        ...

    @abstractmethod
    async def close_window(self, title_or_handle: str | int) -> bool:
        """Close an application window."""
        ...


# ─── Windows Implementation ──────────────────────────────────────────────────

class WindowsWindowBackend(BaseWindowBackend):
    """
    Production Windows implementation using win32 API / ctypes.
    """

    def _sync_list_windows(self) -> List[WindowInfo]:
        if sys.platform != "win32":
            return []

        windows: List[WindowInfo] = []
        try:
            from tools.desktop_utils import ensure_desktop_access
            ensure_desktop_access()

            import win32gui
            import psutil

            fg_hwnd = win32gui.GetForegroundWindow()

            def enum_cb(hwnd, _):
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                title = win32gui.GetWindowText(hwnd).strip()
                if not title:
                    return True

                rect = win32gui.GetWindowRect(hwnd)
                width = rect[2] - rect[0]
                height = rect[3] - rect[1]
                if width <= 10 or height <= 10:
                    return True

                proc_name = ""
                pid_val = 0
                try:
                    import win32process
                    _, pid_val = win32process.GetWindowThreadProcessId(hwnd)
                    proc = psutil.Process(pid_val)
                    proc_name = proc.name()
                except Exception:
                    pass

                windows.append(WindowInfo(
                    handle=int(hwnd),
                    title=title,
                    process_name=proc_name,
                    pid=pid_val,
                    bounds=rect,
                    is_active=(hwnd == fg_hwnd),
                    is_visible=True
                ))
                return True

            win32gui.EnumWindows(enum_cb, None)
        except Exception as e:
            logger.debug(f"EnumWindows error: {e}")

        return windows

    async def list_windows(self) -> List[WindowInfo]:
        return await asyncio.to_thread(self._sync_list_windows)

    def _sync_get_active_window(self) -> Optional[WindowInfo]:
        if sys.platform != "win32":
            return None
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return None

            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value.strip()

            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            proc_name = ""
            try:
                import psutil
                proc = psutil.Process(pid.value)
                proc_name = proc.name()
            except Exception:
                pass

            return WindowInfo(
                handle=int(hwnd),
                title=title,
                process_name=proc_name,
                pid=pid.value,
                bounds=(0, 0, 0, 0),
                is_active=True,
                is_visible=True
            )
        except Exception as e:
            logger.debug(f"Get active window error: {e}")
            return None

    async def get_active_window(self) -> Optional[WindowInfo]:
        return await asyncio.to_thread(self._sync_get_active_window)

    def _sync_focus_window(self, title_or_handle: str | int) -> bool:
        if sys.platform != "win32":
            return False
        try:
            import ctypes
            user32 = ctypes.windll.user32

            target_hwnd = None
            if isinstance(title_or_handle, int):
                target_hwnd = title_or_handle
            else:
                query = str(title_or_handle).lower()
                for w in self._sync_list_windows():
                    if query in w.title.lower() or query in w.process_name.lower():
                        target_hwnd = w.handle
                        break

            if not target_hwnd:
                return False

            # Bring to front
            SW_RESTORE = 9
            user32.ShowWindow(target_hwnd, SW_RESTORE)
            user32.SetForegroundWindow(target_hwnd)
            return True
        except Exception as e:
            logger.error(f"Failed to focus window: {e}")
            return False

    async def focus_window(self, title_or_handle: str | int) -> bool:
        return await asyncio.to_thread(self._sync_focus_window, title_or_handle)

    def _sync_launch_application(self, app_name: str, args: Optional[List[str]] = None) -> bool:
        """Launch application without arbitrary shell commands."""
        app_clean = app_name.strip()
        cmd_args = [app_clean]
        if args:
            cmd_args.extend(args)

        # Standard known Windows applications mapping
        KNOWN_APPS = {
            "calc": "calc.exe",
            "calculator": "calc.exe",
            "notepad": "notepad.exe",
            "code": "code.cmd",
            "vscode": "code.cmd",
            "explorer": "explorer.exe",
            "terminal": "wt.exe",
            "chrome": "chrome.exe",
            "google chrome": "chrome.exe",
            "edge": "msedge.exe",
            "msedge": "msedge.exe",
            "operagx": r"C:\Users\krithik\AppData\Local\Programs\Opera GX\opera.exe",
            "operagx.exe": r"C:\Users\krithik\AppData\Local\Programs\Opera GX\opera.exe",
            "opera gx": r"C:\Users\krithik\AppData\Local\Programs\Opera GX\opera.exe",
            "opera": r"C:\Users\krithik\AppData\Local\Programs\Opera GX\opera.exe",
            "opera.exe": r"C:\Users\krithik\AppData\Local\Programs\Opera GX\opera.exe",
        }

        # If app_name is an HTTP/HTTPS URL, launch directly via default browser / webbrowser
        if app_clean.startswith("http://") or app_clean.startswith("https://"):
            try:
                import webbrowser
                webbrowser.open(app_clean)
                return True
            except Exception as e_url:
                logger.error(f"Failed to open URL '{app_clean}': {e_url}")

        exe = KNOWN_APPS.get(app_clean.lower(), app_clean)

        try:
            # We explicitly do NOT use shell=True to avoid command injection
            if sys.platform == "win32":
                subprocess.Popen([exe] + (args or []), shell=False)
                return True
        except FileNotFoundError:
            # Try launching via start without shell execution if known
            try:
                os.startfile(exe)
                return True
            except Exception as e_start:
                logger.error(f"Failed to launch application '{app_name}': {e_start}")
                return False
        except Exception as e:
            logger.error(f"Failed to launch application '{app_name}': {e}")
            return False
        return False

    async def launch_application(self, app_name: str, args: Optional[List[str]] = None) -> bool:
        return await asyncio.to_thread(self._sync_launch_application, app_name, args)

    def _sync_close_window(self, title_or_handle: str | int) -> bool:
        if sys.platform != "win32":
            return False
        try:
            import ctypes
            user32 = ctypes.windll.user32
            WM_CLOSE = 0x0010

            target_hwnd = None
            if isinstance(title_or_handle, int):
                target_hwnd = title_or_handle
            else:
                query = str(title_or_handle).lower()
                for w in self._sync_list_windows():
                    if query in w.title.lower() or query in w.process_name.lower():
                        target_hwnd = w.handle
                        break

            if target_hwnd:
                user32.PostMessageW(target_hwnd, WM_CLOSE, 0, 0)
                return True
        except Exception as e:
            logger.error(f"Failed to close window: {e}")
        return False

    async def close_window(self, title_or_handle: str | int) -> bool:
        return await asyncio.to_thread(self._sync_close_window, title_or_handle)


# ─── Mock Window Backend (for testing) ────────────────────────────────────────

class MockWindowBackend(BaseWindowBackend):
    """
    In-memory window backend for tests.
    """

    def __init__(self):
        self.windows: Dict[int, WindowInfo] = {
            101: WindowInfo(
                handle=101,
                title="Visual Studio Code - HELIOS",
                process_name="Code.exe",
                pid=1234,
                bounds=(100, 100, 1200, 900),
                is_active=True,
                is_visible=True,
            ),
            102: WindowInfo(
                handle=102,
                title="Windows PowerShell",
                process_name="powershell.exe",
                pid=5678,
                bounds=(200, 200, 1000, 800),
                is_active=False,
                is_visible=True,
            ),
        }
        self.active_handle = 101

    async def list_windows(self) -> List[WindowInfo]:
        for w in self.windows.values():
            w.is_active = (w.handle == self.active_handle)
        return list(self.windows.values())

    async def get_active_window(self) -> Optional[WindowInfo]:
        return self.windows.get(self.active_handle)

    async def focus_window(self, title_or_handle: str | int) -> bool:
        if isinstance(title_or_handle, int):
            if title_or_handle in self.windows:
                self.active_handle = title_or_handle
                return True
        else:
            q = str(title_or_handle).lower()
            for h, w in self.windows.items():
                if q in w.title.lower() or q in w.process_name.lower():
                    self.active_handle = h
                    return True
        return False

    async def launch_application(self, app_name: str, args: Optional[List[str]] = None) -> bool:
        h = max(self.windows.keys(), default=100) + 1
        title = f"{app_name.title()} Application"
        self.windows[h] = WindowInfo(
            handle=h,
            title=title,
            process_name=f"{app_name.lower()}.exe",
            pid=2000 + h,
            bounds=(50, 50, 800, 600),
            is_active=True,
            is_visible=True,
        )
        self.active_handle = h
        return True

    async def close_window(self, title_or_handle: str | int) -> bool:
        target = None
        if isinstance(title_or_handle, int):
            target = title_or_handle
        else:
            q = str(title_or_handle).lower()
            for h, w in self.windows.items():
                if q in w.title.lower() or q in w.process_name.lower():
                    target = h
                    break
        if target and target in self.windows:
            del self.windows[target]
            if self.active_handle == target:
                self.active_handle = next(iter(self.windows.keys()), 0)
            return True
        return False
