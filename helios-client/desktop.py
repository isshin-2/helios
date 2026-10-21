"""
HELIOS Client — Desktop GUI Application
Cyberpunk native desktop application embedding the remote HELIOS Web HUD with
live endpoint switching, background sidecar management, and system tray integration.
"""

from __future__ import annotations

import asyncio
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

try:
    from .config import (
        SERVER_PRESETS,
        check_server_health,
        get_server_url,
        set_server_url,
        wake_server_wol,
        load_client_config,
    )
    from .sidecar import ClientSidecarDaemon
except ImportError:
    from config import (
        SERVER_PRESETS,
        check_server_health,
        get_server_url,
        set_server_url,
        wake_server_wol,
        load_client_config,
    )
    from sidecar import ClientSidecarDaemon

# Try PyQt5 imports
try:
    from PyQt5.QtCore import Qt, QUrl, QTimer, pyqtSignal, QObject
    from PyQt5.QtWidgets import (
        QApplication,
        QMainWindow,
        QVBoxLayout,
        QHBoxLayout,
        QWidget,
        QLineEdit,
        QPushButton,
        QLabel,
        QComboBox,
        QShortcut,
        QSystemTrayIcon,
        QMenu,
        QAction,
        QMessageBox,
    )
    from PyQt5.QtGui import QKeySequence, QIcon, QColor, QFont
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
    HAS_PYQT = True
except ImportError:
    HAS_PYQT = False


class SidecarWorker(threading.Thread):
    """Background worker running the ClientSidecarDaemon event loop."""

    def __init__(self, server_url: str):
        super().__init__(daemon=True)
        self.server_url = server_url
        self.daemon_instance = ClientSidecarDaemon(server_url=server_url)
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.daemon_instance.run())
        except Exception:
            pass

    def stop(self):
        if self.daemon_instance:
            self.daemon_instance.stop()
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)


