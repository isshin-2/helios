import sys
import os
from PyQt5.QtCore import Qt, QUrl, QTimer
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QShortcut
from PyQt5.QtGui import QKeySequence, QColor
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage

class SilentReconnectPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        if "ERR_CONNECTION_REFUSED" in message:
            return
        super().javaScriptConsoleMessage(level, message, lineNumber, sourceID)

class AICoreOverlay(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # Tool hint hides it from the taskbar on some OS, StaysOnTopHint keeps it above other apps
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # REMOVED WA_TransparentForMouseEvents so the user can actually click the menu buttons!
        # If it blocks the screen, the user can use Ctrl+Shift+Space to toggle visibility.

        # Main widget layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.browser = QWebEngineView()
        self.browser.setPage(SilentReconnectPage(self.browser))
        # Set the webview background to transparent so our CSS gradient shows cleanly
        self.browser.page().setBackgroundColor(QColor(0, 0, 0, 0)) 
        
        # Resolve the absolute path to the HTML file
        html_file = "AI-Core-System.html"
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "static", html_file))
        
        if not os.path.exists(html_path):
            print(f"Error: Please ensure '{html_file}' is in the static directory.")
            sys.exit(1)
            
        self.browser.setUrl(QUrl.fromLocalFile(html_path))
        self.browser.page().featurePermissionRequested.connect(self.handle_feature_permission)
        self.browser.titleChanged.connect(self.on_title_changed)
        layout.addWidget(self.browser)

        # Initial size for core mode
        self.resize_and_move(300, 300)
        
        # Press Ctrl+Shift+Space to hide or show the AI Core
        self.shortcut = QShortcut(QKeySequence("Ctrl+Shift+Space"), self)
        self.shortcut.activated.connect(self.toggle_visibility)

    def resize_and_move(self, w, h):
        self.resize(w, h)
        screen = QApplication.primaryScreen().geometry()
        # Move up a bit (-200) and slightly left (-20)
        self.move(screen.width() - self.width() - 20, screen.height() - self.height() - 200)
        
        # Apply a mask to make the transparent areas click-through to the desktop
        from PyQt5.QtGui import QRegion
        from PyQt5.QtCore import QRect
        if w < 400:
            # Core mode: Mask out the empty space, leaving the bottom-right corner.
            # 300x300 window. The squircle is ~125px + large glowing box-shadow.
            # A 180x180 rectangular mask in the corner avoids clipping the glow entirely.
            box_size = 180
            mask = QRegion(QRect(w - box_size, h - box_size, box_size, box_size))
            self.setMask(mask)
        else:
            # Menu mode: full rounded rectangle
            self.setMask(QRegion(0, 0, w, h, QRegion.Rectangle))

    def on_title_changed(self, title):
        if title.startswith("resize:"):
            try:
                parts = title.split(":")[1].split(",")
                w, h = int(parts[0]), int(parts[1])
                self.resize_and_move(w, h)
            except Exception:
                pass

    def handle_feature_permission(self, url, feature):
        self.browser.page().setFeaturePermission(url, feature, self.browser.page().PermissionGrantedByUser)

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

if __name__ == '__main__':
    # Initialize application
    app = QApplication(sys.argv)
    
    # Create and show the overlay
    overlay = AICoreOverlay()
    overlay.show()
    
    print("HELIOS AI Core Desktop Overlay active.")
    print("- Press 'Ctrl+Shift+Space' to toggle visibility.")
    print("- Ready for interaction.")
    
    sys.exit(app.exec_())
