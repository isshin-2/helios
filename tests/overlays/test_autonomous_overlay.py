import unittest
import os
import sys
from unittest.mock import patch, mock_open, MagicMock

# Ensure scripts directory is in path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class TestAutonomousOverlay(unittest.TestCase):
    @patch('scripts.autonomous_overlay.tk')
    @patch('scripts.autonomous_overlay.os.path.exists')
    def test_autonomous_overlay_state_check(self, mock_exists, mock_tk):
        import scripts.autonomous_overlay as auto_overlay
        
        # Setup mocks
        mock_root = MagicMock()
        mock_label = MagicMock()
        
        # Test state = 1 (Show)
        mock_exists.return_value = True
        with patch('builtins.open', mock_open(read_data='1')):
            auto_overlay.check_state(mock_root, mock_label)
            
            mock_root.deiconify.assert_called_once()
            mock_root.attributes.assert_called_with("-topmost", True)
            
        mock_root.reset_mock()
        
        # Test state = 0 (Hide)
        with patch('builtins.open', mock_open(read_data='0')):
            auto_overlay.check_state(mock_root, mock_label)
            
            mock_root.withdraw.assert_called_once()
            
        # Verify it schedules the next check
        mock_root.after.assert_called_with(200, auto_overlay.check_state, mock_root, mock_label)

    @patch('scripts.autonomous_overlay.tk')
    def test_autonomous_overlay_main(self, mock_tk):
        import scripts.autonomous_overlay as auto_overlay
        
        mock_root = MagicMock()
        mock_tk.Tk.return_value = mock_root
        
        with patch('builtins.open', mock_open()):
            auto_overlay.main()
            
            # Verify window configuration
            mock_root.overrideredirect.assert_called_with(True)
            mock_root.attributes.assert_any_call("-topmost", True)
            mock_root.attributes.assert_any_call("-alpha", 0.9)
            
            # Verify UI elements were created
            mock_tk.Label.assert_called_once()
            
            # Verify initial state is hidden and written to file
            mock_root.withdraw.assert_called()
            mock_root.mainloop.assert_called_once()

if __name__ == "__main__":
    unittest.main()
