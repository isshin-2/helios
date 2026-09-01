import os
import importlib
import inspect
from typing import Tuple, List, Dict, Any
import logging

from tools.base import BaseTool
from providers.base import BaseProvider
from health.monitor import SystemMonitor
from security.permissions import PermissionManager

logger = logging.getLogger(__name__)

class ToolRouter:
    """
    Dynamically loads tools from the tools/ directory and dispatches execution.
    Replaces the old ToolExecutor and regex-based routing.
    """
    def __init__(self, provider: BaseProvider, monitor: SystemMonitor,
                 permission_manager: PermissionManager):
        self.provider = provider
        self.monitor = monitor
        self.permission_manager = permission_manager
        self.tools: Dict[str, BaseTool] = {}
        self._load_tools()

    def _load_tools(self):
        """Dynamically load all Tool classes from the tools package."""
        tools_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools")
        if not os.path.exists(tools_dir):
            return
            
        # Dependencies that different tools might need
        SYSTEM_TOOLS = {"SystemTool", "ScreenVisionTool", "ComputerControlTool"}
        FILESYSTEM_TOOLS = {
            "FileReaderTool", "DirectoryListerTool",
            "FileWriterTool", "TerminalTool",
            "SelfModificationTool", "AskUserTool"
        }
        
        for filename in os.listdir(tools_dir):
            if filename.endswith(".py") and not filename.startswith("__") and filename not in ("base.py", "executor.py"):
                module_name = f"tools.{filename[:-3]}"
                try:
                    module = importlib.import_module(module_name)
                    # Find classes in the module that inherit from BaseTool
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, BaseTool) and obj is not BaseTool:
                            # Instantiate with appropriate dependencies
                            if name in SYSTEM_TOOLS:
                                tool_instance = obj(self.provider, self.monitor)
                            elif name in FILESYSTEM_TOOLS:
                                tool_instance = obj(self.permission_manager)
                            elif name == "SubAgentTool":
                                tool_instance = obj(self.provider, self)
                            else:
                                tool_instance = obj()
                                
                            self.tools[tool_instance.name] = tool_instance
                except Exception as e:
                    logger.error(f"Failed to load tool {module_name}: {e}")

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return the JSON schema representations of all loaded tools for LLM use."""
        schemas = []
        for name, tool in self.tools.items():
            schema = tool.input_schema.model_json_schema()
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": schema
                }
            })
        return schemas
        
    async def execute(self, tool_name: str, user_id: int, **kwargs) -> Tuple[str, str]:
        """
        Execute a tool by name.
        Returns (result_text, tool_name).
        """
        if tool_name not in self.tools:
            return (f"Error: Tool '{tool_name}' not found.", tool_name)
            
        tool = self.tools[tool_name]
        try:
            # Validate input against schema
            validated_inputs = tool.input_schema(**kwargs)
            return await tool.execute(user_id=user_id, **validated_inputs.model_dump())
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return (f"Error executing tool {tool_name}: {e}", tool_name)
