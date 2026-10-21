import pytest
import os
import sys
from pathlib import Path

# Setup paths
AI_ROUTER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROUTER_DIR))

from core.tool_router import ToolRouter
from security.permissions import PermissionManager
from health.monitor import SystemMonitor

@pytest.fixture
def tool_router():
    pm = PermissionManager()
    mon = SystemMonitor(None)
    return ToolRouter(None, mon, pm)

def test_tool_router_schemas_and_aliases(tool_router):
    schemas = tool_router.get_tool_schemas()
    schema_names = [s["function"]["name"] for s in schemas]

    # Verify essential assistant tools exist in canonical schemas
    assert "git_ops" in schema_names
    assert "process_monitor" in schema_names
    assert "http_client" in schema_names
    assert "env_secrets" in schema_names
    assert "reverse_engineer" in schema_names

    # Verify alias mappings in tool dictionary
    assert "FileReaderTool" in tool_router.tools
    assert "file_reader" in tool_router.tools
    assert tool_router.tools["FileReaderTool"] is tool_router.tools["file_reader"]

    assert "FileWriterTool" in tool_router.tools
    assert "file_writer" in tool_router.tools
    assert tool_router.tools["FileWriterTool"] is tool_router.tools["file_writer"]

    assert "TerminalTool" in tool_router.tools
    assert "terminal" in tool_router.tools
    assert tool_router.tools["TerminalTool"] is tool_router.tools["terminal"]

    assert "StatefulShellTool" in tool_router.tools
    assert "stateful_shell" in tool_router.tools
    assert tool_router.tools["StatefulShellTool"] is tool_router.tools["stateful_shell"]

    assert "ReverseEngineerTool" in tool_router.tools
    assert "reverse_engineer" in tool_router.tools
    assert "rea" in tool_router.tools

@pytest.mark.asyncio
async def test_git_ops_tool(tool_router):
    result, tool_name = await tool_router.execute("git_ops", user_id=1, action="status")
    assert tool_name in ("git_ops", "GitOpsTool")
    assert isinstance(result, str)
    assert len(result) > 0

@pytest.mark.asyncio
async def test_process_monitor_tool(tool_router):
    result, tool_name = await tool_router.execute("process_monitor", user_id=1, action="system_stats")
    assert tool_name in ("process_monitor", "ProcessMonitorTool")
    assert "System Resource Status" in result
    assert "CPU Usage" in result
    assert "RAM Usage" in result

@pytest.mark.asyncio
async def test_env_secrets_tool(tool_router):
    result, tool_name = await tool_router.execute("env_secrets", user_id=1, show_keys_only=True)
    assert tool_name in ("env_secrets", "EnvSecretsTool")
    assert "Configuration Keys" in result

@pytest.mark.asyncio
async def test_reverse_engineer_knowledge(tool_router):
    result, tool_name = await tool_router.execute("reverse_engineer", user_id=1, action="rea_knowledge", topic="ghidra")
    assert tool_name in ("reverse_engineer", "ReverseEngineerTool")
    assert "Ghidra Decompilation Workflow" in result

@pytest.mark.asyncio
async def test_reverse_engineer_binary(tool_router):
    target = os.environ.get("COMSPEC", "C:\\Windows\\System32\\cmd.exe")
    result, tool_name = await tool_router.execute("reverse_engineer", user_id=1, action="inspect_binary", file_path=target)
    assert tool_name in ("reverse_engineer", "ReverseEngineerTool")
    assert "REA Binary Inspection" in result
    assert "Windows PE" in result
