import asyncio
from typing import Dict, Any, Tuple
from pydantic import BaseModel, Field
from tools.base import BaseTool
from core.sidecar_manager import sidecar_manager

class SidecarInputSchema(BaseModel):
    command: str = Field(..., description="The terminal command to execute on the remote sidecar machine.")

class SidecarTool(BaseTool):
    name = "sidecar_control"
    description = "Executes an OS/terminal command securely on the connected remote sidecar (user's physical laptop or desktop)."
    input_schema = SidecarInputSchema

    async def execute(self, user_id: int, command: str, **kwargs) -> Tuple[str, str]:
        if not sidecar_manager.active_sidecars:
            return "Error: No sidecar is currently connected to HELIOS. Cannot execute remote command.", self.name
            
        result = await sidecar_manager.execute_on_sidecar("run_command", {"command": command})
        
        if "error" in result:
            return f"Sidecar execution failed: {result['error']}", self.name
            
        output = result.get("output", "Command executed but returned no output.")
        return f"Sidecar Output:\n{output}", self.name
