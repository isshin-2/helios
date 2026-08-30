import webview
import threading
import time
import ctypes
import win32gui
import win32con

def set_transparency():
    # Wait for the window to be created
    time.sleep(1)
    hwnd = win32gui.FindWindowEx(0, 0, None, "Test Window")
    if hwnd:
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style | win32con.WS_EX_LAYERED)
        # Magenta is 0x00FF00FF in COLORREF (BBGGRR)
        win32gui.SetLayeredWindowAttributes(hwnd, 0x00FF00FF, 0, win32con.LWA_COLORKEY)

w = webview.create_window('Test Window', html='<body style="background-color: transparent;"><div style="border-radius: 40px; background: red; width: 100%; height: 100%;"></div></body>', background_color='#FF00FF', frameless=True)

threading.Thread(target=set_transparency, daemon=True).start()

def on_load():
    time.sleep(4)
    w.destroy()

webview.start(on_load)
