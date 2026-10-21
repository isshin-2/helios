from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import time
import concurrent.futures
import logging

logger = logging.getLogger("helios.connectors")

class ConnectorExecutionError(Exception):
    pass

class ConnectorTimeoutError(ConnectorExecutionError):
    pass

class BaseConnector(ABC):
    """Abstract Base Class for all HELIOS & Twin ecosystem extensible connectors."""

    id: str = "base_connector"
    name: str = "Base Connector"
    version: str = "1.0.0"
    description: str = "Base abstract connector interface"
    scopes: List[str] = ["read_only"]
    timeout_seconds: int = 15

    @abstractmethod
    def input_schema(self) -> Dict[str, Any]:
        """Returns JSON-schema formatted contract for connector inputs."""
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    @abstractmethod
    def output_schema(self) -> Dict[str, Any]:
        """Returns JSON-schema formatted contract for connector outputs."""
        return {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"}
            }
        }

    @abstractmethod
    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Executes connector logic. Subclasses must implement this method."""
        pass

    def run_safe(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Safely executes the connector with timeout enforcement, error capture, and execution metadata."""
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.execute, params, context or {})
            try:
                result = future.result(timeout=self.timeout_seconds)
                execution_ms = round((time.time() - start_time) * 1000, 2)
                if isinstance(result, dict):
                    result.setdefault("success", True)
                    result.setdefault("_execution_ms", execution_ms)
                    result.setdefault("_connector_id", self.id)
                    return result
                return {
                    "success": True,
                    "data": result,
                    "_execution_ms": execution_ms,
                    "_connector_id": self.id
                }
            except concurrent.futures.TimeoutError:
                execution_ms = round((time.time() - start_time) * 1000, 2)
                logger.error(f"[Connector Timeout] {self.id} exceeded limit of {self.timeout_seconds}s")
                return {
                    "success": False,
                    "error": f"Connector execution timed out after {self.timeout_seconds}s",
                    "error_type": "TimeoutError",
                    "_execution_ms": execution_ms,
                    "_connector_id": self.id
                }
            except Exception as e:
                execution_ms = round((time.time() - start_time) * 1000, 2)
                logger.error(f"[Connector Error] {self.id} failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "_execution_ms": execution_ms,
                    "_connector_id": self.id
                }
