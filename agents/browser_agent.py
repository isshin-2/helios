"""
HELIOS — Browser Agent
Dedicated agent for autonomous web research and DOM interaction.
"""

import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from agents.base import BaseAgent, AgentResult, AgentStatus
from providers.base import BaseProvider
from gateway.tool_gateway import ToolGateway

class BrowserAgent(BaseAgent):
    """
    Sub-agent that specializes in web browsing and extraction.
    Uses ToolGateway to execute the BrowserTool safely.
    """
    def __init__(
        self, 
        provider: BaseProvider, 
        tool_gateway: ToolGateway,
        agent_id: Optional[str] = None
    ):
        super().__init__(agent_id)
        self.provider = provider
        self.tool_gateway = tool_gateway

    @property
    def agent_type(self) -> str:
        return "browser"

    async def execute(self, objective: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        started_at = datetime.now(timezone.utc)
        
        # Here the agent would use the LLM to decide what URLs to fetch based on the objective
        # For simplicity in this architectural pass, we'll extract a URL from the objective if present
        
        # Heuristic: Find first http link in the objective
        words = objective.split()
        url = None
        for w in words:
            if w.startswith("http://") or w.startswith("https://"):
                url = w
                break
                
        if not url:
            # Let the LLM figure out a search query, then use a tool, etc.
            # (Simulated for this milestone)
            return self._make_result(
                status=AgentStatus.NEEDS_INPUT,
                summary="No URL provided for the browser agent to navigate.",
                started_at=started_at
            )
            
        try:
            # Route through the unified gateway!
            result_text, _ = await self.tool_gateway.execute_tool(
                tool_name="browser_tool",
                user_id=context.get("user_id", 0) if context else 0,
                arguments={"url": url, "extract_dom": False}
            )
            
            return self._make_result(
                status=AgentStatus.SUCCESS,
                summary=f"Successfully navigated to {url}",
                detail=result_text,
                started_at=started_at,
                confidence=1.0
            )
        except Exception as e:
            self.logger.error(f"Browser agent error: {e}")
            return self._make_result(
                status=AgentStatus.FAILURE,
                summary=f"Failed to navigate to {url}",
                error=str(e),
                started_at=started_at
            )
