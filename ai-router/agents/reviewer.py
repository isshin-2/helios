"""
HELIOS — Reviewer Agent
Independently critiques code changes, git diffs, architectural compliance,
and potential regressions before finalization.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from agents.base import AgentResult, AgentStatus, BaseAgent
from core.coding_runtime import CodingContext
from core.model_router import model_router
from providers.base import BaseProvider

logger = logging.getLogger("helios.agents.reviewer")


class ReviewFinding(BaseModel):
    category: str = Field(description="Category: correctness, maintainability, architecture, unnecessary_changes, api_compatibility, regressions")
    description: str = Field(description="Details of the finding")
    severity: str = Field(default="medium", description="Severity: low, medium, high, critical")
    file: Optional[str] = None


class ReviewReport(BaseModel):
    approved: bool = Field(description="Whether the changes are approved for merge/finalize")
    severity: str = Field(default="none", description="Highest severity among findings")
    findings: List[ReviewFinding] = Field(default_factory=list)
    required_changes: List[str] = Field(default_factory=list)
    summary: str = ""


class ReviewerAgent(BaseAgent):
    """
    Independent code reviewer evaluating correctness, maintainability,
    architecture consistency, and unnecessary modifications.
    """

    def __init__(self, provider: BaseProvider, agent_id: Optional[str] = None):
        super().__init__(agent_id)
        self.provider = provider

    @property
    def agent_type(self) -> str:
        return "reviewer"

    async def execute(self, objective: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        started_at = datetime.now(timezone.utc)
        context = context or {}

        coding_ctx: Optional[CodingContext] = context.get("coding_context")
        diff_text = context.get("diff", "")
        if not diff_text and coding_ctx:
            diff_text = context.get("diff", "")
        test_results = (coding_ctx.test_results if coding_ctx else None) or context.get("test_results") or {}
        architecture = (coding_ctx.architecture if coding_ctx else None) or context.get("architecture") or {}

        model_name, options = await model_router.prepare_model_for_agent("reviewer", self.provider)

        prompt = f"""You are the HELIOS Lead Code Reviewer.
Evaluate the following proposed code modifications against the original objective and architecture.
Do NOT simply trust the coder. Look for regressions, unnecessary changes, API breaks, or poor error handling.

OBJECTIVE:
{objective}

ARCHITECTURE:
{json.dumps(architecture, indent=2)}

TEST RESULTS:
{json.dumps(test_results, indent=2)}

GIT DIFF:
{diff_text if diff_text else "[No diff provided or clean working tree]"}

You MUST respond strictly with valid JSON conforming to this schema:
{{
  "approved": true/false,
  "severity": "none" | "low" | "medium" | "high" | "critical",
  "findings": [
    {{
      "category": "correctness" | "architecture" | "unnecessary_changes" | "api_compatibility",
      "description": "Explanation",
      "severity": "low" | "medium" | "high" | "critical",
      "file": "path/to/file.py"
    }}
  ],
  "required_changes": ["Actionable change 1 if not approved"],
  "summary": "Overall evaluation summary"
}}
"""

        try:
            resp = await self.provider.generate(
                model=model_name,
                prompt=prompt,
                options=options,
                stream=False,
                format="json",
            )
            raw = resp.get("response", "").strip()

            parsed = None
            try:
                parsed = json.loads(raw)
            except Exception:
                m = re.search(r"(\{[\s\S]*\})", raw)
                if m:
                    parsed = json.loads(m.group(1))

            if not parsed or "approved" not in parsed:
                # Default heuristic if json parse fails: if tests passed and diff exists, approve with low severity
                tests_passed = test_results.get("status") == "success" or test_results.get("exit_code") == 0
                parsed = {
                    "approved": tests_passed,
                    "severity": "none" if tests_passed else "medium",
                    "findings": [],
                    "required_changes": [] if tests_passed else ["Resolve failing tests"],
                    "summary": "Automated fallback review evaluation",
                }

            report = ReviewReport(**parsed)

            if report.approved:
                return self._make_result(
                    status=AgentStatus.SUCCESS,
                    summary=f"Code review approved: {report.summary}",
                    detail=report.model_dump_json(indent=2),
                    evidence={"review": report.model_dump()},
                    started_at=started_at,
                    confidence=0.95,
                )
            else:
                return self._make_result(
                    status=AgentStatus.FAILURE,
                    summary=f"Code review rejected ({report.severity}): {report.summary}",
                    detail=f"Required changes: {report.required_changes}\nFindings: {report.findings}",
                    error=f"Review failed: {'; '.join(report.required_changes)}",
                    evidence={"review": report.model_dump()},
                    started_at=started_at,
                    confidence=0.9,
                )

        except Exception as e:
            self.logger.error(f"Reviewer error: {e}", exc_info=True)
            return self._make_result(
                status=AgentStatus.FAILURE,
                summary=f"Reviewer execution failed: {str(e)}",
                error=str(e),
                started_at=started_at,
            )
