"""HELIOS Zero-Friction Bootstrap & Adaptive Ingestion Engine.
Probes hardware, auto-installs Ollama if missing, pulls tier-matched models, and safeguards existing configs.
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import shutil
import subprocess
import time
import json
import urllib.request

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AI_ROUTER_DIR = os.path.join(BASE_DIR, "ai-router")
if AI_ROUTER_DIR not in sys.path:
    sys.path.insert(0, AI_ROUTER_DIR)

from core.hardware_governor import HardwareGovernor

def check_command_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def is_ollama_service_online() -> bool:
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags", headers={"User-Agent": "HELIOS-Bootstrap"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False

def ensure_ollama_installed():
    """Auto-installs Ollama via winget or direct download if not present."""
    print("[*] Probing Ollama runtime...")
    if check_command_exists("ollama") or is_ollama_service_online():
        print("[OK] Ollama is installed and detected in environment.")
        return True

    print("[!] Ollama not detected in PATH. Commencing automated installation...")
    # Attempt winget installation first
    if check_command_exists("winget"):
        try:
            print("[*] Installing Ollama via Windows Package Manager (winget)...")
            res = subprocess.run(["winget", "install", "--id", "Ollama.Ollama", "-e", "--accept-package-agreements", "--accept-source-agreements", "--silent"], timeout=180)
            if res.returncode == 0:
                print("[OK] Ollama successfully installed via winget.")
                return True
        except Exception as e:
            print(f"[!] winget installation encountered issue: {e}")

    # Fallback to direct official installer download
    print("[*] Downloading official Ollama installer for Windows...")
    installer_url = "https://ollama.com/download/OllamaSetup.exe"
    local_installer = os.path.join(BASE_DIR, "temp_OllamaSetup.exe")
    try:
        urllib.request.urlretrieve(installer_url, local_installer)
        print("[*] Launching silent Ollama installation...")
        subprocess.run([local_installer, "/silent"], check=True, timeout=120)
        print("[OK] Ollama installer executed successfully.")
        if os.path.exists(local_installer):
            os.remove(local_installer)
        return True
    except Exception as e:
        print(f"[!] Failed to auto-install Ollama: {e}")
        print("[!] Please install Ollama manually from https://ollama.com")
        return False

def ensure_ollama_running():
    """Ensures Ollama daemon is running."""
    if is_ollama_service_online():
        return True
    
    print("[*] Starting Ollama daemon in background...")
    try:
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(10):
            time.sleep(1)
            if is_ollama_service_online():
                print("[OK] Ollama service connected at http://localhost:11434")
                return True
    except Exception as e:
        print(f"[!] Failed to spawn Ollama daemon: {e}")
    return False

def get_installed_ollama_models() -> set:
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags", headers={"User-Agent": "HELIOS-Bootstrap"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {m.get("name") for m in data.get("models", [])}
    except Exception:
        return set()

def pull_tier_models(governor: HardwareGovernor, dry_run: bool = False):
    """Pulls recommended models suited for the detected hardware tier, skipping existing ones."""
    if not is_ollama_service_online():
        print("[!] Ollama service unreachable; skipping automated model pulls.")
        return

    installed = get_installed_ollama_models()
    rec_models = governor.decision.recommended_models
    print(f"[*] Checking models for {governor.decision.tier_name}:")

    for role, model_tag in rec_models.items():
        # Check if already present (with or without :latest)
        base_tag = model_tag.split(":")[0]
        is_installed = any(m.startswith(base_tag) for m in installed)
        if is_installed:
            print(f"  [OK] Model '{model_tag}' ({role}) is already downloaded.")
        else:
            if dry_run:
                print(f"  [>] Would pull hardware-matched model: {model_tag} ({role})")
            else:
                print(f"  [*] Pulling optimal model: {model_tag} ({role})...")
                try:
                    subprocess.run(["ollama", "pull", model_tag], timeout=600)
                    print(f"  [OK] {model_tag} pulled successfully.")
                except Exception as e:
                    print(f"  [!] Pull error for {model_tag}: {e}")

def update_env_file(env_path: str, updates: dict):
    """Safely updates or appends key-value pairs in an .env file without destroying other entries or comments."""
    if not os.path.exists(env_path):
        with open(env_path, "w", encoding="utf-8") as f:
            for k, v in updates.items():
                f.write(f"{k}={v}\n")
        return

    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    keys_found = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _ = stripped.split("=", 1)
            k = k.strip()
            if k in updates:
                new_lines.append(f"{k}={updates[k]}\n")
                keys_found.add(k)
                continue
        new_lines.append(line)

    for k, v in updates.items():
        if k not in keys_found:
            new_lines.append(f"{k}={v}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

def ensure_safe_env():
    """Creates default .env from .env.example if missing, preserving any existing .env."""
    env_file = os.path.join(BASE_DIR, ".env")
    example_file = os.path.join(BASE_DIR, ".env.example")
    if not os.path.exists(env_file) and os.path.exists(example_file):
        print("[*] Creating initial .env from template...")
        shutil.copyfile(example_file, env_file)
        print("[OK] Initialized .env.")
    else:
        print("[OK] Existing .env detected — preserving user configurations (Idempotent).")

def run_customization_wizard(interactive: bool = True):
    """Interactive / automated CLI customization wizard for HELIOS & Twin Ecosystem."""
    print("=" * 78)
    print("  HELIOS & TWIN ECOSYSTEM — INTERACTIVE CUSTOMIZATION WIZARD")
    print("=" * 78)

    governor = HardwareGovernor()
    detected_tier = governor.decision.tier_name
    print(f"Detected Hardware Profile: {detected_tier}")
    print("-" * 78)

    # 1. Default Launch Edition
    print("\n[1/5] Select Default Ecosystem Launch Edition:")
    print("  [1] Developer Edition  (AI-Router :8000, Web UI, Hikari Swarm :8001)")
    print("  [2] Solstice User Ed.  (Solstice 3D Companion :8082, WebGL :8080)")
    print("  [3] Co-existence Mode  (Launch Core Router, Coding Swarm, and Solstice)")
    ed_choice = "1"
    if interactive and sys.stdin.isatty():
        try:
            val = input("  Select edition [1-3, default=1]: ").strip()
            if val in ("1", "2", "3"):
                ed_choice = val
        except (EOFError, KeyboardInterrupt):
            pass

    edition_map = {"1": "dev", "2": "solstice", "3": "all"}
    chosen_edition = edition_map.get(ed_choice, "dev")
    print(f"  -> Selected Edition: {chosen_edition.upper()}")

    # 2. Model Tier Profile
    print("\n[2/5] Select Compute & Model Tier Profile:")
    print("  [1] Tier 3: Budget / iGPU     (Qwen 2.5 1.5B, Coder 1.5B, Moondream 1B)")
    print("  [2] Tier 2: Balanced / <=8GB  (Llama 3.2 3B, Coder 3B, Qwen2.5-VL 3B)")
    print("  [3] Tier 1: Heavy / >=12GB    (Qwen 2.5 7B, Coder 7B, LLaVA 7B)")
    print("  [4] Auto-Detect Hardware      (Keep hardware governor recommendation)")

    tier_choice = "4"
    if interactive and sys.stdin.isatty():
        try:
            val = input("  Select tier [1-4, default=4]: ").strip()
            if val in ("1", "2", "3", "4"):
                tier_choice = val
        except (EOFError, KeyboardInterrupt):
            pass

    model_configs = {
        "1": {
            "tier": "Tier 3: Budget",
            "models": {
                "general": "qwen2.5:1.5b",
                "coder": "qwen2.5-coder:1.5b",
                "vision": "moondream:latest",
                "embed": "nomic-embed-text:latest"
            }
        },
        "2": {
            "tier": "Tier 2: Balanced",
            "models": {
                "general": "llama3.2:3b",
                "coder": "qwen2.5-coder:3b",
                "vision": "qwen2.5vl:3b",
                "embed": "nomic-embed-text:latest"
            }
        },
        "3": {
            "tier": "Tier 1: Heavy",
            "models": {
                "general": "qwen2.5:7b",
                "coder": "qwen2.5-coder:7b",
                "vision": "llava:7b",
                "embed": "nomic-embed-text:latest"
            }
        },
        "4": {
            "tier": governor.decision.tier_name,
            "models": governor.decision.recommended_models
        }
    }
    selected_tier_info = model_configs.get(tier_choice, model_configs["4"])
    print(f"  -> Applied Profile: {selected_tier_info['tier']}")

    # 3. Solstice Companion Character Persona
    print("\n[3/5] Select Solstice 3D Companion Avatar Persona:")
    print("  [1] Ren  (HELIOS Male Twin — Tactical Engineer / Deep Coder)")
    print("  [2] Airi (HELIOS Female Twin — Expressive Companion / Visual Host)")
    print("  [3] Dual (Switchable between Ren & Airi)")
    char_choice = "1"
    if interactive and sys.stdin.isatty():
        try:
            val = input("  Select persona [1-3, default=1]: ").strip()
            if val in ("1", "2", "3"):
                char_choice = val
        except (EOFError, KeyboardInterrupt):
            pass
    char_map = {"1": "ren", "2": "airi", "3": "dual"}
    chosen_persona = char_map.get(char_choice, "ren")
    print(f"  -> Selected Persona: {chosen_persona.upper()}")

    # 4. Zero-Trust IPC Bridge Security
    print("\n[4/5] Zero-Trust IPC HMAC-SHA256 Token Bridge:")
    print("  [1] Enforce Strict Token Isolation (Recommended for Multi-Engine Sovereignty)")
    print("  [2] Permissive Local Development Mode")
    bridge_choice = "1"
    if interactive and sys.stdin.isatty():
        try:
            val = input("  Bridge mode [1-2, default=1]: ").strip()
            if val in ("1", "2"):
                bridge_choice = val
        except (EOFError, KeyboardInterrupt):
            pass
    bridge_enabled = "true" if bridge_choice == "1" else "false"
    print(f"  -> Bridge Strict Security: {bridge_enabled.upper()}")

    # 5. Service Ports Configuration
    print("\n[5/5] Port Configuration (HELIOS Core: 8000 | Hikari: 8001 | Solstice: 8082 | WebGL: 8080):")
    core_port = "8000"
    hikari_port = "8001"
    sol_port = "8082"
    webgl_port = "8080"
    if interactive and sys.stdin.isatty():
        try:
            custom_p = input("  Customize port bindings? [y/N]: ").strip().lower()
            if custom_p == "y":
                cp = input(f"    HELIOS Core Port [{core_port}]: ").strip()
                if cp: core_port = cp
                hp = input(f"    Hikari Swarm Port [{hikari_port}]: ").strip()
                if hp: hikari_port = hp
                sp = input(f"    Solstice Engine Port [{sol_port}]: ").strip()
                if sp: sol_port = sp
                wp = input(f"    Solstice WebGL Port [{webgl_port}]: ").strip()
                if wp: webgl_port = wp
        except (EOFError, KeyboardInterrupt):
            pass
    print(f"  -> Ports Configured: Core={core_port}, Hikari={hikari_port}, Solstice={sol_port}, WebGL={webgl_port}")

    # Build updates for .env
    env_updates = {
        "DEFAULT_EDITION": chosen_edition,
        "TIER_OVERRIDE": selected_tier_info["tier"],
        "SERVER_PORT": core_port,
        "HIKARI_PORT": hikari_port,
        "SOLSTICE_PORT": sol_port,
        "CHARACTER_PORT": webgl_port,
        "SOLSTICE_PERSONA": chosen_persona,
        "BRIDGE_ENABLED": bridge_enabled,
        "PRIMARY_MODEL": selected_tier_info["models"].get("general", "qwen2.5:1.5b"),
        "CODER_MODEL": selected_tier_info["models"].get("coder", "qwen2.5-coder:1.5b"),
        "VISION_MODEL": selected_tier_info["models"].get("vision", "moondream:latest"),
        "EMBED_MODEL": selected_tier_info["models"].get("embed", "nomic-embed-text:latest"),
    }

    # Save to root .env and ai-router/.env
    root_env = os.path.join(BASE_DIR, ".env")
    ai_env = os.path.join(BASE_DIR, "ai-router", ".env")
    update_env_file(root_env, env_updates)
    update_env_file(ai_env, env_updates)
    print("\n[OK] Synchronized configurations to .env and ai-router/.env")

    # Save structured custom_profile.json
    profile_data = {
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "edition": chosen_edition,
        "tier": selected_tier_info["tier"],
        "persona": chosen_persona,
        "bridge_strict": bridge_enabled == "true",
        "ports": {
            "core": int(core_port),
            "hikari": int(hikari_port),
            "solstice": int(sol_port),
            "webgl": int(webgl_port)
        },
        "models": selected_tier_info["models"]
    }
    config_dir = os.path.join(BASE_DIR, "config")
    os.makedirs(config_dir, exist_ok=True)
    profile_path = os.path.join(config_dir, "custom_profile.json")
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile_data, f, indent=2)
    print(f"[OK] Saved custom profile to {profile_path}")

    # Prompt for Voice Biometrics Calibration if desired
    print("\n[*] Local Voice Biometrics Enrollment:")
    enroll_voice = False
    if interactive and sys.stdin.isatty():
        try:
            v_ans = input("  Run local voice biometrics enrollment/calibration now? [y/N]: ").strip().lower()
            enroll_voice = (v_ans == "y")
        except (EOFError, KeyboardInterrupt):
            pass

    if enroll_voice:
        voice_script = os.path.join(BASE_DIR, "scripts", "verify_voice.py")
        if os.path.exists(voice_script):
            print("[*] Launching Voice Biometrics Verification & Calibration Runner...")
            subprocess.run([sys.executable, voice_script])

    # Ingest models if needed
    if is_ollama_service_online():
        installed = get_installed_ollama_models()
        missing = [m for m in selected_tier_info["models"].values() if not any(m.startswith(im.split(":")[0]) for im in installed)]
        if missing:
            print(f"\n[*] The following recommended models for {selected_tier_info['tier']} are not yet installed:")
            for m in missing:
                print(f"    - {m}")
            pull_now = True
            if interactive and sys.stdin.isatty():
                try:
                    p_ans = input("  Pull these models from Ollama now? [Y/n]: ").strip().lower()
                    pull_now = (p_ans != "n")
                except (EOFError, KeyboardInterrupt):
                    pass
            if pull_now:
                for m in missing:
                    print(f"  [*] Pulling {m}...")
                    try:
                        subprocess.run(["ollama", "pull", m], timeout=600)
                        print(f"  [OK] {m} pulled successfully.")
                    except Exception as e:
                        print(f"  [!] Failed to pull {m}: {e}")

    # Synchronize Living Audit
    audit_script = os.path.join(BASE_DIR, "scripts", "run_audit.py")
    if os.path.exists(audit_script):
        subprocess.run([sys.executable, audit_script])

    print("\n" + "=" * 78)
    print("  [SUCCESS] HELIOS CUSTOMIZATION COMPLETE!")
    print("=" * 78)

def run_bootstrap(dry_run: bool = False):
    print("=" * 78)
    print("  HELIOS Autonomous Systems Bootstrap & Hardware Diagnostic")
    print("=" * 78)

    governor = HardwareGovernor()
    print(governor.get_advisory_banner())
    print()

    # Safe config provisioning
    ensure_safe_env()

    # Ollama Provisioning
    if not dry_run:
        ensure_ollama_installed()
        ensure_ollama_running()

    # Model ingestion
    pull_tier_models(governor, dry_run=dry_run)

    # Sync Living Audit
    audit_script = os.path.join(BASE_DIR, "scripts", "run_audit.py")
    if os.path.exists(audit_script):
        subprocess.run([sys.executable, audit_script])

    print("\n[OK] Bootstrap health check completed successfully.")

if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    is_custom = "--custom" in sys.argv or "-c" in sys.argv

    if is_custom:
        run_customization_wizard(interactive=not is_dry)
    else:
        run_bootstrap(dry_run=is_dry)
