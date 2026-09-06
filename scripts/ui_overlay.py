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
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html_path = os.path.join(base_dir, 'static', 'media', 'siri_overlay.html')
    
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
        
    window_title = 'HELIOS Listening'
    
    # Use native pywebview transparency
    window = webview.create_window(
        window_title, 
        html=html_content, 
        transparent=True,
        frameless=True, 
        width=250, 
        height=250, 
        x=x + 25, 
        y=y + 25, 
        on_top=True
    )
    
    def state_updater():
        import time
        state_file = os.path.join(base_dir, 'overlay_state.txt')
        last_state = ""
        while True:
            time.sleep(0.1)
            try:
                if os.path.exists(state_file):
                    with open(state_file, "r") as f:
                        state = f.read().strip()
                    if state != last_state:
                        window.evaluate_js(f"document.getElementById('status').innerText = '{state}';")
                        last_state = state
            except Exception:
                pass

    import threading
    threading.Thread(target=state_updater, daemon=True).start()
    
    webview.start()

if __name__ == "__main__":
    main()
