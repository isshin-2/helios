import asyncio
import logging
import uuid
from typing import Tuple, Dict, Any, Optional
from pydantic import BaseModel, Field

from tools.base import BaseTool
from providers.base import BaseProvider

logger = logging.getLogger(__name__)

class SubAgentInput(BaseModel):
    task: str = Field(..., description="The specific task, research question, or multi-step problem for the sub-agent to solve.")
    budget: int = Field(5, description="Maximum number of thought/action iterations the sub-agent can take.")

class SubAgentTool(BaseTool):
    """
    Spawns an asynchronous background sub-agent with a restricted tool set and its own context budget.
    """
    
    def __init__(self, provider: BaseProvider, tool_router: Any = None):
        self.provider = provider
        self.tool_router = tool_router
        self._active_tasks: Dict[str, asyncio.Task] = {}
        
    @property
    def name(self) -> str:
        return "SubAgentTool"
        
    @property
    def description(self) -> str:
        return "Spawns a background sub-agent to perform deep research or multi-step reasoning."
        
    @property
    def input_schema(self) -> type[BaseModel]:
        return SubAgentInput
        
    @property
    def requires_permission(self) -> bool:
        return False
        
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running sub-agent task."""
        if task_id in self._active_tasks:
            self._active_tasks[task_id].cancel()
            return True
        return False
        
    async def _run_agent_loop(self, task: str, user_id: int, budget: int) -> str:
        """The actual agent loop running in the background."""
        # For Phase 7, we implement a simple single-pass deep reasoning call.
        # In a more advanced version, this would be a ReAct loop iterating `budget` times.
        
        messages = [
            {"role": "system", "content": "You are a research sub-agent. Solve the task concisely and return the final answer. You operate in a sandbox."},
            {"role": "user", "content": task}
        ]
        
        try:
            # We use chat() for messages
            response = await self.provider.chat(
                model="deepseek-r1:7b",
                messages=messages,
                stream=False
            )
            
            result = ""
            if isinstance(response, dict) and "message" in response:
                result = response["message"].get("content", "")
            
            return f"Sub-Agent completed task: '{task}'.\n\nResult:\n{result}"
            
        except asyncio.CancelledError:
            logger.info("Sub-agent task was cancelled.")
            return "Sub-Agent task was cancelled."
        except Exception as e:
            logger.error(f"Sub-agent failed: {e}")
            return f"Sub-Agent failed with error: {str(e)}"
            
    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        task = kwargs.get("task", "")
        budget = kwargs.get("budget", 5)
        
        # We run it directly here (asynchronously but awaited)
        # to ensure it returns to the orchestrator.
        # Background task spawning can be triggered by calling _run_agent_loop in an asyncio.create_task 
        # and returning a task ID. But since orchestrator expects a string result for deterministic tools right now,
        # we will await it.
        
        task_id = str(uuid.uuid4())
        
        # In a fully asynchronous design where the main agent doesn't block:
        # We'd return "Sub-agent started with ID: {task_id}" and let it push to EventBus when done.
        # For this Phase, we'll await it to fit the `execute` signature and provide the answer immediately.
        
        try:
            result_text = await self._run_agent_loop(task, user_id, budget)
            return (result_text, self.name)
        except Exception as e:
            return (f"Error running subagent: {e}", self.name)
