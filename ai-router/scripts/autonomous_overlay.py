import webview
import os
import ctypes

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
        
    user32 = ctypes.windll.user32
    screen_w = user32.GetSystemMetrics(0)
    
    width = screen_w
    height = 80
    x = 0
    y = 20
    
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
