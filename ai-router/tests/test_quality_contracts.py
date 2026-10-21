"""
Unit tests for core/quality_contracts.py.
Validates Pydantic serialization, finding lifecycle, and acceptance gate enforcement.
"""

import pytest
from core.quality_contracts import (
    AcceptanceGate,
    AuditFinding,
    CoverageLedger,
    CoverageLedgerEntry,
    FindingLifecycleStatus,
    FindingSeverity,
    LedgerEntryStatus,
    VerificationResult,
)


def test_acceptance_gate_unlazy_enforcement():
    gate = AcceptanceGate(
        task_id="task-123",
        required_tests=["pytest"],
        required_lints=["flake8"],
    )
    # No checks run yet -> must NOT be satisfied
    assert not gate.is_satisfied()

    # Add only one passing check
    gate.results.append(
        VerificationResult(check_name="pytest", exit_code=0, passed=True)
    )
    assert not gate.is_satisfied()

    # Add failing lint
    gate.results.append(
        VerificationResult(check_name="flake8", exit_code=1, passed=False)
    )
    assert not gate.is_satisfied()

    # Replace with passing lint
    gate.results[-1] = VerificationResult(check_name="flake8", exit_code=0, passed=True)
    assert gate.is_satisfied()


def test_coverage_ledger_staleness():
    ledger = CoverageLedger(
        repo_path="/test/repo",
        entries={
            "src/app.py": CoverageLedgerEntry(
                file_path="src/app.py",
                sha256_hash="hash_a",
                status=LedgerEntryStatus.COMPLETED,
            )
        },
    )
    # Same hash -> not stale
    assert not ledger.is_file_stale("src/app.py", "hash_a")
    # Different hash -> stale
    assert ledger.is_file_stale("src/app.py", "hash_modified")
    # New file -> stale
    assert ledger.is_file_stale("src/other.py", "hash_b")


def test_audit_finding_lifecycle():
    finding = AuditFinding(
        finding_id="SEC-001",
        run_id="run-1",
        title="Command Injection",
        severity=FindingSeverity.HIGH,
        confidence=0.9,
        lifecycle_status=FindingLifecycleStatus.NEEDS_VALIDATION,
        affected_file="main.py",
        description="os.system call with user input",
        attack_scenario="Attacker injects ; rm -rf",
        evidence="os.system(user_param)",
        remediation="Use subprocess with explicit args",
    )
    assert finding.lifecycle_status == FindingLifecycleStatus.NEEDS_VALIDATION
    finding.lifecycle_status = FindingLifecycleStatus.CONFIRMED
    assert finding.lifecycle_status == FindingLifecycleStatus.CONFIRMED
