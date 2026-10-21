import asyncio
import json
import logging
import time
import uuid
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class SidecarManager:
    def __init__(self):
        self.active_sidecars: Dict[str, Any] = {}
        self.sidecar_metadata: Dict[str, Dict[str, Any]] = {}
        self.pending_requests: Dict[str, asyncio.Future] = {}

    async def register(self, sidecar_id: str, websocket):
        self.active_sidecars[sidecar_id] = websocket
        self.sidecar_metadata[sidecar_id] = {
            "connected_at": time.time(),
            "status": "connected"
        }
        logger.info(f"Sidecar connected: {sidecar_id}")

    def unregister(self, sidecar_id: str):
        if sidecar_id in self.active_sidecars:
            del self.active_sidecars[sidecar_id]
        if sidecar_id in self.sidecar_metadata:
            del self.sidecar_metadata[sidecar_id]
        logger.info(f"Sidecar disconnected: {sidecar_id}")

    def has_active_sidecars(self) -> bool:
        return len(self.active_sidecars) > 0

    def get_sidecars_info(self) -> List[Dict[str, Any]]:
        result = []
        for sid, meta in self.sidecar_metadata.items():
            result.append({
                "sidecar_id": sid,
                **meta
            })
        return result

    async def handle_message(self, sidecar_id: str, message: str):
        try:
            data = json.loads(message)
            if data.get("type") == "register":
                incoming_meta = data.get("metadata", {})
                if sidecar_id in self.sidecar_metadata:
                    self.sidecar_metadata[sidecar_id].update(incoming_meta)
                else:
                    self.sidecar_metadata[sidecar_id] = incoming_meta
                logger.info(f"[Sidecar] Registered node '{incoming_meta.get('hostname', sidecar_id)}' (OS: {incoming_meta.get('os')})")
                return

            req_id = data.get("request_id")
            if req_id and req_id in self.pending_requests:
                self.pending_requests[req_id].set_result(data)
        except Exception as e:
            logger.error(f"Error parsing sidecar message: {e}")

    async def execute_on_sidecar(self, action: str, payload: dict, timeout: int = 30) -> dict:
        if not self.active_sidecars:
            return {"error": "No sidecars currently connected to HELIOS."}
        
        # Pick the first connected sidecar (could be expanded for multi-machine later)
        sidecar_id = list(self.active_sidecars.keys())[0]
        websocket = self.active_sidecars[sidecar_id]
        
        request_id = str(uuid.uuid4())
        future = asyncio.Future()
        self.pending_requests[request_id] = future
        
        message = {
            "request_id": request_id,
            "action": action,
            "payload": payload
        }
        
        try:
            await websocket.send_text(json.dumps(message))
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            return {"error": "Sidecar execution timed out."}
        except Exception as e:
            return {"error": str(e)}
        finally:
            if request_id in self.pending_requests:
                del self.pending_requests[request_id]

sidecar_manager = SidecarManager()

