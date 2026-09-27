"""
HELIOS — Tool Gateway
Provides a unified interface for routing tool calls to built-in tools, MCP tools,
or external services.
"""

import logging
from typing import Dict, Any, List, Tuple
from core.tool_router import ToolRouter
from core.mcp_client import MCPManager

logger = logging.getLogger("helios.gateway.tools")

class ToolGateway:
    """
    Unified entry point for all tool executions.
    Routes to the old ToolRouter for local built-ins or MCPManager for MCP tools.
    """
    def __init__(self, tool_router: ToolRouter, mcp_manager: MCPManager):
        self.tool_router = tool_router
        self.mcp_manager = mcp_manager

    async def get_all_schemas(self) -> List[Dict[str, Any]]:
        """Combine schemas from local tools and all MCP servers."""
        schemas = self.tool_router.get_tool_schemas()
        
        try:
            mcp_tools = await self.mcp_manager.list_all_tools()
            for tool in mcp_tools:
                schemas.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["inputSchema"]
                    }
                })
        except Exception as e:
            logger.error(f"Failed to fetch MCP tools: {e}")
            
        return schemas

    async def execute_tool(self, tool_name: str, user_id: int, arguments: Dict[str, Any]) -> Tuple[str, str]:
        """
        Routes the tool call to the correct handler based on the tool name prefix.
        MCP tools are registered with `{server_name}__{tool_name}`.
        Returns (result, tool_name).
        """
        if "__" in tool_name:
            # It's an MCP tool
            try:
                result = await self.mcp_manager.call_tool(tool_name, arguments)
                return result, tool_name
            except Exception as e:
                logger.error(f"MCP tool execution failed: {e}")
                return f"Error: MCP tool {tool_name} failed: {e}", tool_name
        else:
            # It's a local built-in tool
            return await self.tool_router.execute(tool_name, user_id, **arguments)
