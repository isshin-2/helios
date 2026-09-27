import unittest
import os
import sys
from unittest.mock import patch, MagicMock

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class TestVoiceOverlayWebview(unittest.TestCase):
    @patch('voice.overlay_webview.webview')
    @patch('voice.overlay_webview.ctypes')
    def test_voice_overlay_main(self, mock_ctypes, mock_webview):
        # Mock window resolution
        mock_user32 = MagicMock()
        mock_user32.GetSystemMetrics.side_effect = lambda x: 1920 if x == 0 else 1080
        mock_ctypes.windll.user32 = mock_user32
        
        # Mock webview window
        mock_window = MagicMock()
        mock_webview.create_window.return_value = mock_window
        
        import voice.overlay_webview as voice_overlay
        
        with patch('threading.Thread'), patch('builtins.open'):
            voice_overlay.main()
            
            # Verify DPI awareness
            mock_ctypes.windll.shcore.SetProcessDpiAwareness.assert_called_once_with(1)
            
            # Verify webview window settings (Magenta keying)
            mock_webview.create_window.assert_called_once()
            args, kwargs = mock_webview.create_window.call_args
            
            self.assertEqual(args[0], 'HELIOS Listening')
            # In voice overlay, transparent is False and background is Magenta
            self.assertFalse(kwargs['transparent'])
            self.assertEqual(kwargs['background_color'], '#FF00FF')
            self.assertTrue(kwargs['frameless'])
            self.assertTrue(kwargs['on_top'])
            
            mock_webview.start.assert_called_once()

if __name__ == "__main__":
    unittest.main()
