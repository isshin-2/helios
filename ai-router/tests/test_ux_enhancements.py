import pytest
import sys
import os

# Ensure ai-router root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.audio_chimes import AudioChimeEngine, chime_engine
from scripts.autonomous_overlay import get_target_monitor_bounds

def test_audio_chime_engine_initialization():
    engine = AudioChimeEngine(enabled=False)
    assert engine is not None
    assert engine.enabled is False
    # Test playing chime when disabled does not raise
    engine.play_chime("thinking")
    engine.play_chime("complete")
    engine.play_chime("abort")

def test_target_monitor_bounds_detection():
    x, y, w, h = get_target_monitor_bounds()
    assert isinstance(x, int)
    assert isinstance(y, int)
    assert isinstance(w, int)
    assert isinstance(h, int)
    assert w > 0
    assert h > 0

def test_system_tray_icon_generation():
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from core.system_tray import create_status_icon, HeliosSystemTray
    
    icon = create_status_icon("#00E5FF")
    assert icon is not None
    assert not icon.isNull()
