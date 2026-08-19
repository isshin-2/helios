"""
HELIOS — Self-Modification Validator
======================================
Risk classification and path validation for self-modification experiments.
Does NOT duplicate the PermissionManager — defers to it for all security decisions.
"""

import os
from pathlib import Path
from typing import Optional

from security.permissions import PermissionManager, HELIOS_DIR
from .models import RiskLevel


# ─── Risk Classification ────────────────────────────────────────────────────

# Paths whose modification is classified as HIGH risk
HIGH_RISK_PREFIXES = [
    "tools/",
    "db.py",
]

# Paths classified as MEDIUM risk
MEDIUM_RISK_PREFIXES = [
    "skills/",
    "router/",
    "core/",
]

# Everything else (prompts/, static/, frontend/, plugins/, experiments/) is LOW


def classify_risk(target_path: str) -> RiskLevel:
    """
    Classify the risk level of modifying a given target path.
    
    Protected paths are not classified here — the PermissionManager
    rejects them outright. This only classifies paths that have already
    passed the protection check.
    """
    normalized = target_path.replace("\\", "/").lower()

    for prefix in HIGH_RISK_PREFIXES:
        if normalized.startswith(prefix.lower()):
            return RiskLevel.HIGH

    for prefix in MEDIUM_RISK_PREFIXES:
        if normalized.startswith(prefix.lower()):
            return RiskLevel.MEDIUM

    return RiskLevel.LOW


def validate_experiment_source(source_path: Path, experiment_dir: Path) -> bool:
    """
    Verify that a source file is actually inside the experiment's modified/ directory.
    Prevents metadata from redirecting the source outside the experiment.
    """
    try:
        resolved_source = source_path.resolve(strict=False)
        resolved_experiment = (experiment_dir / "modified").resolve(strict=False)

        # Check containment using parent chain
        return (resolved_source == resolved_experiment or
                resolved_experiment in resolved_source.parents)
    except (OSError, ValueError):
        return False


def validate_experiment_target(target_path: str,
                               permission_manager: PermissionManager) -> bool:
    """
    Verify that a production target is inside HELIOS and is not protected.
    Does NOT check user write permissions — that is done separately during deployment.
    """
    try:
        resolved = Path(target_path).resolve(strict=False)
        helios_resolved = Path(HELIOS_DIR).resolve(strict=False)

        # Must be inside HELIOS
        if not (resolved == helios_resolved or
                helios_resolved in resolved.parents):
            return False

        # Must not be protected
        if permission_manager.is_protected_path(resolved):
            return False

        return True
    except (OSError, ValueError):
        return False
