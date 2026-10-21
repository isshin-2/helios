import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the root directory to sys.path so we can import overlays
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

@patch('overlays.tensura_popup.webview')
def test_tensura_popup_initialization(mock_webview):
    from overlays.tensura_popup import get_user_input
    
    mock_window = MagicMock()
    mock_webview.create_window.return_value = mock_window
    
    # Run get_user_input with mocked webview
    result = get_user_input("Are you the Storm Dragon Veldora?", options=["Yes", "No"])
    
    # Verify create_window was called with expected title and properties
    mock_webview.create_window.assert_called_once()
    args, kwargs = mock_webview.create_window.call_args
    assert args[0] == 'HELIOS - Question'
    assert kwargs.get('transparent') is True
    assert kwargs.get('frameless') is True
    assert kwargs.get('on_top') is True
    
    # Verify webview.start was called
    mock_webview.start.assert_called_once_with(gui="edgechromium")
    
    # Should default to "CANCELLED" when no result was submitted
    assert result == "CANCELLED"

