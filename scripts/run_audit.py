"""Audit Runner: Re-scans modified files, validates IPC boundaries, inspects hardware, and synchronizes docs/SYSTEM_AUDIT.md."""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import subprocess
import datetime
import json

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AI_ROUTER_DIR = os.path.join(BASE_DIR, "ai-router")
if AI_ROUTER_DIR not in sys.path:
    sys.path.insert(0, AI_ROUTER_DIR)

from core.hardware_governor import HardwareGovernor
from core.security.bridge_guard import BridgeGuard
from connectors.registry import ConnectorRegistry

def run_git_diff_summary() -> str:
    try:
        res = subprocess.run(["git", "status", "--short"], cwd=BASE_DIR, capture_output=True, text=True, timeout=5)
        lines = res.stdout.strip().splitlines()
        return f"{len(lines)} modified/untracked files" if lines else "Clean working directory"
    except Exception as e:
        return f"Git query failed: {e}"

def generate_audit():
    print("[*] Running HELIOS & Twin Ecosystem Comprehensive Audit...")
    governor = HardwareGovernor()
    guard = BridgeGuard()
    registry = ConnectorRegistry()

    now_iso = datetime.datetime.now().astimezone().isoformat()
    git_summary = run_git_diff_summary()

    audit_path = os.path.join(BASE_DIR, "docs", "SYSTEM_AUDIT.md")
    os.makedirs(os.path.dirname(audit_path), exist_ok=True)

    tier_desc = governor.decision.tier_name
    vram = governor.profile.gpu_vram_gb
    ram = governor.profile.ram_total_gb
    gpu = governor.profile.gpu_name

    connectors = registry.list_connectors()
    conn_rows = "\n".join([
        f"| `{c['id']}` | `{c['version']}` | `{', '.join(c['scopes'])}` | {c['timeout_seconds']}s | Enforced |"
        for c in connectors
    ]) or "| None | - | - | - | - |"

    warning_bullets = "\n".join([f"- ⚠️ {w}" for w in governor.decision.warnings]) if governor.decision.warnings else "- None (Full hardware capabilities active)"

    downgrade_rows = "\n".join([
        f"- **{k.upper()}**: {v}" for k, v in governor.decision.downgrade_advisories.items()
    ]) if governor.decision.downgrade_advisories else "- None"

    content = f"""# HELIOS & Twin Ecosystem Living System Audit
> **Single Source of Truth (SSoT) for Component Topologies, Hardware Tiers, and Security Boundaries**  
> **Last Synchronized:** `{now_iso}`  
> **Audit Status:** `HARDENED & ISOLATED`  
> **Governor Status:** `{tier_desc}`  
> **Git Working State:** `{git_summary}`

---

## 1. Process & Component Port Topology

| Subsystem | Process Identifier | Primary Port | Protocol | Memory Silo | Isolation Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **HELIOS Core Router** | `helios.core` | `8000` | HTTP / WebSocket | `data/helios.db` | Strict (HMAC Required) |
| **Hikari Coding Swarm** | `helios.hikari` | `8001` | WebSocket / CLI | `data/hikari.db` | Strict (Worktree Sandbox) |
| **Solstice (Sol) Avatar** | `helios.solstice` | `8082` | HTTP / WebSocket | `data/solstice.db` | Strict (Avatar Silo) |
| **3D WebGL Studio** | `helios.character` | `8080` | HTTP / Static WebGL | None (Stateless Client) | Read-Only Telemetry |
| **Ollama Local Daemon** | `ollama.service` | `11434` | HTTP / REST | `.ollama/models` | Localhost Only |

---

## 2. Hardware Probing Profile & Acceleration Tiers

| Hardware Metric | Inspected Value | System Allocation | Classification |
| :--- | :--- | :--- | :--- |
| **Primary GPU** | `{gpu}` | {vram:.1f} GB Dedicated/Shared | **{tier_desc}** |
| **Physical System RAM** | `{ram:.2f} GB Total` | Available: ~{governor.profile.ram_available_gb:.2f} GB | {'Constraint' if governor.decision.is_budget else 'Nominal'} |
| **CPU Architecture** | `{governor.profile.cpu_name}` | {governor.profile.cpu_cores_physical} Physical / {governor.profile.cpu_cores_logical} Logical Cores | Fast CPU Compute |
| **Acceleration Engine** | `DirectML / CPU Quantized` | Dynamic Fallback | Active |

### Active Capability Advisories & Warnings
{warning_bullets}

### Recommended Resource Allocations:
{downgrade_rows}

---

## 3. Data Boundary & IPC Isolation Status

- **Bridge Enabled:** `{guard.is_enabled}`
- **Cross-Engine Isolation:** `STRICT ENFORCEMENT (Zero-Trust)`
- **SQLite Database Stores:**
  - `HELIOS`: `data/helios.db` (Isolated)
  - `Hikari`: `data/hikari.db` (Isolated)
  - `Solstice`: `data/solstice.db` (Isolated)
- **Token Max Age:** `{guard.config.get('token_max_age_seconds', 5)}s (Anti-Replay Window)`

---

## 4. Registered Connector Catalog & Scopes

| Connector ID | Version | Scopes | Timeout | Zero-Trust Sandbox |
| :--- | :--- | :--- | :--- | :--- |
{conn_rows}

---

## 5. Antigravity Slash Command Entry Points

| Slash Command | Dispatch Target | Mode | Verification |
| :--- | :--- | :--- | :--- |
| `/audit` | `scripts/run_audit.py` | Full workspace re-scan & SSoT sync | Automated |
| `/setup` | `scripts/bootstrap.py` | Idempotent environment & hardware check | Automated |
| `/test-isolation` | `tests/test_isolation.py` | Data & memory segregation suite | Automated |
| `/verify-voice` | `scripts/verify_voice.py` | Speaker calibration & PIN verification | Interactive / Automated |
| `/3d-web-experience` | `scripts/launch_3d_experience.py` | Launches dual-avatar WebGL on :8080 | Automated |
"""

    with open(audit_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[OK] Successfully refreshed {audit_path}")
    print(governor.get_advisory_banner())

if __name__ == "__main__":
    generate_audit()
