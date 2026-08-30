import os
import webview
import threading
import time

def main():
    # Set webview2 background to transparent using environment variable
    os.environ['WEBVIEW2_DEFAULT_BACKGROUND_COLOR'] = '00000000'
    
    html = """
    <body style="background-color: transparent; overflow: hidden; display: flex; justify-content: center; align-items: center; margin: 0;">
        <div style="width: 100px; height: 100px; background: rgba(0, 200, 255, 0.5); border-radius: 50%; box-shadow: 0 0 20px #00c8ff;">
        </div>
    </body>
    """
    
    w = webview.create_window('Test Alpha', html=html, transparent=True, frameless=True, width=300, height=300, on_top=True)
    
    def on_load():
        time.sleep(4)
        w.destroy()
        
    webview.start(on_load)

if __name__ == "__main__":
    main()
