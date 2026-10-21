from typing import Dict, Any, List, Optional
import psutil
import platform
import os
from connectors.base import BaseConnector
from core.hardware_governor import HardwareGovernor

class SystemDiagnosticsConnector(BaseConnector):
    """Provides realtime system health, CPU/RAM usage, and active hardware tier metrics."""

    id = "system_diagnostics"
    name = "System Diagnostics & Hardware Prober"
    version = "1.0.0"
    description = "Inspects host CPU, RAM, GPU, active tier, and budget hardware warnings."
    scopes = ["read_only"]
    timeout_seconds = 10

    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "include_warnings": {"type": "boolean", "default": True}
            }
        }

    def output_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "cpu_percent": {"type": "number"},
                "ram_percent": {"type": "number"},
                "hardware_tier": {"type": "integer"},
                "tier_name": {"type": "string"},
                "is_budget": {"type": "boolean"},
                "warnings": {"type": "array", "items": {"type": "string"}}
            }
        }

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        governor = HardwareGovernor()
        vm = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.1)

        return {
            "success": True,
            "cpu_percent": cpu,
            "ram_total_gb": round(vm.total / (1024 ** 3), 2),
            "ram_available_gb": round(vm.available / (1024 ** 3), 2),
            "ram_percent": vm.percent,
            "hardware_tier": governor.decision.tier,
            "tier_name": governor.decision.tier_name,
            "is_budget": governor.decision.is_budget,
            "warnings": governor.decision.warnings if params.get("include_warnings", True) else [],
            "downgrades": governor.decision.downgrade_advisories
        }
