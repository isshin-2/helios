"""Automated Unit & Integration Tests for HELIOS Extensible Developer Connectors.
Verifies registry discovery, dynamic registration, schema scaffolding, safe sandbox execution, and state toggling.
"""

import os
import sys
import pytest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AI_ROUTER_DIR = os.path.join(BASE_DIR, "ai-router")
if AI_ROUTER_DIR not in sys.path:
    sys.path.insert(0, AI_ROUTER_DIR)

from connectors.registry import ConnectorRegistry, get_connector_registry
from connectors.base import BaseConnector

def test_connector_discovery_and_builtins():
    """Verify built-in system diagnostics connector is discovered."""
    registry = get_connector_registry()
    connectors = registry.list_connectors()
    assert len(connectors) >= 1
    
    diag = next((c for c in connectors if c["id"] == "system_diagnostics"), None)
    assert diag is not None
    assert diag["name"] == "System Diagnostics & Hardware Prober"
    assert "read_only" in diag["scopes"]

def test_connector_scaffold_generation():
    """Verify registry can generate valid BaseConnector Python boilerplate."""
    registry = get_connector_registry()
    scaffold = registry.generate_scaffold(
        connector_id="mock_weather",
        name="Mock Weather Service",
        description="Fetches local temperature metrics",
        scopes=["network:read"]
    )
    assert "class MockWeatherConnector(BaseConnector):" in scaffold
    assert "def execute(self, params: Dict[str, Any]" in scaffold
    assert "def input_schema(self) -> Dict[str, Any]:" in scaffold
    assert "def output_schema(self) -> Dict[str, Any]:" in scaffold

def test_connector_execution_sandbox():
    """Verify execution of a connector returns structured dict within timeouts."""
    registry = get_connector_registry()
    res = registry.execute("system_diagnostics", {})
    assert res["success"] is True
    assert "hardware_tier" in res
    assert "ram_total_gb" in res
    assert "tier_name" in res

def test_connector_toggle_state():
    """Verify connectors can be toggled enabled and disabled."""
    registry = get_connector_registry()
    # Toggle off
    ok = registry.toggle_connector("system_diagnostics", False)
    assert ok is True
    assert registry.manifest_data["connectors"][0]["enabled"] is False

    # Toggle back on
    ok = registry.toggle_connector("system_diagnostics", True)
    assert ok is True
    assert registry.manifest_data["connectors"][0]["enabled"] is True
