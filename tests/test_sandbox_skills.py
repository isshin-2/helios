import pytest
import os
import asyncio
from pathlib import Path

from security.permissions import PermissionManager, HELIOS_DIR
from tools.filesystem import FileReaderTool, FileWriterTool, DirectoryListerTool
from tools.terminal import TerminalTool
from db import get_db

@pytest.fixture
def test_user():
    conn = get_db()
    cursor = conn.cursor()
    # Ensure test user exists with broad system access for testing boundaries
    access = {
        "file_read": {"enabled": True, "paths": [HELIOS_DIR]},
        "file_write": {"enabled": True, "paths": [HELIOS_DIR]},
        "directory_list": {"enabled": True, "paths": [HELIOS_DIR]},
        "terminal": {"enabled": True, "commands": ["python", "python3", "echo", "cmd"]}
    }
    import json
    cursor.execute("INSERT OR REPLACE INTO users (id, username, system_access) VALUES (?, ?, ?)", 
                   (999, "test_sandbox_user", json.dumps(access)))
    conn.commit()
    conn.close()
    
    yield 999
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = 999")
    conn.commit()
    conn.close()

@pytest.fixture
def permission_manager():
    return PermissionManager()

@pytest.mark.asyncio
async def test_file_reader_tool(permission_manager, test_user, tmp_path):
    tool_inst = FileReaderTool(permission_manager)
    
    test_file = Path(HELIOS_DIR) / "test_read.txt"
    test_file.write_text("Hello HELIOS")
    
    try:
        # 1. Read existing file
        result, tool_name = await tool_inst.execute(user_id=test_user, file_path=test_file.name, working_directory=HELIOS_DIR)
        assert tool_name == "FileReaderTool"
        assert "Hello HELIOS" in result
        
        # 2. Read non-existent file
        result2, _ = await tool_inst.execute(user_id=test_user, file_path="does_not_exist.txt", working_directory=HELIOS_DIR)
        assert "not found" in result2.lower()
        
        # 3. Path traversal attempt
        result3, _ = await tool_inst.execute(user_id=test_user, file_path="../../../windows/system32/cmd.exe", working_directory=HELIOS_DIR)
        assert "denied" in result3.lower() or "not inside any approved location" in result3.lower()
        
    finally:
        if test_file.exists():
            test_file.unlink()

@pytest.mark.asyncio
async def test_file_writer_tool(permission_manager, test_user):
    tool_inst = FileWriterTool(permission_manager)
    
    # 1. Write file
    test_file = "test_write.txt"
    
    # Execute should return APPROVAL_REQUIRED, not write it directly
    result, tool_name = await tool_inst.execute(user_id=test_user, file_path=test_file, content="Test content", working_directory=HELIOS_DIR)
    assert tool_name == "FileWriterTool"
    assert "APPROVAL_REQUIRED::file_write::" in result
    
    # Now simulate approval being granted and perform_write being called
    full_path = Path(HELIOS_DIR) / test_file
    try:
        write_res, _ = await tool_inst.perform_write(str(full_path), "Test content", test_user)
        assert "Successfully wrote" in write_res
        assert full_path.read_text() == "Test content"
    finally:
        if full_path.exists():
            full_path.unlink()

@pytest.mark.asyncio
async def test_directory_lister_tool(permission_manager, test_user):
    tool_inst = DirectoryListerTool(permission_manager)
    
    # 1. List directory
    result, tool_name = await tool_inst.execute(user_id=test_user, directory_path=".", working_directory=HELIOS_DIR)
    assert tool_name == "DirectoryListerTool"
    assert "📁" in result or "📄" in result
    assert "__pycache__" not in result # should be filtered
    
@pytest.mark.asyncio
async def test_terminal_tool(permission_manager, test_user):
    tool_inst = TerminalTool(permission_manager)
    
    test_script = Path(HELIOS_DIR) / "test_dummy.py"
    test_script.write_text("print('hello')")
    try:
        # 1. Execute a non-privileged allowed command
        result2, tool_name2 = await tool_inst.execute(user_id=test_user, command=f"python {test_script.name}", working_directory=HELIOS_DIR)
        assert tool_name2 == "TerminalTool"
        assert "APPROVAL_REQUIRED::execute::python" in result2
        
        # 2. Blocked command execution attempt
        result3, _ = await tool_inst.execute(user_id=test_user, command="bash", working_directory=HELIOS_DIR)
        assert "denied" in result3.lower() or "blocked" in result3.lower()
        
        # 3. Dangerous python flag attempt
        result4, _ = await tool_inst.execute(user_id=test_user, command="python -c 'print(1)'", working_directory=HELIOS_DIR)
        assert "denied" in result4.lower() or "blocked" in result4.lower()
    finally:
        if test_script.exists():
            test_script.unlink()
