import unittest
import os
import sys
from unittest.mock import patch, MagicMock

# Ensure scripts directory is in path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class TestUIOverlay(unittest.TestCase):
    @patch('scripts.ui_overlay.webview')
    @patch('scripts.ui_overlay.ctypes')
    def test_ui_overlay_main(self, mock_ctypes, mock_webview):
        # Mock window resolution
        mock_user32 = MagicMock()
        mock_user32.GetSystemMetrics.side_effect = lambda x: 1920 if x == 0 else 1080
        mock_ctypes.windll.user32 = mock_user32
        
        # Mock webview window
        mock_window = MagicMock()
        mock_webview.create_window.return_value = mock_window
        
        # Import after mocking to avoid issues if run on headless
        import scripts.ui_overlay as ui_overlay
        
        # We don't want to actually start the infinite thread or webview loop in tests
        # Instead, we just verify the window creation logic
        
        with patch('threading.Thread'):
            ui_overlay.main()
            
            # Verify DPI awareness was attempted
            mock_ctypes.windll.shcore.SetProcessDpiAwareness.assert_called_once_with(1)
            
            # Verify webview was configured correctly
            mock_webview.create_window.assert_called_once()
            args, kwargs = mock_webview.create_window.call_args
            
            self.assertEqual(args[0], 'HELIOS Listening')
            self.assertTrue(kwargs['transparent'])
            self.assertTrue(kwargs['frameless'])
            self.assertTrue(kwargs['on_top'])
            
            mock_webview.start.assert_called_once()

if __name__ == "__main__":
    unittest.main()
