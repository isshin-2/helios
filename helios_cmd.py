"""HELIOS Unified Slash Command Dispatcher CLI.
Exposes Antigravity operational workflows: /audit, /setup, /test-isolation, /verify-voice, /3d-web-experience.
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import subprocess

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
AI_ROUTER_DIR = os.path.join(BASE_DIR, "ai-router")
if AI_ROUTER_DIR not in sys.path:
    sys.path.insert(0, AI_ROUTER_DIR)

from core.hardware_governor import HardwareGovernor

PY_EXE = os.path.join(AI_ROUTER_DIR, "venv", "Scripts", "python.exe")
if not os.path.exists(PY_EXE):
    PY_EXE = sys.executable

COMMANDS = {
    "/audit": {
        "desc": "Re-scans modified files, validates IPC boundaries, and refreshes docs/SYSTEM_AUDIT.md",
        "action": lambda args: subprocess.run([PY_EXE, os.path.join(BASE_DIR, "scripts", "run_audit.py")] + args)
    },
    "/setup": {
        "desc": "Executes hardware diagnostic, Ollama provisioning, and adaptive model health check",
        "action": lambda args: subprocess.run([PY_EXE, os.path.join(BASE_DIR, "scripts", "bootstrap.py")] + args)
    },
    "/custom": {
        "desc": "Launches the interactive ecosystem customization wizard (profiles, models, ports, biometrics)",
        "action": lambda args: subprocess.run([PY_EXE, os.path.join(BASE_DIR, "scripts", "bootstrap.py"), "--custom"] + args)
    },
    "/test-isolation": {
        "desc": "Runs automated pytest suite verifying hard memory and IPC isolation across HELIOS, Hikari, and Solstice",
        "action": lambda args: subprocess.run([PY_EXE, "-m", "pytest", os.path.join(BASE_DIR, "tests", "test_isolation.py"), "-v"] + args)
    },
    "/verify-voice": {
        "desc": "Launches speaker calibration centroid enrollment and fallback PIN security verification loop",
        "action": lambda args: subprocess.run([PY_EXE, os.path.join(BASE_DIR, "scripts", "verify_voice.py")] + args)
    },
    "/3d-web-experience": {
        "desc": "Spins up WebGL/Three.js dual-twin scene with real-time WebSocket telemetry for Airi & Ren",
        "action": lambda args: subprocess.run([PY_EXE, os.path.join(BASE_DIR, "scripts", "launch_3d_experience.py")] + args)
    },
    "/dev": {
        "desc": "Launches HELIOS Developer Edition (Core Router :8000 + Hikari Swarm :8001)",
        "action": lambda args: subprocess.run(["cmd.exe", "/c", os.path.join(BASE_DIR, "start_helios_dev.bat")] + args)
    },
    "/user": {
        "desc": "Launches HELIOS User Edition (Solstice Companion Engine :8082 + 3D Avatar :8080)",
        "action": lambda args: subprocess.run(["cmd.exe", "/c", os.path.join(BASE_DIR, "start_solstice.bat")] + args)
    },
    "/ralph": {
        "desc": "Runs autonomous Ralph Loop: tests each task, makes atomic git commits, and logs rollback points",
        "action": lambda args: subprocess.run([PY_EXE, os.path.join(BASE_DIR, "scripts", "ralph_runner.py")] + args)
    }
}

def print_help(governor: HardwareGovernor):
    print("=" * 78)
    print("  HELIOS & TWIN ECOSYSTEM — ANTIGRAVITY COMMAND DISPATCHER")
    print(f"  Active Tier: {governor.decision.tier_name}")
    print("=" * 78)
    print("Available Operational Slash Commands:\n")
    for cmd, info in COMMANDS.items():
        print(f"  {cmd:<22} : {info['desc']}")
    print("\nUsage:")
    print("  python helios_cmd.py /audit")
    print("  helios /test-isolation")
    print("  helios /3d-web-experience")
    print("=" * 78)

def main():
    governor = HardwareGovernor()
    raw_args = sys.argv[1:]

    if not raw_args or raw_args[0].lower() in ("-h", "--help", "help", "/help", "-help"):
        print_help(governor)
        return

    cmd = raw_args[0].lower()
    # Normalize command if passed without leading slash
    if not cmd.startswith("/"):
        cmd = f"/{cmd}"

    if cmd in COMMANDS:
        extra_args = raw_args[1:]
        res = COMMANDS[cmd]["action"](extra_args)
        sys.exit(res.returncode if hasattr(res, "returncode") else 0)
    else:
        print(f"[!] Unknown slash command: '{cmd}'")
        print_help(governor)
        sys.exit(1)

if __name__ == "__main__":
    main()