if HAS_PYQT:
    class SilentPage(QWebEnginePage):
        def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
            if "ERR_CONNECTION_REFUSED" in message:
                return
            super().javaScriptConsoleMessage(level, message, lineNumber, sourceID)


    class HeliosClientWindow(QMainWindow):
        def __init__(self, initial_server: Optional[str] = None):
            super().__init__()
            self.current_server = (initial_server or get_server_url()).rstrip("/")
            self.sidecar_worker: Optional[SidecarWorker] = None
            self.sidecar_active = False

            self.initUI()
            self.start_health_timer()

            # Auto-start sidecar if configured
            cfg = load_client_config()
            if cfg.get("auto_connect_sidecar", True):
                self.toggle_sidecar(force_state=True)

        def initUI(self):
            self.setWindowTitle("HELIOS AI Client")
            self.resize(1300, 880)
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #090a10;
                }
                QWidget#topBar {
                    background-color: #0d1017;
                    border-bottom: 1px solid #1a2333;
                    padding: 4px;
                }
                QLabel#logoLabel {
                    color: #00e5ff;
                    font-weight: bold;
                    font-size: 13px;
                    letter-spacing: 1px;
                }
                QLabel#statusLabel {
                    font-size: 11px;
                    font-weight: bold;
                    padding: 2px 8px;
                    border-radius: 4px;
                }
                QLineEdit#urlInput {
                    background-color: #121824;
                    color: #e2e8f0;
                    border: 1px solid #2d3748;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 12px;
                }
                QLineEdit#urlInput:focus {
                    border: 1px solid #00e5ff;
                }
                QComboBox#presetCombo {
                    background-color: #121824;
                    color: #e2e8f0;
                    border: 1px solid #2d3748;
                    border-radius: 4px;
                    padding: 3px 8px;
                    font-size: 11px;
                }
                QPushButton {
                    background-color: #1a2333;
                    color: #00e5ff;
                    border: 1px solid #00e5ff;
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #00e5ff;
                    color: #090a10;
                }
                QPushButton#btnSidecarActive {
                    background-color: #0d3826;
                    color: #38ef7d;
                    border: 1px solid #38ef7d;
                }
                QPushButton#btnSidecarInactive {
                    background-color: #331a1a;
                    color: #ff5252;
                    border: 1px solid #ff5252;
                }
                QPushButton#btnWake {
                    color: #ffb700;
                    border-color: #ffb700;
                }
                QPushButton#btnWake:hover {
                    background-color: #ffb700;
                    color: #090a10;
                }
            """)

            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            main_layout = QVBoxLayout(central_widget)
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(0)

            # ── Top Control Bar ─────────────────────────────────────────────
            top_bar = QWidget()
            top_bar.setObjectName("topBar")
            bar_layout = QHBoxLayout(top_bar)
            bar_layout.setContentsMargins(10, 6, 10, 6)
            bar_layout.setSpacing(8)

            # Logo
            self.logo = QLabel("✦ HELIOS CLIENT")
            self.logo.setObjectName("logoLabel")
            bar_layout.addWidget(self.logo)

            # Status pill
            self.status_pill = QLabel("CHECKING...")
            self.status_pill.setObjectName("statusLabel")
            self.status_pill.setStyleSheet("background-color: #2d3748; color: #a0aec0;")
            bar_layout.addWidget(self.status_pill)

            # Preset selector
            self.preset_combo = QComboBox()
            self.preset_combo.setObjectName("presetCombo")
            for preset in SERVER_PRESETS:
                self.preset_combo.addItem(preset["name"], preset["url"])
            self.preset_combo.addItem("Custom URL...", "")
            self.preset_combo.currentIndexChanged.connect(self.on_preset_changed)
            bar_layout.addWidget(self.preset_combo)

            # Server URL Input
            self.url_input = QLineEdit(self.current_server)
            self.url_input.setObjectName("urlInput")
            self.url_input.setMinimumWidth(240)
            self.url_input.returnPressed.connect(self.apply_server_url)
            bar_layout.addWidget(self.url_input)

            # Connect Button
            self.btn_connect = QPushButton("Connect")
            self.btn_connect.clicked.connect(self.apply_server_url)
            bar_layout.addWidget(self.btn_connect)

            # Wake-on-LAN Button
            self.btn_wake = QPushButton("⚡ Wake AI PC")
            self.btn_wake.setObjectName("btnWake")
            self.btn_wake.clicked.connect(self.wake_server)
            bar_layout.addWidget(self.btn_wake)

            # Sidecar Toggle Button
            self.btn_sidecar = QPushButton("🖥️ Sidecar: OFF")
            self.btn_sidecar.setObjectName("btnSidecarInactive")
            self.btn_sidecar.clicked.connect(lambda: self.toggle_sidecar())
            bar_layout.addWidget(self.btn_sidecar)

            # Hikari CLI Button
            self.btn_terminal = QPushButton("💻 Terminal")
            self.btn_terminal.clicked.connect(self.launch_terminal)
            bar_layout.addWidget(self.btn_terminal)

            # Airi 3D Companion Button
            self.btn_airi = QPushButton("🎭 Airi 3D")
            self.btn_airi.clicked.connect(self.launch_airi)
            bar_layout.addWidget(self.btn_airi)

            # Refresh Button
            self.btn_refresh = QPushButton("🔄")
            self.btn_refresh.setToolTip("Reload webview (F5)")
            self.btn_refresh.clicked.connect(self.reload_webview)
            bar_layout.addWidget(self.btn_refresh)

            main_layout.addWidget(top_bar)

            # ── Main WebView ────────────────────────────────────────────────
            self.browser = QWebEngineView()
            self.browser.setPage(SilentPage(self.browser))
            self.browser.page().setBackgroundColor(QColor(9, 10, 16))
            self.load_server_ui()
            main_layout.addWidget(self.browser, stretch=1)

            # Shortcuts
            self.f5_shortcut = QShortcut(QKeySequence("F5"), self)
            self.f5_shortcut.activated.connect(self.reload_webview)

        def load_server_ui(self):
            target_url = f"{self.current_server}/static/app.html"
            self.browser.setUrl(QUrl(target_url))

        def reload_webview(self):
            self.browser.reload()

        def on_preset_changed(self, index):
            url_data = self.preset_combo.currentData()
            if url_data:
                self.url_input.setText(url_data)
                self.apply_server_url()

        def apply_server_url(self):
            new_url = self.url_input.text().strip().rstrip("/")
            if not new_url.startswith("http://") and not new_url.startswith("https://"):
                new_url = f"http://{new_url}"
            self.current_server = new_url
            set_server_url(new_url)
            self.load_server_ui()
            self.check_health_now()

            # Restart sidecar if active
            if self.sidecar_active:
                self.toggle_sidecar(force_state=False)
                self.toggle_sidecar(force_state=True)

        def check_health_now(self):
            h = check_server_health(self.current_server, timeout=2.0)
            if h.get("online"):
                lat = h.get("latency_ms", 0.0)
                self.status_pill.setText(f"● ONLINE ({lat}ms)")
                self.status_pill.setStyleSheet("background-color: #0d3826; color: #38ef7d; font-weight: bold;")
            else:
                self.status_pill.setText("○ OFFLINE")
                self.status_pill.setStyleSheet("background-color: #381a1a; color: #ff5252; font-weight: bold;")

        def start_health_timer(self):
            self.health_timer = QTimer(self)
            self.health_timer.setInterval(4000)
            self.health_timer.timeout.connect(self.check_health_now)
            self.health_timer.start()
            self.check_health_now()

        def toggle_sidecar(self, force_state: Optional[bool] = None):
            target = not self.sidecar_active if force_state is None else force_state
            if target:
                if self.sidecar_worker and self.sidecar_worker.is_alive():
                    self.sidecar_worker.stop()
                self.sidecar_worker = SidecarWorker(self.current_server)
                self.sidecar_worker.start()
                self.sidecar_active = True
                self.btn_sidecar.setText("🖥️ Sidecar: ACTIVE")
                self.btn_sidecar.setObjectName("btnSidecarActive")
                self.btn_sidecar.setStyle(self.btn_sidecar.style())
            else:
                if self.sidecar_worker:
                    self.sidecar_worker.stop()
                    self.sidecar_worker = None
                self.sidecar_active = False
                self.btn_sidecar.setText("🖥️ Sidecar: OFF")
                self.btn_sidecar.setObjectName("btnSidecarInactive")
                self.btn_sidecar.setStyle(self.btn_sidecar.style())

        def wake_server(self):
            ok = wake_server_wol()
            QMessageBox.information(
                self,
                "Wake-on-LAN Transmitted",
                f"UDP WoL magic packet sent to dedicated AI PC.\nReachability check running..."
            )
            QTimer.singleShot(2500, self.check_health_now)

        def launch_terminal(self):
            repo_root = Path(__file__).resolve().parent.parent
            bat_path = repo_root / "start_helios_client.bat"
            if sys.platform == "win32":
                os.system(f'start "" cmd /c "{bat_path}" cli')
            else:
                subprocess.Popen(["python", "-m", "helios-client.cli", "--server", self.current_server])

        def launch_airi(self):
            repo_root = Path(__file__).resolve().parent.parent
            airi_bat = repo_root / "start_airi.bat"
            if airi_bat.exists():
                os.system(f'start "" cmd /c "{airi_bat}"')
            else:
                webbrowser.open("http://localhost:8080?edition=full_spec")

        def closeEvent(self, event):
            if self.sidecar_worker:
                self.sidecar_worker.stop()
            event.accept()


def launch_desktop(server_url: Optional[str] = None):
    """Launch the client desktop GUI window."""
    if not HAS_PYQT:
        print("[!] PyQt5 / PyQtWebEngine not available. Launching default browser...")
        url = (server_url or get_server_url()).rstrip("/")
        webbrowser.open(f"{url}/static/app.html")
        return

    app = QApplication(sys.argv)
    window = HeliosClientWindow(initial_server=server_url)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    url_arg = sys.argv[1] if len(sys.argv) > 1 else None
    launch_desktop(url_arg)
