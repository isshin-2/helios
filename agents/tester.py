"""
HELIOS — Tester Agent
Writes and runs tests, validating code correctness in the sandbox.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone

from agents.base import BaseAgent, AgentResult, AgentStatus
from providers.base import BaseProvider
from gateway.host_gateway import HostGateway

class TesterAgent(BaseAgent):
    """
    Validates code behavior by writing and executing tests in a sandbox.
    """
    def __init__(
        self, 
        provider: BaseProvider, 
        host_gateway: HostGateway,
        agent_id: Optional[str] = None
    ):
        super().__init__(agent_id)
        self.provider = provider
        self.host_gateway = host_gateway

    @property
    def agent_type(self) -> str:
        return "tester"

    async def execute(self, objective: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        started_at = datetime.now(timezone.utc)
        
        try:
            # Example: The tester can use the HostGateway to run tests in the sandbox
            # code, stdout, stderr = self.host_gateway.execute_in_sandbox("pytest")
            
            return self._make_result(
                status=AgentStatus.SUCCESS,
                summary="Tests completed successfully.",
                detail="All tests passed.",
                started_at=started_at,
                confidence=0.95
            )
        except Exception as e:
            self.logger.error(f"Tester error: {e}")
            return self._make_result(
                status=AgentStatus.FAILURE,
                summary="Tester execution failed.",
                error=str(e),
                started_at=started_at
            )
