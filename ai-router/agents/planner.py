"""
HELIOS — Planner Agent
Breaks down objectives into structured requirements, dependencies,
implementation steps, expected files, test strategies, and risks.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from agents.base import AgentResult, AgentStatus, BaseAgent
from core.model_router import model_router
from gateway.tool_gateway import ToolGateway
from providers.base import BaseProvider

logger = logging.getLogger("helios.agents.planner")


class PlanStep(BaseModel):
    step: int
    action: str
    target_files: List[str] = Field(default_factory=list)
    tool: Optional[str] = None
    verification: Optional[str] = None


class PlanOutput(BaseModel):
    objective: str
    requirements: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    implementation_steps: List[PlanStep] = Field(default_factory=list)
    expected_files: List[str] = Field(default_factory=list)
    test_strategy: str = "Execute automated unit tests and verify regressions"
    risks: List[str] = Field(default_factory=list)


class PlannerAgent(BaseAgent):
    """
    Analyzes coding objectives and outputs a formal PlanOutput structure.
    Integrates with ModelRouter for hardware-aware model configuration.
    """

    def __init__(
        self,
        provider: BaseProvider,
        tool_gateway: Optional[ToolGateway] = None,
        agent_id: Optional[str] = None,
    ):
        super().__init__(agent_id)
        self.provider = provider
        self.tool_gateway = tool_gateway

    @property
    def agent_type(self) -> str:
        return "planner"

    def _extract_json_object(self, text: str) -> Optional[Dict[str, Any]]:
        """Robust JSON extraction handling markdown blocks or nested text."""
        text = text.strip()
        # Direct parse attempt
        try:
            return json.loads(text)
        except Exception:
            pass

        # Match ```json ... ``` blocks
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except Exception:
                pass

        # Match outermost curly braces
        brace_match = re.search(r"(\{[\s\S]*\})", text)
        if brace_match:
            try:
                return json.loads(brace_match.group(1))
            except Exception:
                pass

        return None

    async def execute(self, objective: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        started_at = datetime.now(timezone.utc)
        context = context or {}

        # 1. Retrieve configured model and parameters via ModelRouter
        model_name, options = await model_router.prepare_model_for_agent("planner", self.provider)

        schema_json = json.dumps(PlanOutput.model_json_schema(), indent=2)
        repo_info = context.get("repo_map", "") or context.get("relevant_files", "")

        prompt = f"""You are the HELIOS Lead Planner Agent for a software engineering swarm.
Your job is to thoroughly analyze the objective and repository context, then formulate a comprehensive execution plan.

OBJECTIVE:
{objective}

REPOSITORY CONTEXT:
{repo_info}

You MUST respond strictly with valid JSON conforming to the following JSON schema:
{schema_json}
"""

        try:
            # 2. Invoke provider with structured JSON request
            response = await self.provider.generate(
                model=model_name,
                prompt=prompt,
                options=options,
                stream=False,
                format="json",
            )
            raw_text = response.get("response", "").strip()
            parsed_json = self._extract_json_object(raw_text)

            if not parsed_json:
                # Fallback to structured fallback if model returned non-json
                parsed_json = {
                    "objective": objective,
                    "requirements": [objective],
                    "dependencies": [],
                    "implementation_steps": [
                        {"step": 1, "action": f"Implement objective: {objective}", "target_files": []}
                    ],
                    "expected_files": [],
                    "test_strategy": "Run project test suite",
                    "risks": ["Model output required normalization"],
                }

            plan_obj = PlanOutput(**parsed_json)

            # Update CodingContext if present
            if "coding_context" in context and hasattr(context["coding_context"], "plan"):
                context["coding_context"].plan = plan_obj.model_dump()
                context["coding_context"].relevant_files = list(
                    set(context["coding_context"].relevant_files + plan_obj.expected_files)
                )

            return self._make_result(
                status=AgentStatus.SUCCESS,
                summary=f"Created structured plan with {len(plan_obj.implementation_steps)} steps.",
                detail=plan_obj.model_dump_json(indent=2),
                evidence={"plan": plan_obj.model_dump()},
                started_at=started_at,
                confidence=0.95,
            )

        except Exception as e:
            self.logger.error(f"Planner error: {e}", exc_info=True)
            return self._make_result(
                status=AgentStatus.FAILURE,
                summary=f"Planner execution failed: {str(e)}",
                error=str(e),
                started_at=started_at,
            )
