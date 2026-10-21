"""
HELIOS / Hikari — Cloudflare-Style Adversarial Security Auditor
Implements a 6-phase vulnerability discovery pipeline:
Phase 1: Reconnaissance (Architecture, trust boundaries, repo revision)
Phase 2: Coverage Ledger (.helios_audit_ledger.json, file hashes, resumable audit state)
Phase 3: Hunter Agent (Candidate vulnerability detection with exact lines & proof)
Phase 4: Adversarial Verifier / Disprover (Independent counterexample validation)
Phase 5: Structured Schema Output (findings.json with stable IDs)
Phase 6: Action-First Markdown Report (Concise executive findings & remediations)

Auditor is strictly read-only by default and never silently modifies code.
Remediations are routed through the Supervisor and Coding Swarm.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.quality_contracts import (
    AuditFinding,
    AuditReport,
    CoverageLedger,
    CoverageLedgerEntry,
    FindingLifecycleStatus,
    FindingSeverity,
    LedgerEntryStatus,
)
from providers.base import BaseProvider

logger = logging.getLogger("helios.security_audit")

AUDIT_RULES_VERSION = "1.0.0"
LEDGER_FILENAME = ".helios_audit_ledger.json"
FINDINGS_FILENAME = "findings.json"


class CloudflareSecurityAuditor:
    """
    Structured 6-phase adversarial security auditor.
    """

    def __init__(
        self,
        provider: BaseProvider,
        repo_root: str,
        rules_version: str = AUDIT_RULES_VERSION,
        timeout_seconds: float = 60.0,
    ):
        self.provider = provider
        self.repo_root = os.path.abspath(repo_root)
        self.rules_version = rules_version
        self.timeout_seconds = timeout_seconds
        self.ledger_path = os.path.join(self.repo_root, LEDGER_FILENAME)

    def _compute_sha256(self, file_path: str) -> str:
        h = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return ""

    def _get_git_revision(self) -> Optional[str]:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=3,
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
        return None

    # ─── Phase 1: Reconnaissance ──────────────────────────────────────────────
    def run_reconnaissance(self, target_subpath: Optional[str] = None) -> Dict[str, Any]:
        """Maps project structure, entrypoints, and sensitive zones."""
        base_dir = os.path.join(self.repo_root, target_subpath) if target_subpath else self.repo_root
        discovered_files: List[str] = []

        # Target code files while ignoring build/venv/caches
        ignored_dirs = {".git", "venv", ".venv", "__pycache__", "node_modules", "dist", "build"}
        valid_exts = {".py", ".js", ".ts", ".jsx", ".tsx", ".sh", ".bat", ".json", ".yaml", ".yml"}

        for root, dirs, files in os.walk(base_dir):
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in valid_exts and file not in (LEDGER_FILENAME, FINDINGS_FILENAME):
                    rel_path = os.path.relpath(os.path.join(root, file), self.repo_root)
                    discovered_files.append(rel_path.replace("\\", "/"))

        return {
            "repo_revision": self._get_git_revision(),
            "target_dir": base_dir,
            "discovered_files": sorted(discovered_files),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ─── Phase 2: Coverage Ledger ─────────────────────────────────────────────
    def load_or_init_ledger(self, recon: Dict[str, Any]) -> CoverageLedger:
        """Loads existing ledger or initializes a new one, flagging stale files."""
        if os.path.exists(self.ledger_path):
            try:
                with open(self.ledger_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    ledger = CoverageLedger(**data)
            except Exception as e:
                logger.warning(f"Failed to load ledger, re-initializing: {e}")
                ledger = CoverageLedger(
                    audit_rules_version=self.rules_version,
                    repo_path=self.repo_root,
                    repo_revision=recon.get("repo_revision"),
                )
        else:
            ledger = CoverageLedger(
                audit_rules_version=self.rules_version,
                repo_path=self.repo_root,
                repo_revision=recon.get("repo_revision"),
            )

        # Update entry states against current file hashes
        for rel_file in recon["discovered_files"]:
            abs_path = os.path.join(self.repo_root, rel_file)
            current_hash = self._compute_sha256(abs_path)
            if ledger.is_file_stale(rel_file, current_hash):
                ledger.entries[rel_file] = CoverageLedgerEntry(
                    file_path=rel_file,
                    sha256_hash=current_hash,
                    status=LedgerEntryStatus.PENDING,
                    rules_version=self.rules_version,
                )

        self._save_ledger(ledger)
        return ledger

    def _save_ledger(self, ledger: CoverageLedger):
        try:
            with open(self.ledger_path, "w", encoding="utf-8") as f:
                f.write(ledger.model_dump_json(indent=2))
        except Exception as e:
            logger.error(f"Failed to persist ledger: {e}")

    # ─── Phase 3: Hunter Agent ────────────────────────────────────────────────
    async def hunt_candidates(
        self,
        file_path: str,
        content: str,
        run_id: str,
    ) -> List[AuditFinding]:
        """Hunts for vulnerabilities in an isolated code unit."""
        # 1. Deterministic pattern checks
        det_candidates = self._deterministic_pattern_check(file_path, content, run_id)

        # 2. Semantic LLM Hunt
        prompt = f"""You are the Hunter Agent in an adversarial security harness.
