import webview
import threading
import time

def show_webview():
    def _run():
        import ctypes
        user32 = ctypes.windll.user32
        sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        w, h = 250, 250
        
        with open('siri_overlay.html', 'r', encoding='utf-8') as f:
            html = f.read()
            
        window = webview.create_window('Siri', html=html, transparent=True, frameless=True, width=w, height=h, x=sw-w-40, y=sh-h-80)
        
        def close_window():
            time.sleep(4)
            window.destroy()
            
        webview.start(close_window)
        print("Webview closed")

    threading.Thread(target=_run, daemon=True).start()

if __name__ == "__main__":
    show_webview()
    time.sleep(5)
    print("Main thread exiting")
