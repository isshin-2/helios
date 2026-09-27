"""Tests for the gateway package."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from gateway.tool_gateway import ToolGateway
from gateway.host_gateway import HostGateway

@pytest.mark.asyncio
class TestToolGateway:
    async def test_get_all_schemas(self):
        mock_router = MagicMock()
        mock_router.get_tool_schemas.return_value = [{"type": "function", "function": {"name": "local_tool"}}]
        
        mock_mcp = AsyncMock()
        mock_mcp.list_all_tools.return_value = [{"name": "mcp_server__mcp_tool", "description": "desc", "inputSchema": {}}]
        
        gateway = ToolGateway(mock_router, mock_mcp)
        schemas = await gateway.get_all_schemas()
        
        assert len(schemas) == 2
        assert schemas[0]["function"]["name"] == "local_tool"
        assert schemas[1]["function"]["name"] == "mcp_server__mcp_tool"

    async def test_execute_local_tool(self):
        mock_router = AsyncMock()
        mock_router.execute.return_value = ("local result", "local_tool")
        
        mock_mcp = AsyncMock()
        
        gateway = ToolGateway(mock_router, mock_mcp)
        result, name = await gateway.execute_tool("local_tool", 1, {"arg": "val"})
        
        assert result == "local result"
        assert name == "local_tool"
        mock_router.execute.assert_called_once_with("local_tool", 1, arg="val")
        mock_mcp.call_tool.assert_not_called()

    async def test_execute_mcp_tool(self):
        mock_router = AsyncMock()
        mock_mcp = AsyncMock()
        mock_mcp.call_tool.return_value = "mcp result"
        
        gateway = ToolGateway(mock_router, mock_mcp)
        result, name = await gateway.execute_tool("mcp_server__mcp_tool", 1, {"arg": "val"})
        
        assert result == "mcp result"
        assert name == "mcp_server__mcp_tool"
        mock_mcp.call_tool.assert_called_once_with("mcp_server__mcp_tool", {"arg": "val"})
        mock_router.execute.assert_not_called()

class TestHostGateway:
    def test_is_path_allowed(self):
        mock_perms = MagicMock()
        mock_perms.validate_path_access.return_value = True
        
        gateway = HostGateway(mock_perms, use_docker_sandbox=False)
        assert gateway.is_path_allowed("C:/test") is True
        mock_perms.validate_path_access.assert_called_once()
        
    @patch("gateway.host_gateway.SandboxManager")
    def test_execute_in_sandbox(self, mock_sandbox_class):
        mock_sandbox = MagicMock()
        mock_sandbox.create_sandbox.return_value = "sand-123"
        mock_sandbox.execute.return_value = (0, "output", "")
        mock_sandbox_class.return_value = mock_sandbox
        
        gateway = HostGateway(MagicMock(), use_docker_sandbox=False)
        code, out, err = gateway.execute_in_sandbox("echo test")
        
        assert code == 0
        assert out == "output"
        mock_sandbox.create_sandbox.assert_called_once()
        mock_sandbox.execute.assert_called_once_with("sand-123", "echo test", 60)
        mock_sandbox.destroy_sandbox.assert_called_once_with("sand-123")
