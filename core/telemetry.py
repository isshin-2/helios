import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

class TelemetryManager:
    """
    Phase 11: OBSERVABILITY
    Outputs structured JSON logs for all critical agent state changes.
    """
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = self.log_dir / "telemetry.jsonl"

    def record_event(self, event_type: str, session_id: str, data: Dict[str, Any]):
        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "session_id": session_id,
            "data": data
        }
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload) + "\n")
        except Exception as e:
            logger.error(f"Failed to record telemetry: {e}")

telemetry = TelemetryManager()
