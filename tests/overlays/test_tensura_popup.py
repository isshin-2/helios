import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the root directory to sys.path so we can import overlays
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

@pytest.fixture
def mock_tk():
    with patch('tkinter.Tk') as mock_tk_class:
        # Create a mock root window
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        
        # We need to mock winfo_screenwidth etc if they are called
        mock_root.winfo_screenwidth.return_value = 1920
        mock_root.winfo_screenheight.return_value = 1080
        
        yield mock_root

def test_tensura_popup_initialization(mock_tk):
    from overlays.tensura_popup import get_user_input
    
    # Run the function. Because we mocked Tk(), it won't actually block!
    # Wait, get_user_input calls root.mainloop(). Since root is a MagicMock, mainloop() does nothing!
    result = get_user_input("Are you the Storm Dragon Veldora?", options=["Yes", "No"])
    
    # Verify the window properties were set for Tensura style
    mock_tk.title.assert_called_with("HELIOS: System Notice")
    mock_tk.attributes.assert_any_call("-fullscreen", True)
    mock_tk.attributes.assert_any_call("-alpha", 0.90)
    mock_tk.configure.assert_called()
    
    # It should return None because we didn't mock a button click event
    assert result is None
