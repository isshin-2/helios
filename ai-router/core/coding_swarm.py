"""
HELIOS — Coding Swarm Orchestrator
Coordinates the multi-agent coding pipeline through the deterministic Supervisor:
ANALYZE (RepoMapper) → PLAN (Planner) → ARCHITECT (Architect) →
EXECUTE (Coder) → VERIFY (Tester) →
[Parallel Review: Reviewer + SecurityReviewer] →
FINALIZE → COMPLETED (with automated REPAIR loops on failures).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, Optional, Tuple

from agents.architect import ArchitectAgent
from agents.base import AgentResult, AgentStatus
from agents.coder import CoderAgent
from agents.planner import PlannerAgent
from agents.repair import RepairAgent
from agents.repo_mapper import RepoMapperAgent
from agents.reviewer import ReviewerAgent
from agents.security_reviewer import SecurityReviewerAgent
from agents.tester import TesterAgent
from core.checkpoints import CheckpointManager
from core.coding_runtime import CodingContext, CodingTaskRuntime
from core.state_machine import TaskState
from core.supervisor import Supervisor
from core.task_contract import RiskLevel, TaskBudget, TaskContract
from providers.base import BaseProvider
from security.permissions import PermissionManager

logger = logging.getLogger("helios.coding_swarm")


class CodingSwarmOrchestrator:
    """
    Executes end-to-end coding tasks in an isolated workspace.
    LLMs do NOT control the global state machine; the Supervisor does.
    """

    def __init__(
        self,
        provider: BaseProvider,
        permission_manager: Optional[PermissionManager] = None,
        checkpoint_manager: Optional[CheckpointManager] = None,
    ):
        self.provider = provider
        self.permission_manager = permission_manager or PermissionManager()
        self.checkpoint_manager = checkpoint_manager or CheckpointManager()

        # Instantiate Swarm Agents
        self.planner = PlannerAgent(self.provider)
        self.architect = ArchitectAgent(self.provider)
        self.repo_mapper = RepoMapperAgent(self.provider)
        self.coder = CoderAgent(self.provider, permission_manager=self.permission_manager)
        self.tester = TesterAgent(self.provider)
        self.repair = RepairAgent(self.provider, permission_manager=self.permission_manager)
        self.reviewer = ReviewerAgent(self.provider)
        self.security_reviewer = SecurityReviewerAgent(self.provider)

    async def run_task(
        self,
        objective: str,
        repository_root: str,
        budget: Optional[TaskBudget] = None,
        risk_level: RiskLevel = RiskLevel.LOW,
        test_command: Optional[str] = None,
        on_step: Optional[Callable[[str, str, Optional[Dict[str, Any]]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Runs a complete autonomous coding task through the swarm pipeline.
        Returns final execution summary and artifacts.
        """
        def notify(state_name: str, message: str, payload: Any = None):
            if on_step:
                try:
                    on_step(state_name, message, payload)
                except Exception as e:
                    logger.debug(f"on_step callback error: {e}")
        contract = TaskContract(
            objective=objective,
            budget=budget or TaskBudget(
                max_iterations=12,
                max_agent_calls=30,
                max_tool_calls=60,
                max_retries=3,
                max_repeated_failures=3,
            ),
            risk_level=risk_level,
            metadata={"workflow": "coding", "is_coding_task": True},
        )

        runtime = CodingTaskRuntime(
            contract=contract,
            repo_root=repository_root,
            permission_manager=self.permission_manager,
            checkpoint_manager=self.checkpoint_manager,
        )

        if test_command:
            runtime.context.test_command = test_command

        supervisor = Supervisor()
        supervisor.start(contract)
        runtime.save_checkpoint()

        logger.info(f"[SWARM] Started coding task {contract.task_id} in {runtime.working_directory}")

        try:
            while not supervisor.is_done:
                runtime.sync_context()
                current_state = supervisor.state
                logger.info(f"[SWARM] State: {current_state.value} | Iteration: {contract.iterations}/{contract.budget.max_iterations}")

                # ─── 1. ANALYZE ───────────────────────────────────────────
                if current_state == TaskState.ANALYZE:
                    notify("ANALYZE", "Mapping repository symbols and dependency graph...")
                    repo_res = await self.repo_mapper.execute(
                        contract.objective,
                        {"coding_context": runtime.context, "repository_root": runtime.working_directory},
                    )
                    decision = supervisor.evaluate(repo_res)
                    supervisor.apply(decision)

                # ─── 2. PLAN ──────────────────────────────────────────────
                elif current_state == TaskState.PLAN:
                    notify("PLAN", "Formulating execution plan and file modification map...")
                    plan_res = await self.planner.execute(
                        contract.objective,
                        {"coding_context": runtime.context, "repo_map": runtime.context.relevant_files},
                    )
                    decision = supervisor.evaluate(plan_res)
                    supervisor.apply(decision)

                # ─── 3. ARCHITECT ─────────────────────────────────────────
                elif current_state == TaskState.ARCHITECT:
                    notify("ARCHITECT", "Specifying architecture constraints and interface boundaries...")
                    arch_res = await self.architect.execute(
                        contract.objective,
                        {
                            "coding_context": runtime.context,
                            "plan": runtime.context.plan,
                            "repo_map": runtime.context.relevant_files,
                        },
                    )
                    decision = supervisor.evaluate(arch_res)
                    supervisor.apply(decision)

                # ─── 4. EXECUTE (Coder) ───────────────────────────────────
                elif current_state == TaskState.EXECUTE:
                    notify("EXECUTE", f"Executing code edits (Iteration {contract.iterations}/{contract.budget.max_iterations})...")
                    coder_res = await self.coder.execute(
                        contract.objective,
                        {"coding_context": runtime.context, "worktree": runtime.working_directory},
                    )
                    decision = supervisor.evaluate(coder_res)
                    supervisor.apply(decision)

                # ─── 5. VERIFY (Tester) ───────────────────────────────────
                elif current_state == TaskState.VERIFY:
                    notify("VERIFY", f"Executing test suite: {runtime.context.test_command or 'pytest'}...")
                    tester_res = await self.tester.execute(
                        contract.objective,
                        {"coding_context": runtime.context, "worktree": runtime.working_directory},
                    )
                    decision = supervisor.evaluate(tester_res)
                    supervisor.apply(decision)

                # ─── 6. REPAIR (Repair Agent on failure) ──────────────────
                elif current_state == TaskState.REPAIR:
                    notify("REPAIR", "Diagnosing failure and synthesizing minimal patch...")
                    diff_text = runtime.workspace.get_diff()
                    repair_res = await self.repair.execute(
                        contract.objective,
                        {
                            "coding_context": runtime.context,
                            "worktree": runtime.working_directory,
                            "diff": diff_text,
                        },
                    )
                    decision = supervisor.evaluate(repair_res)
                    supervisor.apply(decision)

                # ─── 7. REVIEW (Parallel Code Review & Security Review) ───
                elif current_state == TaskState.REVIEW:
                    notify("REVIEW", "Running Code Review and Security Audit in parallel...")
                    diff_text = runtime.workspace.get_diff()

                    # Run Reviewer and SecurityReviewer in parallel safely
                    logger.info("[SWARM] Running Code Reviewer and Security Reviewer in parallel...")
                    rev_task = self.reviewer.execute(
                        contract.objective,
                        {"coding_context": runtime.context, "diff": diff_text},
                    )
                    sec_task = self.security_reviewer.execute(
                        contract.objective,
                        {"coding_context": runtime.context, "diff": diff_text},
                    )
                    rev_result, sec_result = await asyncio.gather(rev_task, sec_task)

                    # Evaluate Reviewer
                    rev_decision = supervisor.evaluate(rev_result)
                    supervisor.apply(rev_decision)

                    # If review approved and advanced to SECURITY_REVIEW, evaluate security
                    if supervisor.state == TaskState.SECURITY_REVIEW:
                        sec_decision = supervisor.evaluate(sec_result)
                        supervisor.apply(sec_decision)

                # ─── 8. SECURITY_REVIEW (Single-stage evaluation) ─────────
                elif current_state == TaskState.SECURITY_REVIEW:
                    notify("SECURITY_REVIEW", "Auditing security policies and protected zones...")
                    diff_text = runtime.workspace.get_diff()
                    sec_res = await self.security_reviewer.execute(
                        contract.objective,
                        {"coding_context": runtime.context, "diff": diff_text},
                    )
                    decision = supervisor.evaluate(sec_res)
                    supervisor.apply(decision)

                # ─── 9. WAITING_APPROVAL ──────────────────────────────────
                elif current_state == TaskState.WAITING_APPROVAL:
                    notify("WAITING_APPROVAL", "Task requires human approval to proceed.")
                    logger.warning("[SWARM] Task requires human approval to proceed.")
                    break

                # ─── 10. FINALIZE ─────────────────────────────────────────
                elif current_state == TaskState.FINALIZE:
                    notify("FINALIZE", "Finalizing verified changes and archiving artifacts...")
                    final_res = AgentResult(
                        agent_id="swarm_finalizer",
                        agent_type="finalizer",
                        status=AgentStatus.SUCCESS,
                        summary="Coding swarm completed task successfully with passing tests and verified security.",
                        artifacts=runtime.context.artifacts,
                    )
                    decision = supervisor.evaluate(final_res)
                    supervisor.apply(decision)

                # Save checkpoint after each state transition
                runtime.save_checkpoint()

            final_summary = supervisor.finalize_task()
            final_summary["diff"] = runtime.workspace.get_diff()
            final_summary["changed_files"] = runtime.workspace.get_changed_files()
            final_summary["worktree"] = runtime.working_directory
            runtime.save_checkpoint()
            return final_summary

        except Exception as e:
            logger.error(f"[SWARM] Unhandled swarm failure: {e}", exc_info=True)
            supervisor.cancel(f"Unhandled error: {e}")
            runtime.save_checkpoint()
            return {
                "task_id": contract.task_id,
                "status": "FAILED",
                "error": str(e),
                "success": False,
            }
