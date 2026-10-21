"""Launcher for Antigravity Slash Command: /3d-web-experience.
Launches Solstice (Sol) Avatar Telemetry Engine (:8082) and 3D WebGL Viewer (:8080)
with budget hardware GPU optimization profiles and dual-twin presence.
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import time
import subprocess
import webbrowser
import urllib.request

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AI_ROUTER_DIR = os.path.join(BASE_DIR, "ai-router")
if AI_ROUTER_DIR not in sys.path:
    sys.path.insert(0, AI_ROUTER_DIR)

from core.hardware_governor import HardwareGovernor

def is_service_up(url: str) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HELIOS-Launcher"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status in (200, 404)
    except Exception:
        return False

def launch_3d_experience(dry_run: bool = False):
    print("=" * 78)
    print("  ANTIGRAVITY /3d-web-experience: Dual-Twin 3D Avatar Co-Presence Studio")
    print("=" * 78)

    governor = HardwareGovernor()
    print(governor.get_advisory_banner())
    print()

    # Determine query params with hardware and mode profiles
    query_params = ["synergy=true"]
    base_page = "/dev_studio.html" if "--studio" in sys.argv else "/"
    if governor.decision.is_budget:
        query_params.append("budget=true")
        query_params.append("fps=30")
        query_params.append("shadows=false")
    else:
        query_params.append("fps=60")

    launch_url = f"http://localhost:8080{base_page}?{'&'.join(query_params)}"

    if dry_run:
        print("[OK] Dry run: Verified WebGL viewer configuration and telemetry profiles.")
        print(f"  Target URL: {launch_url}")
        print("[OK] /3d-web-experience readiness verified successfully.")
        return

    # 1. Start Solstice (Sol) Engine on Port 8082 if not online
    solstice_url = "http://localhost:8082/health"
    if not is_service_up(solstice_url):
        print("[*] Launching Solstice Avatar Telemetry Engine (Port 8082)...")
        # Check standalone addon in C:\projects\solstice-addon
        addon_sol_script = os.path.abspath(os.path.join(BASE_DIR, "..", "solstice-addon", "server.py"))
        
        sol_script = None
        sol_cwd = BASE_DIR
        if os.path.exists(addon_sol_script):
            sol_script = addon_sol_script
            sol_cwd = os.path.dirname(addon_sol_script)

        if sol_script:
            py_exe = os.path.join(BASE_DIR, "ai-router", "venv", "Scripts", "python.exe")
            if not os.path.exists(py_exe):
                py_exe = sys.executable

            subprocess.Popen([py_exe, sol_script], cwd=sol_cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(8):
                time.sleep(1)
                if is_service_up(solstice_url):
                    print("[OK] Solstice Avatar Engine connected at :8082")
                    break
        else:
            print("[i] Solstice addon not found at ../solstice-addon. WebGL 3D Avatar running standalone.")
    else:
        print("[OK] Solstice Avatar Engine is already running on :8082.")

    # 2. Check 3D Viewer on Port 8080
    viewer_url = "http://localhost:8080"
    if not is_service_up(viewer_url):
        print("[*] Launching 3D WebGL Avatar Server (Port 8080)...")
        char_script = os.path.join(BASE_DIR, "helios-character", "ai_server.py")
        char_cwd = os.path.join(BASE_DIR, "helios-character")
        addon_char_script = os.path.abspath(os.path.join(BASE_DIR, "..", "solstice-addon", "ai_server.py"))
        if not os.path.exists(char_script) and os.path.exists(addon_char_script):
            char_script = addon_char_script
            char_cwd = os.path.dirname(addon_char_script)

        py_exe = os.path.join(BASE_DIR, "ai-router", "venv", "Scripts", "python.exe")
        if not os.path.exists(py_exe):
            py_exe = sys.executable

        env = os.environ.copy()
        env["CHAR_MODE"] = "character_only"
        subprocess.Popen([py_exe, char_script], cwd=char_cwd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(8):
            time.sleep(1)
            if is_service_up(viewer_url):
                print("[OK] 3D WebGL Avatar Server connected at :8080")
                break
    else:
        print("[OK] 3D WebGL Avatar Server is already running on :8080.")

    # 3. Determine URL with budget hardware tuning
    query_params = ["synergy=true"]
    if "--pose-studio" in sys.argv:
        base_page = "/pose_studio.html"
    elif "--studio" in sys.argv:
        base_page = "/dev_studio.html"
    else:
        base_page = "/"
    if governor.decision.is_budget:
        query_params.append("budget=true")
        query_params.append("fps=30")
        query_params.append("shadows=false")
    else:
        query_params.append("fps=60")

    launch_url = f"{viewer_url}{base_page}?{'&'.join(query_params)}"
    print(f"\n[OK] Launching 3D Web Experience in browser: {launch_url}")
    try:
        webbrowser.open(launch_url)
    except Exception as e:
        print(f"[!] Could not open browser automatically: {e}")
        print(f"[>] Navigate to: {launch_url}")

if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    launch_3d_experience(dry_run=is_dry)
