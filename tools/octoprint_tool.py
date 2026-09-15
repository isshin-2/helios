import requests
from typing import Tuple, Dict, Any
from pydantic import BaseModel, Field
from tools.base import BaseTool
import json

class OctoPrintStatusSchema(BaseModel):
    octoprint_url: str = Field(description="The URL or IP address of the OctoPrint server (e.g. http://octopi.local)")
    api_key: str = Field(description="The API key for OctoPrint")

class OctoPrintStatusTool(BaseTool):
    @property
    def name(self) -> str:
        return "octoprint_status"

    @property
    def description(self) -> str:
        return "Get the current print status and job details from an OctoPrint server."

    @property
    def input_schema(self) -> type[BaseModel]:
        return OctoPrintStatusSchema
        
    @property
    def requires_permission(self) -> bool:
        return False

    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        base_url = kwargs.get("octoprint_url").rstrip('/')
        headers = {"X-Api-Key": kwargs.get("api_key")}
        
        try:
            job_resp = requests.get(f"{base_url}/api/job", headers=headers, timeout=5)
            printer_resp = requests.get(f"{base_url}/api/printer", headers=headers, timeout=5)
            
            job_data = job_resp.json() if job_resp.status_code == 200 else {}
            printer_data = printer_resp.json() if printer_resp.status_code == 200 else {}
            
            result = {
                "job": job_data,
                "printer": printer_data
            }
            return (json.dumps(result, indent=2), self.name)
        except Exception as e:
            return (f"Failed to connect to OctoPrint: {str(e)}", self.name)

class OctoPrintControlSchema(BaseModel):
    octoprint_url: str = Field(description="The URL or IP address of the OctoPrint server")
    api_key: str = Field(description="The API key for OctoPrint")
    command: str = Field(description="The command to send: 'cancel', 'pause', or 'resume'")

class OctoPrintControlTool(BaseTool):
    @property
    def name(self) -> str:
        return "octoprint_control"

    @property
    def description(self) -> str:
        return "Control the current print job on an OctoPrint server (cancel, pause, resume)."

    @property
    def input_schema(self) -> type[BaseModel]:
        return OctoPrintControlSchema
        
    @property
    def requires_permission(self) -> bool:
        return True

    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        base_url = kwargs.get("octoprint_url").rstrip('/')
        headers = {"X-Api-Key": kwargs.get("api_key")}
        command = kwargs.get("command").lower()
        
        if command not in ["cancel", "pause", "resume"]:
            return ("Invalid command. Must be cancel, pause, or resume.", self.name)
            
        payload = {"command": command}
        
        try:
            resp = requests.post(f"{base_url}/api/job", headers=headers, json=payload, timeout=5)
            if resp.status_code == 204:
                return (f"Successfully executed '{command}' on OctoPrint.", self.name)
            else:
                return (f"Failed to execute command: HTTP {resp.status_code}", self.name)
        except Exception as e:
            return (f"Failed to connect to OctoPrint: {str(e)}", self.name)
