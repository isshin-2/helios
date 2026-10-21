import unittest
import os
import sys
from unittest.mock import patch, mock_open, MagicMock

# Ensure scripts directory is in path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class TestAutonomousOverlay(unittest.TestCase):
    @patch('scripts.autonomous_overlay.webview')
    def test_autonomous_overlay_main(self, mock_webview):
        import scripts.autonomous_overlay as auto_overlay
        
        mock_window = MagicMock()
        mock_webview.create_window.return_value = mock_window
        
        with patch('builtins.open', mock_open(read_data='<html>test overlay</html>')):
            auto_overlay.main()
            
            # Verify window creation parameters
            mock_webview.create_window.assert_called_once()
            args, kwargs = mock_webview.create_window.call_args
            assert args[0] == "HELIOS Autonomous Warning"
            assert kwargs.get("transparent") is True
            assert kwargs.get("frameless") is True
            assert kwargs.get("on_top") is True
            
            # Verify webview start was called
            mock_webview.start.assert_called_once()

    @patch('scripts.autonomous_overlay.win32gui', create=True)
    def test_enforce_topmost(self, mock_win32gui):
        import scripts.autonomous_overlay as auto_overlay
        with patch.dict('sys.modules', {'win32gui': mock_win32gui, 'win32con': MagicMock()}):
            mock_win32gui.FindWindowEx.return_value = 12345
            auto_overlay.enforce_topmost("HELIOS Autonomous Warning")
            mock_win32gui.SetWindowPos.assert_called_once()

if __name__ == "__main__":
    unittest.main()

