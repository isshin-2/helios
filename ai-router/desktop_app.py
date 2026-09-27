import sys
import os
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QShortcut
from PyQt5.QtGui import QKeySequence, QIcon
from PyQt5.QtWebEngineWidgets import QWebEngineView

class HeliosFullApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("HELIOS AI Desktop App")
        # Base dimensions that match a standard desktop app
        self.resize(1280, 850)
        
        # Center on screen
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

        # Main widget layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.browser = QWebEngineView()
        
        # Point to the local HELIOS server (the SITE)
        # This guarantees the APP and the SITE match perfectly, with all site features intact!
        self.browser.setUrl(QUrl("http://127.0.0.1:8000/static/app.html"))
        layout.addWidget(self.browser)
        
        # Reload shortcut (F5)
        self.reload_shortcut = QShortcut(QKeySequence("F5"), self)
        self.reload_shortcut.activated.connect(self.browser.reload)
        
        # DevTools shortcut (F12)
        # Not easily supported in basic PyQtWebEngine without extra setup, but kept for future.

if __name__ == '__main__':
    # Initialize application
    app = QApplication(sys.argv)
    
    # Create and show the full desktop app
    window = HeliosFullApp()
    window.show()
    
    print("HELIOS Full Desktop App launched.")
    print("- Loading Site UI from local server...")
    print("- Ensure HELIOS backend (start.bat or main.py) is running to serve the UI.")
    print("- Press 'F5' to refresh the page.")
    
    sys.exit(app.exec_())
