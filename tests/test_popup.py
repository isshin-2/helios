import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from tools.interactive import AskUserTool, AskUserSchema

@pytest.fixture
def permission_manager_mock():
    return MagicMock()

@pytest.mark.asyncio
async def test_ask_user_tool_returns_user_input(permission_manager_mock):
    """Test that AskUserTool successfully parses and returns the user's input from the popup."""
    tool = AskUserTool(permission_manager_mock)
    
    # Mock the asyncio.create_subprocess_exec to simulate user clicking a button
    mock_process = MagicMock()
    mock_process.communicate = AsyncMock(return_value=(b"Confirmed\n", b""))
    
    with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
        result, name = await tool.execute(
            user_id=1, 
            question="Proceed?", 
            options=["Confirmed", "Denied"]
        )
        
        assert name == "AskUserTool"
        assert result == "User replied: Confirmed"
        
        # Verify it passed the right args to the subprocess
        mock_exec.assert_called_once()
        args = mock_exec.call_args[0]
        assert "tensura_popup.py" in args[1]
        assert args[2] == "Proceed?"
        assert args[3] == "Confirmed,Denied"

@pytest.mark.asyncio
async def test_ask_user_tool_handles_cancellation(permission_manager_mock):
    """Test that AskUserTool correctly handles the user pressing Esc (CANCELLED)."""
    tool = AskUserTool(permission_manager_mock)
    
    mock_process = MagicMock()
    mock_process.communicate = AsyncMock(return_value=(b"CANCELLED\n", b""))
    
    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        result, _ = await tool.execute(user_id=1, question="Proceed?")
        
        assert result == "User cancelled the prompt or provided no input."

@pytest.mark.asyncio
async def test_ask_user_tool_handles_empty_input(permission_manager_mock):
    """Test that AskUserTool handles empty responses (e.g. user just hits enter with no text)."""
    tool = AskUserTool(permission_manager_mock)
    
    mock_process = MagicMock()
    mock_process.communicate = AsyncMock(return_value=(b"", b""))
    
    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        result, _ = await tool.execute(user_id=1, question="Proceed?")
        
        assert result == "User cancelled the prompt or provided no input."

@pytest.mark.asyncio
async def test_ask_user_tool_schema_validation():
    """Test that the AskUserSchema validates inputs correctly."""
    # Valid input with options
    data = {"question": "Which one?", "options": ["A", "B"]}
    schema = AskUserSchema(**data)
    assert schema.question == "Which one?"
    assert schema.options == ["A", "B"]
    
    # Valid input without options
    data_no_options = {"question": "What is your name?"}
    schema_no_options = AskUserSchema(**data_no_options)
    assert schema_no_options.options is None

