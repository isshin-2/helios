"""
HELIOS — Planner Agent
Breaks down objectives into steps and forms execution strategies.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
import json

from agents.base import BaseAgent, AgentResult, AgentStatus
from providers.base import BaseProvider
from gateway.tool_gateway import ToolGateway

class PlannerAgent(BaseAgent):
    """
    Analyzes an objective and creates a step-by-step plan.
    """
    def __init__(self, provider: BaseProvider, tool_gateway: ToolGateway, agent_id: Optional[str] = None):
        super().__init__(agent_id)
        self.provider = provider
        self.tool_gateway = tool_gateway

    @property
    def agent_type(self) -> str:
        return "planner"

    async def execute(self, objective: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        started_at = datetime.now(timezone.utc)
        context_str = json.dumps(context, indent=2) if context else "{}"
        
        prompt = f"""
You are the HELIOS Planner Agent.
Break down the following objective into a logical sequence of execution steps.
Consider the provided context.

OBJECTIVE:
{objective}

CONTEXT:
{context_str}

Respond with a JSON array of step objects, where each step has:
- "step": integer sequence number
- "action": string description of the action
- "tool": suggested tool name (if applicable, else null)
"""
        try:
            # We assume provider.generate returns a dict with 'response' key
            response = await self.provider.generate(
                model="llama3.2:3b", # Default fast model or configurable
                prompt=prompt,
                stream=False
            )
            content = response.get("response", "[]").strip()
            
            # Very basic cleanup in case of markdown blocks
            if content.startswith("```json"):
                content = content[7:-3]
            elif content.startswith("```"):
                content = content[3:-3]
                
            steps = json.loads(content)
            
            return self._make_result(
                status=AgentStatus.SUCCESS,
                summary=f"Created plan with {len(steps)} steps.",
                detail=content,
                evidence={"steps": steps},
                started_at=started_at,
                confidence=0.9
            )
        except json.JSONDecodeError as e:
            return self._make_result(
                status=AgentStatus.FAILURE,
                summary="Failed to parse plan as JSON.",
                error=str(e),
                started_at=started_at
            )
        except Exception as e:
            self.logger.error(f"Planner error: {e}")
            return self._make_result(
                status=AgentStatus.FAILURE,
                summary="Planner execution failed.",
                error=str(e),
                started_at=started_at
            )
