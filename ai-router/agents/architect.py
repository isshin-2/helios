"""
HELIOS — Architect Agent
Synthesizes planner output, contracts, and repository patterns to define
system boundaries, interfaces, constraints, and files to modify or create.
Does NOT write implementation code.
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
from providers.base import BaseProvider

logger = logging.getLogger("helios.agents.architect")


class ArchitectureSpec(BaseModel):
    """Structured architectural specification."""
    components: List[str] = Field(default_factory=list, description="Components or subsystems involved.")
    interfaces: List[str] = Field(default_factory=list, description="Key interfaces, classes, or signatures to reuse/extend.")
    files_to_modify: List[str] = Field(default_factory=list, description="Existing files to change.")
    files_to_create: List[str] = Field(default_factory=list, description="New files to introduce.")
    constraints: List[str] = Field(default_factory=list, description="Architectural and compatibility constraints.")
    test_strategy: List[str] = Field(default_factory=list, description="Testing boundaries and verification plan.")
    risks: List[str] = Field(default_factory=list, description="Potential architectural regressions or hazards.")
    data_flow: Optional[str] = Field(default=None, description="Data flow description.")
    failure_handling: Optional[str] = Field(default=None, description="Strategy for failure and exception recovery.")


class ArchitectAgent(BaseAgent):
    """
    Evaluates system design and outputs an ArchitectureSpec.
    Ensures that changes maintain consistency with the existing codebase.
    """

    def __init__(self, provider: BaseProvider, agent_id: Optional[str] = None):
        super().__init__(agent_id)
        self.provider = provider

    @property
    def agent_type(self) -> str:
        return "architect"

    def _extract_json_object(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON cleanly from LLM response."""
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            pass

        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except Exception:
                pass

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

        model_name, options = await model_router.prepare_model_for_agent("architect", self.provider)

        plan = context.get("plan", {})
        repo_map = context.get("repo_map", "")
        schema_json = json.dumps(ArchitectureSpec.model_json_schema(), indent=2)

        prompt = f"""You are the HELIOS Lead Software Architect.
Analyze the following objective, high-level plan, and repository context.
Design the architectural specification for the implementation.
Do NOT write code implementation. Focus on design, component interfaces, files to modify/create, constraints, and failure handling.

OBJECTIVE:
{objective}

PLAN:
{json.dumps(plan, indent=2) if isinstance(plan, dict) else str(plan)}

REPOSITORY CONTEXT:
{repo_map}

You MUST output strictly valid JSON matching this schema:
{schema_json}
"""

        try:
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
                parsed_json = {
                    "components": ["Core"],
                    "interfaces": [],
                    "files_to_modify": [],
                    "files_to_create": [],
                    "constraints": ["Preserve existing public API and backwards compatibility"],
                    "test_strategy": ["Run targeted unit tests"],
                    "risks": ["Potential regressions in callers"],
                }

            spec = ArchitectureSpec(**parsed_json)

            # Sync with CodingContext if available
            coding_ctx = context.get("coding_context")
            if coding_ctx and hasattr(coding_ctx, "architecture"):
                coding_ctx.architecture = spec.model_dump()
                combined_files = set(coding_ctx.relevant_files)
                combined_files.update(spec.files_to_modify)
                combined_files.update(spec.files_to_create)
                coding_ctx.relevant_files = sorted(list(combined_files))

            return self._make_result(
                status=AgentStatus.SUCCESS,
                summary=f"Architecture spec created: {len(spec.files_to_modify)} files to modify, {len(spec.files_to_create)} to create.",
                detail=spec.model_dump_json(indent=2),
                evidence={"architecture": spec.model_dump()},
                started_at=started_at,
                confidence=0.95,
            )

        except Exception as e:
            self.logger.error(f"Architect error: {e}", exc_info=True)
            return self._make_result(
                status=AgentStatus.FAILURE,
                summary=f"Architect execution failed: {str(e)}",
                error=str(e),
                started_at=started_at,
            )
