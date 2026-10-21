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

def run_addon_script(addon_dir_name: str, script_name: str, args: list):
    addon_dir = os.path.abspath(os.path.join(BASE_DIR, "..", addon_dir_name))
    script_path = os.path.join(addon_dir, script_name)
    if not os.path.exists(addon_dir):
        print(f"\n[!] Error: Addon '{addon_dir_name}' is not installed or missing.")
        print(f"    Expected path: {addon_dir}")
        print("    Please ensure the addon repository is cloned or installed.\n")
        sys.exit(1)
    if not os.path.exists(script_path):
        print(f"\n[!] Error: Addon script '{script_name}' not found inside '{addon_dir_name}'.")
        print(f"    Expected file: {script_path}\n")
        sys.exit(1)
    return subprocess.run(["cmd.exe", "/c", script_path] + args)

COMMANDS = {
    "/main": {
        "desc": "Launches the HELIOS Main Core AI Router (:8000)",
        "action": lambda args: subprocess.run([PY_EXE, "main.py"] + args, cwd=AI_ROUTER_DIR)
    },
    "/core": {
        "desc": "Alias for /main (HELIOS Main Core AI Router on :8000)",
        "action": lambda args: subprocess.run([PY_EXE, "main.py"] + args, cwd=AI_ROUTER_DIR)
    },
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
        "desc": "Launches HELIOS Main Core AI Router (:8000)",
        "action": lambda args: subprocess.run([PY_EXE, "main.py"] + args, cwd=AI_ROUTER_DIR)
    },
    "/user": {
        "desc": "Launches HELIOS 3D Avatar Companion Experience (:8080)",
        "action": lambda args: subprocess.run([PY_EXE, os.path.join(BASE_DIR, "scripts", "launch_3d_experience.py")] + args)
    },
    "/studio": {
        "desc": "Launches Sol Studio (Solstice Pose & 3D Prop Tuner Studio on :8080/?studio=true)",
        "action": lambda args: subprocess.run([PY_EXE, os.path.join(BASE_DIR, "scripts", "launch_3d_experience.py"), "--studio"] + args)
    },
    "/site": {
        "desc": "Launches the official HELIOS project website (React 19 + Vite on :5175)",
        "action": lambda args: run_addon_script("helios-site", "start_site.bat", args)
    },
    "/mobile": {
        "desc": "Launches HELIOS Mobile Companion Addon (Expo / React Native on :8081)",
        "action": lambda args: subprocess.run(["cmd.exe", "/c", os.path.join(BASE_DIR, "scripts", "launchers", "start_phone.bat")] + args)
    },
    "/hikari": {
        "desc": "Launches standalone Hikari Coding Swarm Addon Engine (:8001)",
        "action": lambda args: run_addon_script("hikari-addon", "start_hikari_addon.bat", args)
    },
    "/solstice": {
        "desc": "Launches standalone Solstice Avatar Engine Addon (:8082)",
        "action": lambda args: run_addon_script("solstice-addon", "start_solstice_addon.bat", args)
    },
    "/character-only": {
        "desc": "Launches standalone 3D Character Companion without router (:8080)",
        "action": lambda args: run_addon_script("solstice-addon", "start_character_only.bat", args)
    },
    "/astraea": {
        "desc": "Launches Astraea Autonomous Gaming Operative Addon (:8085)",
        "action": lambda args: run_addon_script("astraea-addon", "start_astraea.bat", args)
    },
    # Backward compatibility aliases
    "/hikari-addon": {
        "desc": "Alias for /hikari",
        "action": lambda args: run_addon_script("hikari-addon", "start_hikari_addon.bat", args),
        "hidden": True
    },
    "/solstice-addon": {
        "desc": "Alias for /solstice",
        "action": lambda args: run_addon_script("solstice-addon", "start_solstice_addon.bat", args),
        "hidden": True
    },
    "/astraea-addon": {
        "desc": "Alias for /astraea",
        "action": lambda args: run_addon_script("astraea-addon", "start_astraea.bat", args),
        "hidden": True
    }
}

def print_help(governor: HardwareGovernor):
    print("=" * 78)
    print("  HELIOS & TWIN ECOSYSTEM — ANTIGRAVITY COMMAND DISPATCHER")
    print(f"  Active Tier: {governor.decision.tier_name}")
    print("=" * 78)
    print("Available Operational Slash Commands:\n")
    for cmd, info in COMMANDS.items():
        if info.get("hidden"):
            continue
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
