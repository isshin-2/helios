import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from main import app, get_db

@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

@pytest.fixture
def test_user():
    conn = get_db()
    cursor = conn.cursor()
    from security.permissions import HELIOS_DIR
    import json
    access = {
        "file_read": {"enabled": True, "paths": [HELIOS_DIR]},
        "file_write": {"enabled": True, "paths": [HELIOS_DIR]},
        "directory_list": {"enabled": True, "paths": [HELIOS_DIR]},
        "terminal": {"enabled": True, "commands": ["python", "echo"]}
    }
    cursor.execute("INSERT OR IGNORE INTO users (id, username, system_access) VALUES (?, ?, ?)", 
                   (999, "test_headless_user", json.dumps(access)))
    conn.commit()
    
    # create a session
    cursor.execute("INSERT OR IGNORE INTO sessions (id, user_id, title) VALUES (?, ?, ?)",
                   (999, 999, "Headless Test"))
    conn.commit()
    conn.close()
    
    yield 999
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE id = 999")
    cursor.execute("DELETE FROM users WHERE id = 999")
    conn.commit()
    conn.close()

@pytest.mark.asyncio
async def test_headless_api_success(async_client, test_user, mock_model_manager):
    payload = {
        "user_id": test_user,
        "session_id": 999,
        "message": "Hello HELIOS"
    }
    
    response = await async_client.post("/api/chat/headless", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "success"
    assert "response" in data
    assert isinstance(data["tools_used"], list)
    
@pytest.mark.asyncio
async def test_headless_api_missing_fields(async_client):
    payload = {
        "user_id": 999
        # missing session_id and message
    }
    
    response = await async_client.post("/api/chat/headless", json=payload)
    assert response.status_code == 422 # validation error

@pytest.fixture
def mock_model_manager():
    # Use patch to replace the real execute_request with a mock async generator function
    with patch("main.manager.execute_request") as mock_exec:
        async def mock_execute_request(messages, *args, **kwargs):
            # Check all messages for user intent
            user_msgs_indices = [i for i, m in enumerate(messages) if m.get("role") == "user"]
            last_user_idx = user_msgs_indices[-1] if user_msgs_indices else 0
            initial_content = messages[last_user_idx].get("content", "") if user_msgs_indices else ""
            
            # Count how many tool responses have been appended in this current run
            tool_msgs_since = sum(1 for m in messages[last_user_idx:] if m.get("role") == "tool")
            
            def create_tool_chunk(name, kwargs_dict):
                return {"message": {"content": "", "tool_calls": [{"function": {"name": name, "arguments": kwargs_dict}}]}}
                
            def create_msg_chunk(msg_content):
                return {"message": {"content": msg_content}}
            
            # Simple simulation for agentic loop test
            if "List the directory contents" in initial_content:
                if tool_msgs_since == 0:
                    yield create_tool_chunk("DirectoryListerTool", {"directory_path": "."})
                elif tool_msgs_since == 1:
                    yield create_tool_chunk("FileReaderTool", {"file_path": "main.py"})
                else:
                    yield create_msg_chunk("The FastAPI app variable is named app.")
            
            # Simple simulation for headless denial test
            elif "Write the text" in initial_content:
                if tool_msgs_since == 0:
                    yield create_tool_chunk("FileWriterTool", {"file_path": "hack.txt", "content": "hack"})
                else:
                    yield create_msg_chunk("[Action blocked pending approval: user denied]")
                    
            # Default response
            else:
                yield create_msg_chunk("Mocked response")
            
        mock_exec.side_effect = mock_execute_request
        yield mock_exec

@pytest.mark.asyncio
async def test_headless_agentic_loop(async_client, test_user, mock_model_manager):
    # Test a multi-step agentic loop
    payload = {
        "user_id": test_user,
        "session_id": 999,
        "message": "List the directory contents, then read the file 'main.py' and tell me the name of the FastAPI app variable."
    }
    
    response = await async_client.post("/api/chat/headless", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "success"
    
    # It should have used at least the directory lister and file reader tools
    tools_used = data.get("tools_used", [])
    assert len(tools_used) >= 2, "Agent should have chained at least two tools"
    
    # We should see evidence of the final answer based on the read file
    response_text = data.get("response", "").lower()
    assert "app" in response_text

@pytest.mark.asyncio
async def test_headless_approval_denial(async_client, test_user, mock_model_manager):
    # Test that a write operation requiring approval is immediately denied in headless mode
    payload = {
        "user_id": test_user,
        "session_id": 999,
        "message": "Write the text 'hack' to a new file called 'hack.txt' in the current directory."
    }
    
    response = await async_client.post("/api/chat/headless", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "success"
    
    # We should see the approval request in the tool activity and blocked action
    tools_used = data.get("tools_used", [])
    assert any("Requires Approval" in t for t in tools_used)
    
    response_text = data.get("response", "")
    assert "[Action blocked pending approval:" in response_text
