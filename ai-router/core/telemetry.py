import json
import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

from core.events import global_bus

logger = logging.getLogger("helios.telemetry")

class TelemetryManager:
    """
    HELIOS Telemetry Manager (Phase 9)
    Outputs structured JSON logs for all critical agent state changes,
    integrated directly into the global EventBus.
    """
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = self.log_dir / "telemetry.jsonl"
        
        # Subscribe to all major system events
        global_bus.subscribe("telemetry_event", self._handle_bus_event)

    def _handle_bus_event(self, payload: Dict[str, Any]):
        """Handler for events pushed via EventBus."""
        event_type = payload.get("event_type", "unknown")
        session_id = payload.get("session_id", "unknown")
        data = payload.get("data", {})
        self.record_event(event_type, session_id, data)

    def record_event(self, event_type: str, session_id: str, data: Dict[str, Any]):
        """Directly record an event to the JSONL sink."""
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "session_id": str(session_id),
            "data": data
        }
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload) + "\n")
        except Exception as e:
            logger.error(f"Failed to record telemetry: {e}")

telemetry = TelemetryManager()
