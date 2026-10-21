"""
HELIOS — Ambient System Tray Engine
Provides real-time AI-PC cluster status, quick links, and system controls in the Windows taskbar.
Runs non-blocking via PyQt5.
"""

import sys
import os
import logging
from typing import Optional
from PyQt5.QtCore import QTimer, QUrl
from PyQt5.QtGui import QIcon, QPixmap, QColor, QPainter, QBrush
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QDesktopServices

logger = logging.getLogger("helios.system_tray")

def create_status_icon(color_hex: str) -> QIcon:
    """Generates a small circular glowing tray icon dynamically."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # Outer ambient glow
    painter.setBrush(QBrush(QColor(color_hex)))
    painter.setPen(QColor(color_hex))
    painter.setOpacity(0.35)
    painter.drawEllipse(2, 2, 28, 28)
    
    # Inner solid cyber core
    painter.setOpacity(1.0)
    painter.drawEllipse(6, 6, 20, 20)
    painter.end()
    
    return QIcon(pixmap)

class HeliosSystemTray:
    """Ambient System Tray component for HELIOS."""

    def __init__(self, app: Optional[QApplication] = None, router_port: int = 8000):
        self.app = app or QApplication.instance() or QApplication(sys.argv)
        self.router_port = router_port
        self.tray = QSystemTrayIcon()
        
        self.cluster_online = False
        self._init_ui()
        self._start_poll_timer()

    def _init_ui(self):
        self.tray.setIcon(create_status_icon("#00E5FF"))  # Default Cyan
        self.tray.setToolTip("HELIOS — AI Operating Environment (Active)")

        menu = QMenu()

        # Status Title Action
        self.status_action = QAction("⚡ Cluster: Local Host (Standby)", menu)
        self.status_action.setEnabled(False)
        menu.addAction(self.status_action)
        menu.addSeparator()

        # Navigation Shortcuts
        act_open_site = QAction("🌐 Open HELIOS Web Studio (:8000)", menu)
        act_open_site.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(f"http://127.0.0.1:{self.router_port}/static/app.html")))
        menu.addAction(act_open_site)

        act_open_holodeck = QAction("🎭 Open Solstice 3D Holodeck (:8080)", menu)
        act_open_holodeck.triggered.connect(lambda: QDesktopServices.openUrl(QUrl("http://127.0.0.1:8080/")))
        menu.addAction(act_open_holodeck)

        act_open_site_portal = QAction("🚀 Open Sovereign Site (:5175)", menu)
        act_open_site_portal.triggered.connect(lambda: QDesktopServices.openUrl(QUrl("http://localhost:5175/")))
        menu.addAction(act_open_site_portal)

        menu.addSeparator()

        # Emergency Stop / Safety Action
        act_emergency = QAction("🛑 Emergency Abort (Release Input)", menu)
        act_emergency.triggered.connect(self._trigger_emergency_stop)
        menu.addAction(act_emergency)

        menu.addSeparator()

        # Exit
        act_exit = QAction("❌ Close Tray", menu)
        act_exit.triggered.connect(self.tray.hide)
        menu.addAction(act_exit)

        self.tray.setContextMenu(menu)
        self.tray.show()

    def _trigger_emergency_stop(self):
        try:
            from computer.controller import computer_controller
            computer_controller.stop("User requested abort via System Tray")
            self.tray.showMessage("HELIOS Safety", "Emergency stop triggered. Control returned to user.", QSystemTrayIcon.Warning, 2000)
        except Exception as e:
            logger.debug(f"Failed to trigger stop: {e}")

    def update_cluster_status(self, is_remote_ai_pc: bool):
        self.cluster_online = is_remote_ai_pc
        if is_remote_ai_pc:
            self.status_action.setText("⚡ Cluster: NVIDIA AI-PC GPU (RTX 5060 Ti)")
            self.tray.setIcon(create_status_icon("#00E5FF"))  # Electric Cyan
            self.tray.setToolTip("HELIOS — Connected to NVIDIA AI-PC GPU Node")
        else:
            self.status_action.setText("⚡ Cluster: Local Host Fallback (Active)")
            self.tray.setIcon(create_status_icon("#FF9900"))  # Amber
            self.tray.setToolTip("HELIOS — Local Host Fallback Mode")

    def _start_poll_timer(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self._check_cluster)
        self.timer.start(10000)  # Check every 10 seconds

    def _check_cluster(self):
        try:
            from core.ai_pc_manager import is_ai_pc_reachable
            reachable = is_ai_pc_reachable(timeout=0.8)
            self.update_cluster_status(reachable)
        except Exception:
            pass

if __name__ == "__main__":
    app = QApplication(sys.argv)
    tray = HeliosSystemTray(app)
    print("HELIOS Ambient System Tray running.")
    sys.exit(app.exec_())