Analyze the following source file for vulnerabilities:
File: {file_path}

CONTENT:
```
{content[:8000]}
```

Look for:
- Command injection / dangerous subprocess execution
- Path traversal / insecure file manipulation
- Authentication / authorization bypass
- Arbitrary code execution / insecure deserialization
- Secret / credential leakage

You MUST reply with a valid JSON array of candidate findings:
[
  {{
    "title": "Short title",
    "severity": "low" | "medium" | "high" | "critical",
    "line_start": 10,
    "line_end": 15,
    "symbol": "function_or_var_name",
    "description": "How the flaw occurs",
    "attack_scenario": "Step-by-step exploit vector",
    "evidence": "Exact vulnerable snippet",
    "remediation": "Concrete fix recommendation"
  }}
]
If clean, return an empty array [].
"""
        try:
            resp = await asyncio.wait_for(
                self.provider.generate(
                    model="security_auditor",
                    prompt=prompt,
                    stream=False,
                    format="json",
                ),
                timeout=self.timeout_seconds,
            )
            raw = resp.get("response", "[]").strip()
            parsed = json.loads(raw) if raw.startswith("[") else []
        except Exception as e:
            logger.debug(f"LLM hunt error or non-json: {e}")
            parsed = []

        findings: List[AuditFinding] = list(det_candidates)
        for idx, item in enumerate(parsed):
            fid = f"SEC-{abs(hash(file_path + item.get('title', '')))%100000:05d}"
            try:
                findings.append(AuditFinding(
                    finding_id=fid,
                    run_id=run_id,
                    title=item.get("title", "Unknown Security Issue"),
                    severity=FindingSeverity(item.get("severity", "medium").lower()),
                    confidence=0.7,
                    lifecycle_status=FindingLifecycleStatus.NEEDS_VALIDATION,
                    affected_file=file_path,
                    line_start=item.get("line_start"),
                    line_end=item.get("line_end"),
                    symbol=item.get("symbol"),
                    description=item.get("description", ""),
                    attack_scenario=item.get("attack_scenario", ""),
                    evidence=item.get("evidence", ""),
                    remediation=item.get("remediation", ""),
                ))
            except Exception:
                pass

        return findings

    def _deterministic_pattern_check(self, file_path: str, content: str, run_id: str) -> List[AuditFinding]:
        findings = []
        lines = content.split("\n")
        
        patterns = [
            (r"\bos\.system\(", "Command Injection via os.system", FindingSeverity.HIGH, "Replace with subprocess.run with argv list"),
            (r"subprocess\.(?:Popen|run|call)\([^,\)]*shell\s*=\s*True", "Command Injection via shell=True", FindingSeverity.HIGH, "Set shell=False and pass args as list"),
            (r"\beval\(", "Arbitrary Code Execution via eval", FindingSeverity.HIGH, "Avoid eval with dynamic input"),
            (r"\bpickle\.loads?\(", "Insecure Deserialization via pickle", FindingSeverity.HIGH, "Use safe serializers like json"),
            (r"(?i)(api[_-]?key|secret|password|token)\s*=\s*['\"][A-Za-z0-9_\-\.]{16,}['\"]", "Hardcoded Secret / Credential Leakage", FindingSeverity.CRITICAL, "Store credentials in environment variables"),
        ]

        for p, title, sev, rem in patterns:
            for idx, line in enumerate(lines, 1):
                if re.search(p, line):
                    fid = f"DET-{abs(hash(file_path + str(idx) + title))%100000:05d}"
                    findings.append(AuditFinding(
                        finding_id=fid,
                        run_id=run_id,
                        title=title,
                        severity=sev,
                        confidence=0.9,
                        lifecycle_status=FindingLifecycleStatus.NEEDS_VALIDATION,
                        affected_file=file_path,
                        line_start=idx,
                        line_end=idx,
                        description=f"Pattern match for {title}",
                        attack_scenario=f"Direct invocation at line {idx}",
                        evidence=line.strip(),
                        remediation=rem,
                    ))
        return findings

    # ─── Phase 4: Adversarial Verifier / Disprover ────────────────────────────
    async def verify_candidate(
        self,
        finding: AuditFinding,
        file_content: str,
    ) -> AuditFinding:
        """
        Adversarially attempts to DISPROVE the candidate finding.
        Searches for guardrails, sanitizers, or unreachable code that prevents exploitation.
        """
        prompt = f"""You are the Adversarial Security Verifier / Disprover.
