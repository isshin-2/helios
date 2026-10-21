import os
import sys
import json
import logging
import importlib
from typing import Dict, Any, List, Optional
from connectors.base import BaseConnector

logger = logging.getLogger("helios.connectors")

class ConnectorRegistry:
    """Manages dynamic discovery, validation, and execution of registered connectors."""

    DEFAULT_MANIFEST_PATH = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "config", "connectors.manifest.json")
    )

    def __init__(self, manifest_path: Optional[str] = None):
        self.manifest_path = manifest_path or self.DEFAULT_MANIFEST_PATH
        self._connectors: Dict[str, BaseConnector] = {}
        self.manifest_data: Dict[str, Any] = {}
        self.reload()

    def reload(self):
        """Loads or reloads the manifest and registers connector instances."""
        self._connectors.clear()
        if not os.path.exists(self.manifest_path):
            self._create_default_manifest()

        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                self.manifest_data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read connectors manifest at {self.manifest_path}: {e}")
            self.manifest_data = {"connectors": []}

        for entry in self.manifest_data.get("connectors", []):
            if not entry.get("enabled", True):
                continue
            conn_id = entry.get("id")
            entrypoint = entry.get("entrypoint")
            if not conn_id or not entrypoint:
                continue

            try:
                module_path, class_name = entrypoint.rsplit(".", 1)
                mod = importlib.import_module(module_path)
                cls = getattr(mod, class_name)
                instance = cls()
                if "timeout_seconds" in entry:
                    instance.timeout_seconds = entry["timeout_seconds"]
                self._connectors[conn_id] = instance
                logger.info(f"Registered connector: {conn_id} ({instance.name})")
            except Exception as e:
                logger.error(f"Failed to load connector '{conn_id}' from {entrypoint}: {e}")

    def _create_default_manifest(self):
        os.makedirs(os.path.dirname(self.manifest_path), exist_ok=True)
        default_manifest = {
            "version": "1.0.0",
            "connectors": [
                {
                    "id": "system_diagnostics",
                    "entrypoint": "connectors.system_diagnostics.SystemDiagnosticsConnector",
                    "scopes": ["read_only"],
                    "timeout_seconds": 10,
                    "enabled": True,
                    "description": "Host hardware diagnostics, CPU/RAM utilization, and budget hardware advisories."
                }
            ]
        }
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(default_manifest, f, indent=2)

    def get_connector(self, connector_id: str) -> Optional[BaseConnector]:
        return self._connectors.get(connector_id)

    def list_connectors(self) -> List[Dict[str, Any]]:
        result = []
        for cid, conn in self._connectors.items():
            result.append({
                "id": cid,
                "name": conn.name,
                "version": conn.version,
                "description": conn.description,
                "scopes": conn.scopes,
                "timeout_seconds": conn.timeout_seconds,
                "input_schema": conn.input_schema(),
                "output_schema": conn.output_schema()
            })
        return result

    def execute(self, connector_id: str, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        connector = self.get_connector(connector_id)
        if not connector:
            return {
                "success": False,
                "error": f"Connector '{connector_id}' is not registered or is disabled.",
                "error_type": "NotFoundError"
            }
        return connector.run_safe(params, context)

    def add_connector(self, entry: Dict[str, Any], python_code: Optional[str] = None) -> Dict[str, Any]:
        """Registers a new developer connector, saves manifest, and optionally writes code."""
        conn_id = entry.get("id")
        entrypoint = entry.get("entrypoint")
        if not conn_id or not entrypoint:
            raise ValueError("Connector 'id' and 'entrypoint' are required.")

        # Write code if supplied
        if python_code:
            try:
                module_name = entrypoint.split(".")[1]
                target_file = os.path.join(os.path.dirname(__file__), f"{module_name}.py")
                with open(target_file, "w", encoding="utf-8") as f:
                    f.write(python_code)
                logger.info(f"Wrote connector code to {target_file}")
            except Exception as e:
                logger.error(f"Failed to write connector code: {e}")
                raise

        # Update manifest
        connectors_list = self.manifest_data.setdefault("connectors", [])
        # Remove existing if overwriting
        self.manifest_data["connectors"] = [c for c in connectors_list if c.get("id") != conn_id]
        
        new_entry = {
            "id": conn_id,
            "entrypoint": entrypoint,
            "scopes": entry.get("scopes", ["read_only"]),
            "timeout_seconds": entry.get("timeout_seconds", 15),
            "enabled": entry.get("enabled", True),
            "description": entry.get("description", "Custom developer-designed connector.")
        }
        self.manifest_data["connectors"].append(new_entry)

        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(self.manifest_data, f, indent=2)

        self.reload()
        return new_entry

    def toggle_connector(self, connector_id: str, enabled: bool) -> bool:
        """Enables or disables an existing connector in manifest."""
        updated = False
        for c in self.manifest_data.get("connectors", []):
            if c.get("id") == connector_id:
                c["enabled"] = enabled
                updated = True
                break

        if updated:
            with open(self.manifest_path, "w", encoding="utf-8") as f:
                json.dump(self.manifest_data, f, indent=2)
            self.reload()
        return updated

    @staticmethod
    def generate_scaffold(connector_id: str, name: str, description: str, scopes: Optional[List[str]] = None) -> str:
        """Generates starter Python boilerplate subclassing BaseConnector."""
        class_name = "".join(part.capitalize() for part in connector_id.replace("-", "_").split("_")) + "Connector"
        scope_list = scopes or ["read_only"]
        return f'''from typing import Dict, Any, Optional
from connectors.base import BaseConnector

class {class_name}(BaseConnector):
    """
    {description or f"Custom developer connector: {name}"}
    """

    id = "{connector_id}"
    name = "{name}"
    version = "1.0.0"
    description = "{description}"
    scopes = {json.dumps(scope_list)}
    timeout_seconds = 15

    def input_schema(self) -> Dict[str, Any]:
        return {{
            "type": "object",
            "properties": {{
                "query": {{"type": "string", "description": "Sample input parameter"}}
            }},
            "required": ["query"]
        }}

    def output_schema(self) -> Dict[str, Any]:
        return {{
            "type": "object",
            "properties": {{
                "success": {{"type": "boolean"}},
                "result": {{"type": "string"}}
            }}
        }}

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        query = params.get("query", "")
        # Implement your custom logic here (API calls, data processing, tool execution)
        return {{
            "success": True,
            "result": f"Processed query successfully: {{query}}",
            "details": "Executed by custom developer connector {connector_id}"
        }}
'''

_global_registry = None

def get_connector_registry() -> ConnectorRegistry:
    global _global_registry
    if _global_registry is None:
        _global_registry = ConnectorRegistry()
    return _global_registry
