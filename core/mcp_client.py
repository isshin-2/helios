import logging
import asyncio
from typing import Dict, Any, List, Optional
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
import mcp.types as types

logger = logging.getLogger(__name__)

class MCPManager:
    """
    Manages connections to local MCP (Model Context Protocol) servers via Stdio.
    Follows a zero-trust model by spawning servers as strict subprocesses.
    """
    
    def __init__(self):
        # A dictionary to hold the server sessions
        # For a full implementation, we'd need to manage the lifecycle contexts.
        # Here we'll wrap a single server for simplicity or extend to multiple.
        self.servers = {}
    
    async def connect_server(self, server_name: str, command: str, args: List[str]):
        """
        Connects to a single MCP server via Stdio.
        Since stdio_client yields context managers, we run the session loop in a task.
        """
        logger.info(f"Connecting to MCP server '{server_name}'...")
        server_params = StdioServerParameters(command=command, args=args)
        
        # We start this in a background task to keep the session alive
        asyncio.create_task(self._run_server(server_name, server_params))
        # Give it a moment to initialize
        await asyncio.sleep(1.0)
        
    async def _run_server(self, server_name: str, server_params: StdioServerParameters):
        try:
            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    self.servers[server_name] = session
                    logger.info(f"MCP server '{server_name}' initialized.")
                    
                    # Keep the session alive indefinitely until cancelled
                    while True:
                        await asyncio.sleep(3600)
        except Exception as e:
            logger.error(f"MCP server '{server_name}' encountered an error: {e}")
            if server_name in self.servers:
                del self.servers[server_name]

    async def list_all_tools(self) -> List[Dict[str, Any]]:
        """
        Gathers tools from all connected MCP servers.
        Returns them in a standard dictionary format compatible with Gemini.
        """
        all_tools = []
        for server_name, session in self.servers.items():
            try:
                # Type: mcp.types.ListToolsResult
                tools_result = await session.list_tools()
                for tool in tools_result.tools:
                        import re
                        safe_tool_name = re.sub(r'[^a-zA-Z0-9_\.\:\-]', '-', tool.name)
                        combined_name = f"{server_name}__{safe_tool_name}"
                        self._tool_name_map = getattr(self, '_tool_name_map', {})
                        self._tool_name_map[combined_name] = tool.name
                        
                        all_tools.append({
                            "name": combined_name,
                            "description": tool.description or "",
                            "inputSchema": tool.inputSchema,
                            "server_name": server_name,
                            "original_name": tool.name
                        })
            except Exception as e:
                logger.error(f"Error listing tools from {server_name}: {e}")
                
        return all_tools

    async def call_tool(self, tool_name_combined: str, arguments: dict) -> str:
        """
        Calls a tool on the appropriate MCP server.
        The name is formatted as {server_name}__{tool_name} to avoid collisions.
        """
        if "__" not in tool_name_combined:
            return f"Error: Invalid tool name format {tool_name_combined}"
            
        server_name, _ = tool_name_combined.split("__", 1)
        original_name = getattr(self, '_tool_name_map', {}).get(tool_name_combined)
        if not original_name:
            original_name = tool_name_combined.split("__", 1)[1] # Fallback
            
        if server_name not in self.servers:
            return f"Error: MCP server {server_name} not found."
            
        session = self.servers[server_name]
        try:
            logger.info(f"Calling MCP Tool: {server_name}.{original_name} with {arguments}")
            # Request tool call
            result = await session.call_tool(original_name, arguments)
            
            # Formulate the response
            # result is typically a list of content blocks (text, image, etc.)
            output = ""
            if result.content:
                for block in result.content:
                    if block.type == "text":
                        output += block.text + "\n"
                    else:
                        output += f"[Returned {block.type} data]\n"
            
            if result.isError:
                return f"Tool Execution Error: {output}"
                
            return output.strip() if output else "Tool execution succeeded with no output."
        except Exception as e:
            logger.error(f"Failed to execute tool {tool_name_combined}: {e}")
            return f"Error executing tool: {e}"