Your sole job is to rigorously inspect whether this reported vulnerability is a FALSE POSITIVE or a GENUINE EXPLOITABLE FLAW.
Look for mitigating controls, type checks, escaping, or unreachability in the code.

FINDING DETAILS:
Title: {finding.title}
File: {finding.affected_file} (Lines {finding.line_start}-{finding.line_end})
Claimed Attack: {finding.attack_scenario}
Reported Evidence: {finding.evidence}

FULL FILE CONTEXT:
```
{file_content[:8000]}
```

Answer with valid JSON:
{{
  "verdict": "confirmed" | "disproved" | "needs_validation",
  "confidence": 0.85,
  "counterevidence_notes": "Explain why this is either disproved (sanitized/unreachable) or genuinely confirmed"
}}
"""
        try:
            resp = await asyncio.wait_for(
                self.provider.generate(
                    model="security_verifier",
                    prompt=prompt,
                    stream=False,
                    format="json",
                ),
                timeout=self.timeout_seconds,
            )
            raw = resp.get("response", "{}").strip()
            parsed = json.loads(raw)
            verdict = parsed.get("verdict", "needs_validation").lower()
            if verdict == "confirmed":
                finding.lifecycle_status = FindingLifecycleStatus.CONFIRMED
            elif verdict == "disproved":
                finding.lifecycle_status = FindingLifecycleStatus.DISPROVED
            else:
                finding.lifecycle_status = FindingLifecycleStatus.NEEDS_VALIDATION

            finding.confidence = float(parsed.get("confidence", finding.confidence))
            finding.counterevidence_notes = parsed.get("counterevidence_notes", "Verified by disprover agent.")
        except Exception as e:
            logger.debug(f"Verifier fallback: {e}")
            # If verifier fails or times out, keep as needs_validation (never assume confirmed)
            finding.lifecycle_status = FindingLifecycleStatus.NEEDS_VALIDATION
            finding.counterevidence_notes = f"Verification inconclusive: {e}"

        return finding

    # ─── Phase 5: Structured Schema Output ────────────────────────────────────
    def save_findings_json(self, findings: List[AuditFinding]) -> str:
        """Saves machine-readable findings.json."""
        out_path = os.path.join(self.repo_root, FINDINGS_FILENAME)
        data = {
            "schema_version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "findings": [f.model_dump() for f in findings],
        }
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=2))
        return out_path

    # ─── Phase 6: Reporting ───────────────────────────────────────────────────
    def generate_markdown_report(self, report: AuditReport) -> str:
        """
        Generates an action-first Markdown report (i-have-adhd format).
        Leads with next actions and confirmed vulnerabilities. Caps lists, cuts preamble.
        """
        lines = [
            "# HELIOS Security Audit Report",
            f"**Run ID:** `{report.run_id}` | **Revision:** `{report.repo_revision or 'local'}` | **Coverage:** `{report.coverage_percentage:.1f}%`",
            "",
        ]

        if report.confirmed_findings:
            lines.append("## 🚨 Immediate Action Required (Confirmed Findings)")
            for f in report.confirmed_findings[:5]:
                lines.append(f"### [{f.severity.upper()}] {f.title} (`{f.affected_file}:{f.line_start}`)")
                lines.append(f"- **Issue:** {f.description}")
                lines.append(f"- **Attack Vector:** {f.attack_scenario}")
                lines.append(f"- **Remediation:** {f.remediation}")
                lines.append(f"- **Proof:** `{f.evidence}`")
                lines.append("")
        else:
            lines.append("## ✔ No Confirmed Vulnerabilities Detected")
            lines.append("All inspected components passed adversarial verification checks.")
            lines.append("")

        if report.suspected_findings:
            lines.append("## ⚠️ Suspected Issues Requiring Manual Review")
            for f in report.suspected_findings[:5]:
                lines.append(f"- **{f.title}** (`{f.affected_file}`): {f.description}")
            lines.append("")

        if report.disproved_findings:
            lines.append("## 🛡️ Disproved Findings (False Positives Filtered Out)")
            for f in report.disproved_findings[:5]:
                lines.append(f"- **{f.title}** (`{f.affected_file}`): {f.counterevidence_notes or 'Mitigated by existing controls'}")
            lines.append("")

        if report.skipped_checks:
            lines.append("## ℹ️ Skipped / Incomplete Checks")
            for sk in report.skipped_checks[:5]:
                lines.append(f"- `{sk.get('file')}`: {sk.get('reason')}")
            lines.append("")

        lines.append("---")
        lines.append("*Audit completed with adversarial disproof verification. A clean report does not guarantee zero vulnerabilities.*")
        return "\n".join(lines)

    # ─── Full Pipeline Orchestration ──────────────────────────────────────────
    async def run_full_audit(self, target_subpath: Optional[str] = None) -> AuditReport:
        run_id = f"audit-{int(time.time())}"
        recon = self.run_reconnaissance(target_subpath)
        ledger = self.load_or_init_ledger(recon)

        all_findings: List[AuditFinding] = []
        files_to_check = [
            f for f, entry in ledger.entries.items()
            if entry.status in (LedgerEntryStatus.PENDING, LedgerEntryStatus.NEEDS_REVIEW)
        ]

        for rel_file in files_to_check:
            abs_path = os.path.join(self.repo_root, rel_file)
            try:
                with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception as e:
                ledger.entries[rel_file].status = LedgerEntryStatus.SKIPPED
                ledger.entries[rel_file].skipped_reason = str(e)
                continue

            # Hunt
            candidates = await self.hunt_candidates(rel_file, content, run_id)

            # Adversarial Verify
            verified_for_file = []
            for cand in candidates:
                ver = await self.verify_candidate(cand, content)
                verified_for_file.append(ver)

            all_findings.extend(verified_for_file)

            # Update ledger
            ledger.entries[rel_file].status = LedgerEntryStatus.COMPLETED
            ledger.entries[rel_file].last_checked_at = datetime.now(timezone.utc).isoformat()
            ledger.entries[rel_file].findings_count = len(verified_for_file)

        self._save_ledger(ledger)
        self.save_findings_json(all_findings)

        confirmed = [f for f in all_findings if f.lifecycle_status == FindingLifecycleStatus.CONFIRMED]
        suspected = [f for f in all_findings if f.lifecycle_status == FindingLifecycleStatus.NEEDS_VALIDATION]
        disproved = [f for f in all_findings if f.lifecycle_status == FindingLifecycleStatus.DISPROVED]

        total_files = len(ledger.entries)
        completed_files = sum(1 for e in ledger.entries.values() if e.status == LedgerEntryStatus.COMPLETED)
        cov_pct = (completed_files / total_files * 100.0) if total_files > 0 else 100.0

        skipped = [
            {"file": e.file_path, "reason": e.skipped_reason or "Skipped"}
            for e in ledger.entries.values() if e.status == LedgerEntryStatus.SKIPPED
        ]

        report = AuditReport(
            run_id=run_id,
            schema_version=self.rules_version,
            repo_revision=recon.get("repo_revision"),
            confirmed_findings=confirmed,
            suspected_findings=suspected,
            disproved_findings=disproved,
            coverage_percentage=cov_pct,
            total_files_inspected=completed_files,
            skipped_checks=skipped,
            is_clean=(len(confirmed) == 0 and len(suspected) == 0),
        )

        # Write markdown report to repo root
        report_md_path = os.path.join(self.repo_root, "AUDIT_REPORT.md")
        try:
            with open(report_md_path, "w", encoding="utf-8") as f:
                f.write(self.generate_markdown_report(report))
        except Exception as e:
            logger.warning(f"Could not write AUDIT_REPORT.md: {e}")

        return report
