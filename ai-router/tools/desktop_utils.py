import sys
import logging

logger = logging.getLogger(__name__)

def ensure_desktop_access() -> bool:
    """
    On Windows, when running inside background services, subshells, or threads,
    explicitly attaches the thread to the active user's input desktop (OpenInputDesktop).
    This ensures GDI BitBlt, PIL ImageGrab, SetCursorPos, and PyAutoGUI events execute reliably.
    """
    if sys.platform != "win32":
        return True
        
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
    except Exception:
        pass

    try:
        import ctypes
        u32 = ctypes.windll.user32
        desk = u32.OpenInputDesktop(0, False, 0x01FF)
        if desk:
            u32.SetThreadDesktop(desk)
            return True
    except Exception as e:
        logger.debug(f"ensure_desktop_access notice: {e}")
        
    return False
