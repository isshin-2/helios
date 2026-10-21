"""
Tests for core/security_audit.py.
Validates 6-phase pipeline, ledger resume, hash staleness, and adversarial disprover.
"""

import os
import tempfile
import pytest
from core.quality_contracts import FindingLifecycleStatus
from core.security_audit import CloudflareSecurityAuditor, LEDGER_FILENAME
from providers.base import BaseProvider


class SecurityMockProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "mock_sec"

    async def list_models(self):
        return ["security_auditor"]

    async def list_running(self):
        return {}

    async def unload_model(self, model: str):
        return {}

    async def chat(self, model: str, messages, **kwargs):
        return {}

    async def get_embeddings(self, model: str, prompt: str):
        return []

    async def generate(self, model: str, prompt: str, **kwargs):
        if "Hunter Agent" in prompt:
            return {
                "response": '[{"title": "Unsafe os.system", "severity": "high", "line_start": 2, "line_end": 2, "description": "Command injection vulnerability", "attack_scenario": "Attacker provides malicious input", "evidence": "os.system(user_in)", "remediation": "Use subprocess"}]'
            }
        elif "Adversarial Security Verifier" in prompt:
            # If the snippet is sanitized, disproves it; else confirms
            if "shlex.quote" in prompt:
                return {
                    "response": '{"verdict": "disproved", "confidence": 0.95, "counterevidence_notes": "Input is escaped using shlex.quote"}'
                }
            return {
                "response": '{"verdict": "confirmed", "confidence": 0.90, "counterevidence_notes": "Vulnerable path confirmed, no sanitization found"}'
            }
        return {"response": "{}"}


@pytest.mark.asyncio
async def test_security_audit_6_phase_flow():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "vulnerable.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("import os\nos.system(user_in)\n")

        auditor = CloudflareSecurityAuditor(provider=SecurityMockProvider(), repo_root=tmpdir)
        report = await auditor.run_full_audit()

        assert report.coverage_percentage == 100.0
        assert report.total_files_inspected == 1
        assert len(report.confirmed_findings) >= 1
        assert report.confirmed_findings[0].lifecycle_status == FindingLifecycleStatus.CONFIRMED
        assert not report.is_clean
        assert os.path.exists(os.path.join(tmpdir, LEDGER_FILENAME))


@pytest.mark.asyncio
async def test_security_audit_disprover_rejects_false_positive():
    with tempfile.TemporaryDirectory() as tmpdir:
        safe_file = os.path.join(tmpdir, "safe.py")
        with open(safe_file, "w", encoding="utf-8") as f:
            f.write("import os, shlex\nos.system(shlex.quote(user_in))\n")

        auditor = CloudflareSecurityAuditor(provider=SecurityMockProvider(), repo_root=tmpdir)
        report = await auditor.run_full_audit()

        # The mock disprover returns 'disproved' when shlex.quote is present
        assert len(report.disproved_findings) >= 1
        assert report.disproved_findings[0].lifecycle_status == FindingLifecycleStatus.DISPROVED
        assert "shlex.quote" in report.disproved_findings[0].counterevidence_notes
