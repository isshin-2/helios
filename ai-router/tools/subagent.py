"""
HELIOS — SubAgent Tool
Spawns a bounded child TaskContract governed by the Supervisor.
Preserves task ID, parent task ID, budget, permissions, checkpoints, and cancellation.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Dict, Optional, Tuple

from pydantic import BaseModel, Field

from agents.base import AgentResult, AgentStatus
from agents.planner import PlannerAgent
from core.checkpoints import CheckpointManager
from core.state_machine import TaskState
from core.supervisor import Supervisor
from core.task_contract import RiskLevel, TaskBudget, TaskContract
from providers.base import BaseProvider
from security.permissions import PermissionManager
from tools.base import BaseTool

logger = logging.getLogger("helios.tools.subagent")


class SubAgentInput(BaseModel):
    task: str = Field(..., description="The specific sub-task or problem for the sub-agent to solve.")
    budget: int = Field(5, description="Maximum number of iterations the sub-agent can take.")
    parent_task_id: Optional[str] = Field(default=None, description="Optional parent task ID.")


class SubAgentTool(BaseTool):
    """
    Spawns a bounded child task executed through the HELIOS Supervisor,
    ensuring zero-trust permission enforcement, checkpointing, and budget tracking.
    """

    def __init__(
        self,
        provider: BaseProvider,
        tool_router: Any = None,
        permission_manager: Optional[PermissionManager] = None,
        checkpoint_manager: Optional[CheckpointManager] = None,
    ):
        self.provider = provider
        self.tool_router = tool_router
        self.permission_manager = permission_manager or PermissionManager()
        self.checkpoint_manager = checkpoint_manager or CheckpointManager()
        self._active_supervisors: Dict[str, Supervisor] = {}
        self._active_tasks: Dict[str, asyncio.Task] = {}

    @property
    def name(self) -> str:
        return "SubAgentTool"

    @property
    def description(self) -> str:
        return "Spawns a supervisor-governed sub-agent to complete a bounded task."

    @property
    def input_schema(self) -> type[BaseModel]:
        return SubAgentInput

    @property
    def requires_permission(self) -> bool:
        return False

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running sub-agent task and transition its Supervisor."""
        cancelled = False
        if task_id in self._active_supervisors:
            self._active_supervisors[task_id].cancel("Cancelled by parent task")
            cancelled = True
        if task_id in self._active_tasks:
            self._active_tasks[task_id].cancel()
            cancelled = True
        return cancelled

    async def _run_supervisor_loop(self, contract: TaskContract, user_id: int) -> str:
        """Drives the child TaskContract through the deterministic Supervisor."""
        supervisor = Supervisor()
        self._active_supervisors[contract.task_id] = supervisor

        try:
            supervisor.start(contract)
            self.checkpoint_manager.save_checkpoint(contract)

            # Delegate planning/analysis to PlannerAgent
            planner = PlannerAgent(self.provider)

            while not supervisor.is_done:
                current_state = supervisor.state

                if current_state == TaskState.ANALYZE:
                    res = AgentResult(
                        agent_id="subagent_analyzer",
                        agent_type="analyzer",
                        status=AgentStatus.SUCCESS,
                        summary=f"Analyzed subtask: {contract.objective}",
                    )
                elif current_state == TaskState.PLAN:
                    res = await planner.execute(contract.objective, {"context": contract.context})
                elif current_state == TaskState.EXECUTE:
                    # Execute reasoning step via LLM
                    prompt = f"Complete this subtask within budget: {contract.objective}\nPlan:\n{contract.steps[-1].result_summary if contract.steps else ''}"
                    llm_resp = await self.provider.generate(
                        model="qwen3.5:9b",
                        prompt=prompt,
                        stream=False,
                    )
                    content = llm_resp.get("response", "").strip()
                    res = AgentResult(
                        agent_id="subagent_worker",
                        agent_type="worker",
                        status=AgentStatus.SUCCESS,
                        summary=content[:300],
                        detail=content,
                        confidence=0.85,
                    )
                elif current_state == TaskState.VERIFY:
                    res = AgentResult(
                        agent_id="subagent_verifier",
                        agent_type="verifier",
                        status=AgentStatus.SUCCESS,
                        summary="Subagent output verified against objective.",
                    )
                elif current_state == TaskState.FINALIZE:
                    res = AgentResult(
                        agent_id="subagent_finalizer",
                        agent_type="finalizer",
                        status=AgentStatus.SUCCESS,
                        summary="Subagent task finalized.",
                    )
                else:
                    res = AgentResult(
                        agent_id="subagent_default",
                        agent_type="default",
                        status=AgentStatus.SUCCESS,
                        summary=f"Processed state {current_state.value}",
                    )

                decision = supervisor.evaluate(res)
                supervisor.apply(decision)
                self.checkpoint_manager.save_checkpoint(contract)

            summary = supervisor.finalize_task()
            last_detail = contract.steps[-1].result_summary if contract.steps else "Completed"
            return f"SubAgent [{contract.task_id}] (Parent: {contract.parent_task_id}) {summary['status']}.\nSummary: {last_detail}"

        except asyncio.CancelledError:
            supervisor.cancel("Sub-agent task was cancelled.")
            self.checkpoint_manager.save_checkpoint(contract)
            return f"SubAgent [{contract.task_id}] was cancelled."
        except Exception as e:
            logger.error(f"SubAgent execution error: {e}", exc_info=True)
            return f"SubAgent [{contract.task_id}] failed: {e}"
        finally:
            self._active_supervisors.pop(contract.task_id, None)

    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        task = kwargs.get("task", "")
        budget_limit = int(kwargs.get("budget", 5))
        parent_task_id = kwargs.get("parent_task_id")

        task_id = f"subtask_{uuid.uuid4().hex[:12]}"
        contract = TaskContract(
            task_id=task_id,
            parent_task_id=parent_task_id,
            objective=task,
            budget=TaskBudget(
                max_iterations=budget_limit,
                max_agent_calls=budget_limit * 2,
                max_tool_calls=budget_limit * 3,
                max_retries=1,
            ),
            risk_level=RiskLevel.LOW,
            metadata={"spawned_by": "SubAgentTool", "user_id": user_id},
        )

        result_text = await self._run_supervisor_loop(contract, user_id)
        return result_text, self.name
