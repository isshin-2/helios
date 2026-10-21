import os
import sys
import asyncio
import importlib
import inspect
from typing import Tuple, List, Dict, Any
import logging
import subprocess

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
        self.overlay_process = None
        self._load_tools()

    def _load_tools(self):
        """Dynamically load all Tool classes from the tools package."""
        tools_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools")
        if not os.path.exists(tools_dir):
            return
            
        SYSTEM_TOOLS = {"SystemTool", "ScreenVisionTool", "ComputerControlTool"}
        MEMORY_TOOLS = {"CoreMemoryAppendTool", "ArchivalMemorySearchTool"}
        FILESYSTEM_TOOLS = {
            "FileReaderTool", "DirectoryListerTool",
            "FileWriterTool", "TerminalTool", "StatefulShellTool",
            "SelfModificationTool", "AskUserTool",
            "RepoMapTool", "FilePatchTool", "FilePatcherTool",
            "GitOpsTool", "ProcessMonitorTool", "HttpClientTool", "EnvSecretsTool",
            "ReverseEngineerTool"
        }
        
        for filename in os.listdir(tools_dir):
            if filename.endswith(".py") and not filename.startswith("__") and filename not in ("base.py", "executor.py"):
                module_name = f"tools.{filename[:-3]}"
                try:
                    module = importlib.import_module(module_name)
                    # Find classes in the module that inherit from BaseTool
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, BaseTool) and obj is not BaseTool:
                            # Inspect constructor parameters for smart dependency injection
                            init_sig = inspect.signature(obj.__init__)
                            params = list(init_sig.parameters.keys())[1:] # strip self
                            
                            tool_instance = None
                            if name in SYSTEM_TOOLS:
                                tool_instance = obj(self.provider, self.monitor)
                            elif name in FILESYSTEM_TOOLS or "permission_manager" in params:
                                tool_instance = obj(self.permission_manager)
                            elif name in MEMORY_TOOLS:
                                if not hasattr(self, 'memory_manager'):
                                    from router.memory import MemoryManager
                                    self.memory_manager = MemoryManager(self.provider)
                                tool_instance = obj(self.memory_manager)
                            elif name == "SubAgentTool":
                                tool_instance = obj(self.provider, self, self.permission_manager)
                            elif len(params) == 0:
                                tool_instance = obj()
                            else:
                                # Fallback instantiation attempting permission_manager or no-args
                                try:
                                    tool_instance = obj(self.permission_manager)
                                except Exception:
                                    tool_instance = obj()
                                
                            if tool_instance:
                                # Primary canonical name
                                self.tools[tool_instance.name] = tool_instance
                                # Register any backwards-compatible aliases
                                for alias in getattr(tool_instance, "aliases", []):
                                    self.tools[alias] = tool_instance
                except Exception as e:
                    logger.error(f"Failed to load tool {module_name}: {e}")

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return the JSON schema representations of unique loaded tools for LLM use."""
        schemas = []
        seen = set()
        for name, tool in self.tools.items():
            if tool.name in seen:
                continue
            seen.add(tool.name)
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
        is_interactive_tool = tool_name in ["computer_control", "screen_vision", "terminal"]
        try:
            if is_interactive_tool and not self.overlay_process:
                script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts', 'autonomous_overlay.py')
                self.overlay_process = subprocess.Popen([sys.executable, script_path])
                
            validated_inputs = tool.input_schema(**kwargs)
            try:
                result = await asyncio.wait_for(tool.execute(user_id=user_id, **validated_inputs.model_dump()), timeout=300.0)
                return result
            except asyncio.TimeoutError:
                return (f"Error: Tool '{tool_name}' timed out after 300 seconds.", tool_name)
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return (f"Error executing tool {tool_name}: {e}", tool_name)
        finally:
            if is_interactive_tool and self.overlay_process:
                try:
                    self.overlay_process.terminate()
                except Exception:
                    pass
                self.overlay_process = None


