"""
HELIOS — Coder Agent
Writes code, executes terminal commands, and modifies files to fulfill a plan.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone

from agents.base import BaseAgent, AgentResult, AgentStatus
from providers.base import BaseProvider
from gateway.tool_gateway import ToolGateway
from gateway.host_gateway import HostGateway

class CoderAgent(BaseAgent):
    """
    Executes implementation tasks, edits files, and runs builds.
    """
    def __init__(
        self, 
        provider: BaseProvider, 
        tool_gateway: ToolGateway, 
        host_gateway: HostGateway,
        agent_id: Optional[str] = None
    ):
        super().__init__(agent_id)
        self.provider = provider
        self.tool_gateway = tool_gateway
        self.host_gateway = host_gateway

    @property
    def agent_type(self) -> str:
        return "coder"

    async def execute(self, objective: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        started_at = datetime.now(timezone.utc)
        
        # In a full implementation, this agent would run a ReAct loop with the tools
        # For now, we simulate a single generation that decides which tool to call
        
        try:
            # We would use the ToolGateway to get schemas, build a system prompt, 
            # and let the model pick the tools to execute.
            
            # Simulated outcome for architecture structure
            return self._make_result(
                status=AgentStatus.SUCCESS,
                summary=f"Executed coding task for: {objective[:30]}...",
                detail="Code changes applied.",
                started_at=started_at,
                confidence=0.8
            )
        except Exception as e:
            self.logger.error(f"Coder error: {e}")
            return self._make_result(
                status=AgentStatus.FAILURE,
                summary="Coder execution failed.",
                error=str(e),
                started_at=started_at
            )
