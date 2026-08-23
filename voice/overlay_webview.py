import webview
import os
import ctypes

def main():
    # Make the process DPI aware so it correctly calculates screen size on zoomed displays
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
        
    user32 = ctypes.windll.user32
    screen_w = user32.GetSystemMetrics(0)
    screen_h = user32.GetSystemMetrics(1)
    
    w, h = 300, 300
    x = screen_w - w - 30
    y = screen_h - h - 70
    
    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'siri_overlay.html')
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
        
    window_title = 'HELIOS Listening'
    
    # We use a Magenta background and set it as the transparent color key via win32gui
    # This forces the corners to be 100% transparent even if WebView2 transparency is broken on the OS.
    window = webview.create_window(
        window_title, 
        html=html_content, 
        transparent=True,
        background_color='#FF00FF', # Magenta
        frameless=True, 
        width=w, 
        height=h, 
        x=x, 
        y=y,
        on_top=True
    )
    
    def apply_transparency():
        import time
        import win32gui
        import win32con
        time.sleep(0.5) # Wait for window to render
        hwnd = win32gui.FindWindowEx(0, 0, None, window_title)
        if hwnd:
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style | win32con.WS_EX_LAYERED)
            # Magenta in COLORREF is 0x00FF00FF (BBGGRR)
            win32gui.SetLayeredWindowAttributes(hwnd, 0x00FF00FF, 0, win32con.LWA_COLORKEY)

    import threading
    threading.Thread(target=apply_transparency, daemon=True).start()
    
    webview.start()

if __name__ == "__main__":
    main()
