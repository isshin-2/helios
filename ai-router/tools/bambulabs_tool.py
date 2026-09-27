import asyncio
from typing import Tuple, Dict, Any
from pydantic import BaseModel, Field
from tools.base import BaseTool
import json

class BambuStatusSchema(BaseModel):
    cloud_email: str = Field(description="Email address for Bambu Cloud account")
    cloud_password: str = Field(description="Password for Bambu Cloud account")
    serial_number: str = Field(description="Serial number of the Bambu printer")

class BambuStatusTool(BaseTool):
    @property
    def name(self) -> str:
        return "bambu_printer_status"

    @property
    def description(self) -> str:
        return "Get the current print status of a Bambu Labs 3D printer."

    @property
    def input_schema(self) -> type[BaseModel]:
        return BambuStatusSchema
        
    @property
    def requires_permission(self) -> bool:
        return False

    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        import connectors.bambulabs as bambu
        
        printer_config = {
            'label': "BambuPrinter",
            'email': kwargs.get("cloud_email"),
            'password': kwargs.get("cloud_password"),
            'serial': kwargs.get("serial_number"),
            'cloud': True
        }
        
        watcher = bambu.PrinterWatcher(printer_config)
        watcher.connect()
        
        # Wait up to 5 seconds to receive the MQTT report
        for _ in range(50):
            if "mc_print_stage" in watcher.status:
                break
            await asyncio.sleep(0.1)
            
        watcher.disconnect()
        
        if "mc_print_stage" in watcher.status:
            return (json.dumps(watcher.status, indent=2), self.name)
        else:
            return ("Failed to retrieve printer status or printer is offline.", self.name)

class BambuStopSchema(BaseModel):
    cloud_email: str = Field(description="Email address for Bambu Cloud account")
    cloud_password: str = Field(description="Password for Bambu Cloud account")
    serial_number: str = Field(description="Serial number of the Bambu printer")

class BambuStopTool(BaseTool):
    @property
    def name(self) -> str:
        return "bambu_printer_stop"

    @property
    def description(self) -> str:
        return "Stop the current print on a Bambu Labs 3D printer. This terminates the physical print job."

    @property
    def input_schema(self) -> type[BaseModel]:
        return BambuStopSchema
        
    @property
    def requires_permission(self) -> bool:
        return True # Stopping a physical print requires permission!

    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        import connectors.bambulabs as bambu
        
        printer_config = {
            'label': "BambuPrinter",
            'email': kwargs.get("cloud_email"),
            'password': kwargs.get("cloud_password"),
            'serial': kwargs.get("serial_number"),
            'cloud': True
        }
        
        watcher = bambu.PrinterWatcher(printer_config)
        watcher.connect()
        # Give it a second to connect before publishing
        await asyncio.sleep(1)
        watcher.stop_print()
        await asyncio.sleep(1)
        watcher.disconnect()
        
        return ("Stop command sent to the Bambu printer successfully.", self.name)
