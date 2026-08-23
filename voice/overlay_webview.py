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
    
    # We use a solid dark background for the widget to completely avoid Windows WebView2 transparency bugs.
    window = webview.create_window(
        window_title, 
        html=html_content, 
        transparent=False,
        background_color='#1a1a1a', # Dark grey to match body
        frameless=True, 
        width=w, 
        height=h, 
        x=x, 
        y=y,
        on_top=True
    )
    
    webview.start()

if __name__ == "__main__":
    main()
