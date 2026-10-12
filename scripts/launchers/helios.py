#!/usr/bin/env python3
"""
HELIOS — Universal Cross-Platform Orchestrator & CLI Entrypoint
Works natively on Windows, macOS, and Linux without shell dependencies.
Usage:
    python helios.py                 # Interactive master launcher menu
    python helios.py core            # Launch HELIOS Core AI Router (:8000)
    python helios.py hikari [prompt] # Launch Hikari Autonomous Coding Swarm
    python helios.py full            # Launch Full Spec (Core :8000 + Airi :8080)
    python helios.py airi            # Launch Airi 3D VRM Companion (:8080)
    python helios.py client          # Launch HELIOS Remote Client Suite
    python helios.py setup           # Verify / install dependencies & configure
    python helios.py status          # System diagnostics & hardware profile
    python helios.py test            # Run verified test suite
"""

import os
import sys
import subprocess
import signal
import platform
import argparse
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
ROUTER_DIR = ROOT_DIR / "ai-router"
CHAR_DIR = ROOT_DIR / "helios-character"
CLIENT_DIR = ROOT_DIR / "helios-client"

def get_venv_python() -> str:
    """Resolve the Python executable inside ai-router/venv if available."""
    if sys.platform == "win32":
        vpy = ROUTER_DIR / "venv" / "Scripts" / "python.exe"
    else:
        vpy = ROUTER_DIR / "venv" / "bin" / "python"
    
    if vpy.exists():
        return str(vpy)
    return sys.executable

def print_banner():
    cyan = "\033[1;36m"
    blue = "\033[1;34m"
    reset = "\033[0m"
    bold = "\033[1m"
    print(rf"""{cyan}{bold}
   __  __  ______  _       _____   ____    _____ 
  |  |/  ||  ____|| |     |_   _| / __ \  / ____|
  |      || |__   | |       | |  | |  | || (___  
  |  __  ||  __|  | |       | |  | |  | | \___ \ 
  | |  | || |____ | |____  _| |_ | |__| | ____) |
  |_|  |_||______||______||_____| \____/ |_____/ 
{reset}{blue}   Autonomous AI Router · 8-Agent Swarm · 3D VRM Companion{reset}
""")

def run_setup(args=None):
    """Run environment setup."""
    print("[*] Running HELIOS Environment Setup...")
    py = sys.executable
    os.chdir(str(ROUTER_DIR))
    cmd = [py, "setup.py"]
    if args and getattr(args, "quick", False):
        cmd.append("--quick")
    return subprocess.run(cmd).returncode

