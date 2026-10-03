"""
HELIOS — Security Reviewer Agent
Audits code changes and diffs for security vulnerabilities:
command injection, path traversal, unsafe subprocess usage, permission bypass,
secret leakage, unsafe deserialization, sandbox escape, and credential exposure.
Does NOT modify code. Reports findings only.
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

logger = logging.getLogger("helios.agents.security_reviewer")


class SecurityVulnerability(BaseModel):
    vuln_type: str = Field(description="Vulnerability type (e.g. command_injection, path_traversal, secret_leakage, unsafe_subprocess, permission_bypass)")
    description: str
    severity: str = "high"  # "low", "medium", "high", "critical"
    file: Optional[str] = None
    recommendation: str = ""


class SecurityReviewReport(BaseModel):
    safe: bool = Field(description="Whether the code is safe to execute and finalize")
    requires_human_approval: bool = Field(default=False, description="Whether high-risk operations require human sign-off")
    vulnerabilities: List[SecurityVulnerability] = Field(default_factory=list)
    summary: str = ""


class SecurityReviewerAgent(BaseAgent):
    """
    Dedicated security auditor for AI code generations.
    Combines deterministic pattern scanning with LLM semantic security analysis.
    Has read-only authority.
    """

    def __init__(self, provider: BaseProvider, agent_id: Optional[str] = None):
        super().__init__(agent_id)
        self.provider = provider

    @property
    def agent_type(self) -> str:
        return "security_reviewer"

    def deterministic_scan(self, diff_text: str) -> List[SecurityVulnerability]:
        """Scans diff for obvious high-risk security patterns."""
        vulns = []

        # 1. Secret / token leakage
        secret_patterns = [
            (r"(?i)(api[_-]?key|secret|password|token)\s*=\s*['\"][A-Za-z0-9_\-\.]{16,}['\"]", "credential_exposure", "Potential hardcoded secret or API token detected"),
            (r"BEGIN (?:RSA |OPENSSH )?PRIVATE KEY", "credential_exposure", "Hardcoded private key detected"),
        ]
        for pattern, vtype, desc in secret_patterns:
            if re.search(pattern, diff_text):
                vulns.append(SecurityVulnerability(
                    vuln_type=vtype,
                    description=desc,
                    severity="critical",
                    recommendation="Remove hardcoded credentials and use environment variables.",
                ))

        # 2. Arbitrary code execution / deserialization
        unsafe_patterns = [
            (r"\bpickle\.loads?\(", "unsafe_deserialization", "Unsafe deserialization using pickle module"),
            (r"\beval\(", "arbitrary_execution", "Usage of eval() allows arbitrary code execution"),
            (r"\bexec\(", "arbitrary_execution", "Usage of exec() allows arbitrary code execution"),
            (r"os\.system\(", "command_injection", "os.system() is prone to command injection; use subprocess with explicit argv"),
            (r"subprocess\.(?:Popen|run|call)\([^,\)]*shell\s*=\s*True", "command_injection", "Subprocess invocation with shell=True"),
        ]
        for pattern, vtype, desc in unsafe_patterns:
            if re.search(pattern, diff_text):
                vulns.append(SecurityVulnerability(
                    vuln_type=vtype,
                    description=desc,
                    severity="high",
                    recommendation="Avoid dynamic evaluation or shell execution.",
                ))

        return vulns

    async def execute(self, objective: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        started_at = datetime.now(timezone.utc)
        context = context or {}

        coding_ctx: Optional[CodingContext] = context.get("coding_context")
        diff_text = context.get("diff", "")
        if not diff_text and coding_ctx:
            diff_text = context.get("diff", "")

        # 1. Deterministic Scan
        det_vulns = self.deterministic_scan(diff_text)

        # 2. Semantic LLM Review
        model_name, options = await model_router.prepare_model_for_agent("security_reviewer", self.provider)

        prompt = f"""You are the HELIOS Lead Cybersecurity Auditor.
Review the following code diff for security vulnerabilities:
- Command injection
- Path traversal
- Unsafe subprocess usage
- Permission / security bypass
- Secret / credential leakage
- Unsafe deserialization
- Sandbox escape possibilities

OBJECTIVE: {objective}
DIFF:
{diff_text if diff_text else "[Clean / no changes]"}

KNOWN DETERMINISTIC FINDINGS:
{[v.model_dump() for v in det_vulns]}

You MUST respond with valid JSON matching this schema:
{{
  "safe": true/false,
  "requires_human_approval": true/false,
  "vulnerabilities": [
    {{
      "vuln_type": "command_injection" | "path_traversal" | "secret_leakage" | "unsafe_subprocess",
      "description": "Details",
      "severity": "low" | "medium" | "high" | "critical",
      "recommendation": "Fix advice"
    }}
  ],
  "summary": "Concise summary of security posture"
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

            if not parsed or "safe" not in parsed:
                # Fallback to deterministic results
                is_safe = (len(det_vulns) == 0)
                parsed = {
                    "safe": is_safe,
                    "requires_human_approval": any(v.severity in ("high", "critical") for v in det_vulns),
                    "vulnerabilities": [v.model_dump() for v in det_vulns],
                    "summary": "Security posture verified by deterministic analyzer" if is_safe else f"Found {len(det_vulns)} potential security issues",
                }

            report = SecurityReviewReport(**parsed)
            # Merge deterministic findings if not present
            existing_desc = {v.description for v in report.vulnerabilities}
            for dv in det_vulns:
                if dv.description not in existing_desc:
                    report.vulnerabilities.append(dv)
                    report.safe = False

            if not report.safe:
                # If high/critical requiring human sign-off
                if report.requires_human_approval:
                    return self._make_result(
                        status=AgentStatus.NEEDS_APPROVAL,
                        summary=f"Security alert requires human approval: {report.summary}",
                        detail=report.model_dump_json(indent=2),
                        evidence={"security_report": report.model_dump()},
                        started_at=started_at,
                        confidence=0.95,
                    )
                return self._make_result(
                    status=AgentStatus.FAILURE,
                    summary=f"Security review failed: {report.summary}",
                    detail=report.model_dump_json(indent=2),
                    error=f"Security violations found: {[v.vuln_type for v in report.vulnerabilities]}",
                    evidence={"security_report": report.model_dump()},
                    started_at=started_at,
                    confidence=0.95,
                )

            return self._make_result(
                status=AgentStatus.SUCCESS,
                summary=f"Security review passed: {report.summary}",
                detail=report.model_dump_json(indent=2),
                evidence={"security_report": report.model_dump()},
                started_at=started_at,
                confidence=0.95,
            )

        except Exception as e:
            self.logger.error(f"SecurityReviewer error: {e}", exc_info=True)
            return self._make_result(
                status=AgentStatus.FAILURE,
                summary=f"Security review failed to complete: {str(e)}",
                error=str(e),
                started_at=started_at,
            )
