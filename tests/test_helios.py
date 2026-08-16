import pytest
import asyncio
from pydantic import BaseModel
from unittest.mock import AsyncMock, MagicMock, patch

from router.classifier import classify_request
from router.rules import get_routing_decision
from security.permissions import PermissionManager
from tools.terminal import TerminalTool
from tools.subagent import SubAgentTool
from core.events import EventBus

# ─── ROUTER TESTS ───────────────────────────────────────────────────────────

def test_classifier_intent():
    # Test simple intent
    flags = classify_request([{"role": "user", "content": "hi there"}])
    assert flags["intent"] == "conversation"
    
    # Test coding intent
    flags = classify_request([{"role": "user", "content": "can you write a python script to parse json?"}])
    assert flags["intent"] == "coding"
    
def test_routing_decision():
    # Reasoning intent should route to reasoning model
    flags = {"intent": "reasoning", "detail": "normal", "requires_tools": False, "requires_reasoning": True, "requires_vision": False, "requires_research": False}
    decision = get_routing_decision(flags)
    assert decision["route"] == "reasoning"
    
    # Coding should use coding model
    flags = {"intent": "coding", "detail": "detailed", "requires_tools": False, "requires_reasoning": False, "requires_vision": False, "requires_research": False}
    decision = get_routing_decision(flags)
    assert decision["route"] == "coding"
    assert "coder" in decision["model"]

# ─── PERMISSION TESTS ───────────────────────────────────────────────────────

@patch("security.permissions.get_db")
def test_terminal_sandbox(mock_get_db):
    # Mock DB so it doesn't try to save
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    pm = PermissionManager()
    user_id = 1
    
    # Mock _get_user_access directly
    pm._get_user_access = MagicMock(return_value={
        "locations": [{"path": "/tmp/allowed", "read": True, "write": True, "exec": True}],
        "file_read": {"enabled": True, "paths": ["/tmp/allowed"]},
        "file_write": {"enabled": True, "paths": ["/tmp/allowed"]},
        "directory_list": {"enabled": True, "paths": ["/tmp/allowed"]},
        "terminal": {
            "enabled": True,
            "commands": ["git", "python"]
        }
    })
    
    # Allowed command
    res = pm.can_execute(user_id, "git", ["status"], "/tmp/allowed")
    assert res.allowed == True
    
    # Blocked command (not in allowlist)
    res = pm.can_execute(user_id, "rm", ["-rf", "/"], "/tmp/allowed")
    assert res.allowed == False
    assert "blocked" in res.reason.lower()
    
    # Blocked directory
    res = pm.can_execute(user_id, "git", ["status"], "/root")
    assert res.allowed == False

# ─── EVENT BUS TESTS ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_event_bus():
    bus = EventBus()
    received = []
    
    async def handler(data):
        received.append(data)
        
    bus.subscribe("test_event", handler)
    await bus.publish("test_event", {"msg": "hello"})
    
    # Give the task loop a tiny bit of time
    await asyncio.sleep(0.01)
    
    assert len(received) == 1
    assert received[0]["msg"] == "hello"

# ─── SUB-AGENT TESTS ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_subagent_tool():
    mock_provider = AsyncMock()
    mock_provider.chat.return_value = {"message": {"content": "42"}}
    
    tool = SubAgentTool(provider=mock_provider)
    result_text, tool_name = await tool.execute(user_id=1, task="what is the answer?", budget=5)
    
    assert tool_name == "SubAgentTool"
    assert "42" in result_text
    mock_provider.chat.assert_called_once()