def run_core(port="8000"):
    """Run Core AI Router Server."""
    py = get_venv_python()
    os.chdir(str(ROUTER_DIR))
    print(f"[*] Starting HELIOS Core Server on 0.0.0.0:{port}...")
    cmd = [py, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", str(port)]
    return subprocess.run(cmd).returncode

def run_hikari(extra_args=None):
    """Run Hikari Autonomous Coding Swarm CLI."""
    py = get_venv_python()
    os.chdir(str(ROUTER_DIR))
    cmd = [py, "helios_code.py"] + (extra_args or [])
    return subprocess.run(cmd).returncode

def run_airi():
    """Run Airi 3D Companion (:8080)."""
    py = get_venv_python()
    os.chdir(str(CHAR_DIR))
    os.environ["HELIOS_EDITION"] = "full_spec"
    os.environ["HELIOS_CHARACTER_MODE"] = "full_spec"
    print("[*] Starting Airi 3D Companion on port 8080...")
    return subprocess.run([py, "ai_server.py"]).returncode

def run_full():
    """Run Full Spec: Core (:8000) + Airi (:8080)."""
    py = get_venv_python()
    print("[*] Launching HELIOS Full Spec Ecosystem...")
    
    # 1. Start Airi character server in background
    char_env = os.environ.copy()
    char_env["HELIOS_EDITION"] = "full_spec"
    char_env["HELIOS_CHARACTER_MODE"] = "full_spec"
    char_proc = subprocess.Popen(
        [py, "ai_server.py"],
        cwd=str(CHAR_DIR),
        env=char_env
    )

    def cleanup(sig=None, frame=None):
        print("\n[*] Shutting down ecosystem services...")
        if char_proc.poll() is None:
            char_proc.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        # 2. Run Core server in foreground
        os.chdir(str(ROUTER_DIR))
        subprocess.run([py, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"])
    finally:
        cleanup()

def run_client(extra_args=None):
    """Run HELIOS Client suite."""
    py = get_venv_python()
    os.chdir(str(ROOT_DIR))
    cmd = [py, "helios-client/main.py"] + (extra_args or ["--gui"])
    return subprocess.run(cmd).returncode

def run_status():
    """Display comprehensive system hardware and network status."""
    print_banner()
    sys.path.insert(0, str(ROUTER_DIR))
    try:
        from core.hardware_profiler import get_cluster_hardware_summary
        summary = get_cluster_hardware_summary()
        local = summary.get("nodes", {}).get("local_controller", {})
        ai_pc = summary.get("nodes", {}).get("ai_pc_gpu_node", {})

        print(f"  OS / Platform      : {local.get('os_name')} {local.get('os_version')} ({platform.machine()})")
        print(f"  CPU                : {local.get('cpu_name')} ({local.get('cpu_cores_logical')} cores)")
        print(f"  RAM Total          : {local.get('ram_total_gb', 0):.1f} GB ({local.get('ram_available_gb', 0):.1f} GB free)")
        print(f"  GPU Hardware       : {local.get('gpu_name')} ({local.get('gpu_vendor').upper()}, {local.get('gpu_vram_gb', 0):.1f} GB VRAM)")
        print(f"  Hardware Tier      : {local.get('tier')}")
        print(f"  AI PC Remote Node  : {'ONLINE (Reachable)' if ai_pc.get('reachable') else 'STANDBY / Offline'}")
        print(f"  Cluster Capacity   : {summary.get('aggregate_capacity', {}).get('total_ram_gb', 0):.1f} GB RAM | {summary.get('aggregate_capacity', {}).get('total_vram_gb', 0):.1f} GB VRAM\n")
    except Exception as e:
        print(f"[!] Could not read hardware profiler: {e}")

def run_test(extra_args=None):
    """Run verified test suite."""
    py = get_venv_python()
    os.chdir(str(ROUTER_DIR))
    cmd = [py, "-m", "pytest", "tests/test_helios_core_suite.py"] + (extra_args or [])
    return subprocess.run(cmd).returncode

def interactive_menu():
    print_banner()
    print("  [1] HELIOS Core Server   (AI Router :8000, Swarm, RAG, Hardware Arbitrator)")
    print("  [2] Hikari Coding CLI    (Interactive Claude Code / Codex Terminal Swarm)")
    print("  [3] HELIOS Full Spec     (Core Server :8000 + Airi 3D Companion :8080)")
    print("  [4] Airi Companion Only  (Standalone 3D VRM Avatar without :8000)")
    print("  [5] HELIOS Client Mode   (Desktop GUI / CLI connected to Server / AI PC)")
    print("  [6] System Diagnostics   (Hardware profile, cluster capacity, node ping)")
    print("  [7] Environment Setup    (Verify & install dependencies, configure .env)")
    print("  [8] Run Test Suite       (Execute core verification tests)")
    print("============================================================================")
    try:
        choice = input("Select launch mode [1-8, default=1]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nExiting.")
        return 0

    if choice == "2":
        return run_hikari()
    elif choice == "3":
        return run_full()
    elif choice == "4":
        return run_airi()
    elif choice == "5":
        return run_client()
    elif choice == "6":
        return run_status()
    elif choice == "7":
        return run_setup()
    elif choice == "8":
        return run_test()
    else:
        return run_core()

def main():
    if len(sys.argv) == 1:
        return interactive_menu()

    cmd = sys.argv[1].lower().lstrip("-")
    extra = sys.argv[2:]

    if cmd in ("core", "server"):
        return run_core()
    elif cmd in ("hikari", "code", "cli"):
        return run_hikari(extra)
    elif cmd in ("full", "full_spec", "all"):
        return run_full()
    elif cmd in ("airi", "character", "avatar"):
        return run_airi()
    elif cmd in ("client", "desktop"):
        return run_client(extra)
    elif cmd in ("setup", "install"):
        parser = argparse.ArgumentParser()
        parser.add_argument("--quick", "-y", action="store_true")
        args, _ = parser.parse_known_args(extra)
        return run_setup(args)
    elif cmd in ("status", "info", "diagnostics"):
        return run_status()
    elif cmd in ("test", "tests", "pytest"):
        return run_test(extra)
    elif cmd in ("help", "h"):
        print(__doc__)
        return 0
    else:
        print(f"Unknown command: {sys.argv[1]}")
        print(__doc__)
        return 1

if __name__ == "__main__":
    sys.exit(main() or 0)
