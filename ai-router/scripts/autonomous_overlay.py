import webview
import os
import sys
import ctypes

def get_target_monitor_bounds():
    """
    Identifies the display bounds (x, y, width, height) of the active monitor.
    Uses mouse cursor position or primary display fallback.
    """
    try:
        import win32api
        import win32gui
        # Get current cursor position
        point = win32gui.GetCursorPos()
        # Find monitor containing the cursor
        hmonitor = win32api.MonitorFromPoint(point, 2)  # MONITOR_DEFAULTTONEAREST = 2
        info = win32api.GetMonitorInfo(hmonitor)
        rect = info.get("Work", info.get("Monitor"))
        left, top, right, bottom = rect
        return left, top, right - left, bottom - top
    except Exception:
        # Fallback to single primary monitor
        user32 = ctypes.windll.user32
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
        return 0, 0, w, h

def enforce_topmost(window_title):
    import win32gui
    import win32con
    hwnd = win32gui.FindWindowEx(0, 0, None, window_title)
    if hwnd:
        win32gui.SetWindowPos(
            hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
        )
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_LAYERED)

def on_loaded(window):
    enforce_topmost("HELIOS Autonomous Warning")

def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
        
    mon_x, mon_y, mon_w, mon_h = get_target_monitor_bounds()
    
    # Position the HUD at the top center of the detected monitor
    width = mon_w
    height = 80
    x = mon_x
    y = mon_y + 20
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html_path = os.path.join(base_dir, 'static', 'media', 'autonomous_overlay.html')
    
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
        
    window = webview.create_window(
        "HELIOS Autonomous Warning", 
        html=html_content, 
        transparent=True,
        frameless=True, 
        width=width, 
        height=height, 
        x=x, 
        y=y, 
        on_top=True
    )
    
    webview.start(on_loaded, window)

if __name__ == "__main__":
    main()
