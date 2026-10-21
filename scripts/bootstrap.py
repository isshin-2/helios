"""HELIOS Zero-Friction Bootstrap & Adaptive Ingestion Engine.
Probes hardware, auto-installs Ollama if missing, pulls tier-matched models, and safeguards existing configs.
Features an interactive CLI customization wizard with 1-key default acceptance for:
1. User Preferences (Call-sign, Persona tone, Wake-word, Hot-mic, Workspace root)
2. Voice Settings (GPT-SoVITS, Kokoro presets, Reference audio, Prosody, Audible test)
3. LLM Integration (Ollama, Remote AI PC / NVIDIA PAIR, Cloud APIs, Tier auto-detection)
4. Ecosystem & Infrastructure (Ports, Biometrics, Swarm concurrency, Security Bridge)
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
import socket

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AI_ROUTER_DIR = os.path.join(BASE_DIR, "ai-router")
if AI_ROUTER_DIR not in sys.path:
    sys.path.insert(0, AI_ROUTER_DIR)

from core.hardware_governor import HardwareGovernor


def check_command_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def is_ollama_service_online(host: str = "http://localhost:11434") -> bool:
    try:
        req = urllib.request.Request(f"{host.rstrip('/')}/api/tags", headers={"User-Agent": "HELIOS-Bootstrap"})
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
    if check_command_exists("winget"):
        try:
            print("[*] Installing Ollama via Windows Package Manager (winget)...")
            res = subprocess.run(["winget", "install", "--id", "Ollama.Ollama", "-e", "--accept-package-agreements", "--accept-source-agreements", "--silent"], timeout=180)
            if res.returncode == 0:
                print("[OK] Ollama successfully installed via winget.")
                return True
        except Exception as e:
            print(f"[!] winget installation encountered issue: {e}")

    print("[*] Downloading official Ollama installer for Windows...")
    installer_url = "https://ollama.com/download/OllamaSetup.exe"
    local_installer = os.path.join(BASE_DIR, "temp_OllamaSetup.exe")
    try:
        urllib.request.urlretrieve(installer_url, local_installer)
        print("[*] Running Ollama installer silently...")
        subprocess.run([local_installer, "/silent"], check=True)
        print("[OK] Ollama successfully installed.")
        if os.path.exists(local_installer):
            os.remove(local_installer)
        return True
    except Exception as e:
        print(f"[!] Manual installation required. Download at https://ollama.com ({e})")
        return False


def ensure_ollama_running():
    """Ensures Ollama background server daemon is active."""
    if is_ollama_service_online():
        print("[OK] Ollama service is active and responsive.")
        return True

    print("[*] Starting Ollama daemon in background...")
    try:
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        for _ in range(10):
            time.sleep(1)
            if is_ollama_service_online():
                print("[OK] Ollama daemon initialized.")
                return True
    except Exception as e:
        print(f"[!] Failed to start Ollama daemon: {e}")
    return False


def get_installed_ollama_models(host: str = "http://localhost:11434") -> list:
    try:
        req = urllib.request.Request(f"{host.rstrip('/')}/api/tags", headers={"User-Agent": "HELIOS-Bootstrap"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def pull_tier_models(governor: HardwareGovernor, dry_run: bool = False):
    """Pulls recommended models suited for the detected hardware tier, skipping existing ones."""
    if not is_ollama_service_online():
        print("[!] Ollama service unreachable; skipping automated model pulls.")
        return

    installed = get_installed_ollama_models()
    rec_models = governor.decision.recommended_models
    print(f"[*] Checking models for {governor.decision.tier_name}:")

    for role, model_tag in rec_models.items():
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


def read_env_file(env_path: str) -> dict:
    env = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    k, v = stripped.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


def update_env_file(env_path: str, updates: dict):
    """Safely updates or appends key-value pairs in an .env file without destroying other entries or comments."""
    if not os.path.exists(env_path):
        os.makedirs(os.path.dirname(os.path.abspath(env_path)), exist_ok=True)
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


def prompt_val(prompt_text: str, default_val: str, interactive: bool = True) -> str:
    """Helper to prompt for a value with [Enter] to keep default."""
    if not interactive or not sys.stdin.isatty():
        return default_val
    try:
        val = input(f"{prompt_text} [{default_val}]: ").strip()
        return val if val else default_val
    except (EOFError, KeyboardInterrupt):
        return default_val


def run_customization_wizard(interactive: bool = True):
    """
    Comprehensive interactive CLI wizard covering:
    1. User Preferences
    2. Voice Settings & Cloning
    3. LLM Integration & AI PC Workstation
    4. Swarm, Security & System Infrastructure
    """
    print("=" * 78)
    print("   HELIOS & TWIN ECOSYSTEM — UNIFIED INTERACTIVE CONFIGURATION WIZARD")
    print("   Press [Enter] at any prompt to accept the current/recommended default.")
    print("=" * 78)

    governor = HardwareGovernor()
    detected_tier = governor.decision.tier_name
    print(f"Hardware Profile Detected: {detected_tier}")
    print("-" * 78)

    # Load existing configuration defaults
    existing_env = read_env_file(os.path.join(BASE_DIR, ".env"))
    if not existing_env:
        existing_env = read_env_file(os.path.join(BASE_DIR, "ai-router", ".env"))

    # =========================================================================
    # SECTION 1: USER PREFERENCES
    # =========================================================================
    print("\n" + "=" * 78)
    print(" [1/4] USER PREFERENCES & CALL-SIGN")
    print("=" * 78)

    user_name = prompt_val("  * User Call-sign / Nickname", existing_env.get("USER_NAME", "User"), interactive)
    bot_name = prompt_val("  * Assistant Name", existing_env.get("BOT_NAME", "HELIOS"), interactive)
    
    print("\n  Persona Style Presets:")
    print("    [1] Helpful, professional, and concise (Technical Engineer)")
    print("    [2] Playful, cybernetic, and expressive anime twin companion")
    print("    [3] Tactical operative, zero-fluff mission advisor")
    style_choice = prompt_val("  Select Persona Style [1-3]", "1", interactive)
    personality_map = {
        "1": "helpful, professional, and concise",
        "2": "playful, cybernetic, and expressive anime twin companion",
        "3": "tactical operative, zero-fluff mission advisor"
    }
    personality = personality_map.get(style_choice, "helpful, professional, and concise")
    print(f"    -> Applied Persona: \"{personality}\"")

    wake_word = prompt_val("  * Wake-Word for Audio Activation", existing_env.get("WAKE_WORD", "helios"), interactive)
    hot_mic_default = existing_env.get("ENABLE_HOT_MIC", "false")
    hot_mic_ans = prompt_val("  * Enable Continuous Hot-Mic Listening [true/false]", hot_mic_default, interactive).lower()
    enable_hot_mic = "true" if hot_mic_ans in ("true", "1", "yes", "y") else "false"

    default_workspace = prompt_val("  * Default Codebase Workspace Path", existing_env.get("DEFAULT_WORKSPACE", "C:\\projects"), interactive)

    # =========================================================================
    # SECTION 2: VOICE SETTINGS & CLONING
    # =========================================================================
    print("\n" + "=" * 78)
    print(" [2/4] VOICE ENGINE, PROSODY & CLONING")
    print("=" * 78)

    voice_enabled_ans = prompt_val("  * Enable Neural Speech Synthesis (TTS) [true/false]", existing_env.get("VOICE_ENABLED", "true"), interactive).lower()
    voice_enabled = "true" if voice_enabled_ans in ("true", "1", "yes", "y") else "false"

    print("\n  Voice Backend Options:")
    print("    [1] gpt_sovits  (High-fidelity zero-shot cloned voice — Airi identity)")
    print("    [2] kokoro      (Low-latency 100% local ONNX engine with 54 voices)")
    print("    [3] edge_tts    (Cloud fallback streaming TTS)")
    v_backend_choice = prompt_val("  Select Voice Backend [1-3]", "1" if existing_env.get("VOICE_BACKEND") == "gpt_sovits" else "2", interactive)
    v_backend_map = {"1": "gpt_sovits", "2": "kokoro", "3": "edge_tts"}
    voice_backend = v_backend_map.get(v_backend_choice, "kokoro")
    print(f"    -> Selected Voice Backend: {voice_backend}")

    print("\n  Active Voice Preset:")
    print("    [1] airi        (Japanese-accented English cybernetic twin)")
    print("    [2] af_heart    (Warm, natural female American English)")
    print("    [3] af_bella    (Clear, articulate female American English)")
    print("    [4] am_michael  (Professional male American English)")
    print("    [5] am_adam     (Authoritative male American English)")
    voice_preset_choice = prompt_val("  Select Voice Preset [1-5]", "1" if existing_env.get("VOICE_NAME") == "airi" else "2", interactive)
    voice_name_map = {"1": "airi", "2": "af_heart", "3": "af_bella", "4": "am_michael", "5": "am_adam"}
    voice_name = voice_name_map.get(voice_preset_choice, "af_heart")
    print(f"    -> Selected Voice Name: {voice_name}")

    voice_speed = prompt_val("  * Speaking Speed Multiplier (0.8 - 1.5)", str(existing_env.get("VOICE_SPEED", "1.0")), interactive)

    # GPT-SoVITS specific inputs
    gpt_sovits_url = existing_env.get("GPT_SOVITS_API_URL", "http://127.0.0.1:9880")
    ref_audio = existing_env.get("GPT_SOVITS_REF_AUDIO", "voices/airi/reference.wav")
    ref_text = existing_env.get("GPT_SOVITS_REF_TEXT", "It's nice to meet you. Well, technically, we've already met, haven't we?")
    if voice_backend == "gpt_sovits" or voice_name == "airi":
        gpt_sovits_url = prompt_val("  * GPT-SoVITS API Endpoint URL", gpt_sovits_url, interactive)
        ref_audio = prompt_val("  * Reference Audio File (.wav/.mp3)", ref_audio, interactive)
        ref_text = prompt_val("  * Reference Transcript Text", ref_text, interactive)

    # Audio Audible confirmation test option
    test_audio_now = prompt_val("  * Play Spoken Audio Confirmation through speakers now? [y/N]", "N", interactive).lower() == "y"
    if test_audio_now:
        try:
            print("    [*] Synthesizing and playing confirmation phrase...")
            import sounddevice as sd
            from core.audio.tts.manager import TTSBackendManager
            t_mgr = TTSBackendManager()
            t_mgr.initialize()
            test_phrase = f"Hello {user_name}! Voice synthesis calibration is operational."
            
            import asyncio
            async def _play():
                chunks = []
                sr_out = 24000
                async for ch, s_rate in t_mgr.synthesize(test_phrase, voice=t_mgr.resolve_voice(voice_name)):
                    chunks.append(ch)
                    sr_out = s_rate
                if chunks:
                    import numpy as np
                    sd.play(np.concatenate(chunks), samplerate=sr_out)
                    sd.wait()
            asyncio.run(_play())
            print("    [OK] Spoken confirmation playback complete.")
        except Exception as e:
            print(f"    [!] Audible test notice: {e}")

    # =========================================================================
    # SECTION 3: LLM INTEGRATION & AI PC WORKSTATION
    # =========================================================================
    print("\n" + "=" * 78)
    print(" [3/4] LLM INTEGRATION, PROVIDERS & AI PC WORKSTATION")
    print("=" * 78)

    print("  Inference Provider Architecture:")
    print("    [1] pair    (NVIDIA PAIR GPU Workstation over LAN / High VRAM offload)")
    print("    [2] ollama  (100% Local Inference on this machine via Ollama)")
    print("    [3] gemini  (Google Gemini API Cloud Inference)")
    print("    [4] groq    (Ultra Low Latency Groq Cloud Inference)")
    prov_choice = prompt_val("  Select Primary LLM Provider [1-4]", "1" if existing_env.get("LLM_PROVIDER") == "pair" else "2", interactive)
    prov_map = {"1": "pair", "2": "ollama", "3": "gemini", "4": "groq"}
    llm_provider = prov_map.get(prov_choice, "ollama")
    print(f"    -> Selected Provider: {llm_provider.upper()}")

    ai_pc_ip = existing_env.get("AI_PC_IP", "192.168.100.254")
    ai_pc_mac = existing_env.get("AI_PC_MAC", "30:56:0F:A8:76:05")
    ai_pc_broadcast = existing_env.get("AI_PC_BROADCAST", "192.168.100.255")
    auto_wake_aipc = existing_env.get("AUTO_WAKE_AI_PC", "true")

    if llm_provider == "pair":
        ai_pc_ip = prompt_val("  * AI PC Workstation IP Address", ai_pc_ip, interactive)
        ai_pc_mac = prompt_val("  * AI PC MAC Address (for Wake-on-LAN)", ai_pc_mac, interactive)
        ai_pc_broadcast = prompt_val("  * AI PC Broadcast Subnet", ai_pc_broadcast, interactive)
        auto_wake_aipc = prompt_val("  * Auto Wake-on-LAN if node is sleeping [true/false]", auto_wake_aipc, interactive)

    gemini_key = existing_env.get("GEMINI_API_KEY", "")
    groq_key = existing_env.get("GROQ_API_KEY", "")
    if llm_provider in ("gemini", "groq") or prompt_val("  Configure Cloud API keys for fallback? [y/N]", "N", interactive).lower() == "y":
        gemini_key = prompt_val("  * Gemini API Key", gemini_key, interactive)
        groq_key = prompt_val("  * Groq API Key", groq_key, interactive)

    # Model Configuration
    print("\n  Subsystem Models Selection:")
    primary_model = prompt_val("  * General Reasoning / Orchestrator Model", existing_env.get("PRIMARY_MODEL", "qwen2.5:1.5b"), interactive)
    coder_model = prompt_val("  * Hikari Autonomous Coding Swarm Model", existing_env.get("CODER_MODEL", "qwen2.5-coder:1.5b"), interactive)
    vision_model = prompt_val("  * Visual Screen & Camera Analysis Model", existing_env.get("VISION_MODEL", "moondream:latest"), interactive)
    embed_model = prompt_val("  * Vector RAG Embedding Model", existing_env.get("EMBED_MODEL", "nomic-embed-text:latest"), interactive)

    # =========================================================================
    # SECTION 4: SWARM CONCURRENCY, PORTS & SECURITY
    # =========================================================================
    print("\n" + "=" * 78)
    print(" [4/4] SWARM CONCURRENCY, PORTS & SECURITY GATE")
    print("=" * 78)

    print("  Coding Swarm Concurrency:")
    print("    [1] Sequential single-agent execution (Recommended for <= 16GB RAM / iGPU)")
    print("    [2] Full 8-agent parallel swarm (Recommended for AI PC / 32GB+ RAM)")
    swarm_choice = prompt_val("  Select Swarm Mode [1-2]", "1" if "Budget" in detected_tier else "2", interactive)
    swarm_parallel = "true" if swarm_choice == "2" else "false"

    print("\n  Service Port Bindings:")
    core_port = prompt_val("  * HELIOS Core Server Port", str(existing_env.get("SERVER_PORT", "8000")), interactive)
    hikari_port = prompt_val("  * Hikari Swarm Port", str(existing_env.get("HIKARI_PORT", "8001")), interactive)
    char_port = prompt_val("  * Airi/Ren 3D Companion WebGL Port", str(existing_env.get("CHARACTER_PORT", "8080")), interactive)

    bridge_strict = prompt_val("  * Zero-Trust HMAC-SHA256 Token Bridge [true/false]", existing_env.get("BRIDGE_ENABLED", "true"), interactive)

    # Voice Biometrics enrollment prompt
    enroll_voice = prompt_val("\n  * Enroll or Calibrate Voice Biometrics Security PIN now? [y/N]", "N", interactive).lower() == "y"
    if enroll_voice:
        voice_script = os.path.join(BASE_DIR, "scripts", "verify_voice.py")
        if os.path.exists(voice_script):
            subprocess.run([sys.executable, voice_script])

    # =========================================================================
    # SAVE & SYNCHRONIZE CONFIGURATIONS
    # =========================================================================
    env_updates = {
        "USER_NAME": user_name,
        "BOT_NAME": bot_name,
        "PERSONALITY": personality,
        "WAKE_WORD": wake_word,
        "ENABLE_HOT_MIC": enable_hot_mic,
        "DEFAULT_WORKSPACE": default_workspace,
        
        "VOICE_ENABLED": voice_enabled,
        "VOICE_BACKEND": voice_backend,
        "VOICE_NAME": voice_name,
        "VOICE_SPEED": voice_speed,
        "GPT_SOVITS_ENABLED": "true" if voice_backend == "gpt_sovits" else "false",
        "GPT_SOVITS_API_URL": gpt_sovits_url,
        "GPT_SOVITS_REF_AUDIO": ref_audio,
        "GPT_SOVITS_REF_TEXT": ref_text,
        
        "LLM_PROVIDER": llm_provider,
        "AI_PC_IP": ai_pc_ip,
        "AI_PC_MAC": ai_pc_mac,
        "AI_PC_BROADCAST": ai_pc_broadcast,
        "AUTO_WAKE_AI_PC": auto_wake_aipc,
        "PAIR_HOST": f"http://{ai_pc_ip}:11434" if llm_provider == "pair" else "http://127.0.0.1:11434",
        "OLLAMA_HOST": f"http://{ai_pc_ip}:11434" if llm_provider == "pair" else "http://127.0.0.1:11434",
        "GEMINI_API_KEY": gemini_key,
        "GROQ_API_KEY": groq_key,
        
        "PRIMARY_MODEL": primary_model,
        "CODER_MODEL": coder_model,
        "VISION_MODEL": vision_model,
        "EMBED_MODEL": embed_model,
        
        "SWARM_PARALLEL_ENABLED": swarm_parallel,
        "SERVER_PORT": core_port,
        "HIKARI_PORT": hikari_port,
        "CHARACTER_PORT": char_port,
        "BRIDGE_ENABLED": bridge_strict,
    }

    # Save to both root .env and ai-router/.env
    root_env = os.path.join(BASE_DIR, ".env")
    ai_env = os.path.join(BASE_DIR, "ai-router", ".env")
    update_env_file(root_env, env_updates)
    update_env_file(ai_env, env_updates)
    print("\n[OK] Configuration persisted to root .env and ai-router/.env.")

    # Save structured JSON profile
    profile_data = {
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "user": {"name": user_name, "assistant_name": bot_name, "personality": personality, "wake_word": wake_word, "workspace": default_workspace},
        "voice": {"backend": voice_backend, "name": voice_name, "speed": float(voice_speed), "gpt_sovits_url": gpt_sovits_url, "ref_audio": ref_audio},
        "llm": {"provider": llm_provider, "ai_pc_ip": ai_pc_ip, "models": {"primary": primary_model, "coder": coder_model, "vision": vision_model, "embed": embed_model}},
        "infrastructure": {"ports": {"core": int(core_port), "hikari": int(hikari_port), "character": int(char_port)}, "swarm_parallel": swarm_parallel == "true", "bridge_strict": bridge_strict == "true"}
    }
    config_dir = os.path.join(BASE_DIR, "config")
    os.makedirs(config_dir, exist_ok=True)
    with open(os.path.join(config_dir, "custom_profile.json"), "w", encoding="utf-8") as f:
        json.dump(profile_data, f, indent=2)
    print(f"[OK] Profile structured report saved to {os.path.join(config_dir, 'custom_profile.json')}")

    # Synchronize Living Audit
    audit_script = os.path.join(BASE_DIR, "scripts", "run_audit.py")
    if os.path.exists(audit_script):
        subprocess.run([sys.executable, audit_script])

    print("\n" + "=" * 78)
    print("  [SUCCESS] HELIOS SETUP & CUSTOMIZATION COMPLETE!")
    print("=" * 78)


def run_bootstrap(dry_run: bool = False):
    print("=" * 78)
    print("  HELIOS Autonomous Systems Bootstrap & Hardware Diagnostic")
    print("=" * 78)

    governor = HardwareGovernor()
    print(governor.get_advisory_banner())
    print()

    ensure_safe_env()

    if not dry_run:
        ensure_ollama_installed()
        ensure_ollama_running()

    pull_tier_models(governor, dry_run=dry_run)

    audit_script = os.path.join(BASE_DIR, "scripts", "run_audit.py")
    if os.path.exists(audit_script):
        subprocess.run([sys.executable, audit_script])

    # Check Addons Status
    hikari_addon = os.path.abspath(os.path.join(BASE_DIR, "..", "hikari-addon"))
    solstice_addon = os.path.abspath(os.path.join(BASE_DIR, "..", "solstice-addon"))
    mobile_addon = os.path.abspath(os.path.join(BASE_DIR, "..", "mobile-addon"))
    print("\n[*] Modular Addons Status:")
    if os.path.exists(hikari_addon):
        print(f"  [OK] Hikari Swarm Addon detected at {hikari_addon}")
    else:
        print("  [i] Hikari Swarm Addon not installed (optional).")
    if os.path.exists(solstice_addon):
        print(f"  [OK] Solstice Avatar Addon detected at {solstice_addon}")
    else:
        print("  [i] Solstice Avatar Addon not installed (optional).")
    if os.path.exists(mobile_addon):
        print(f"  [OK] Mobile Companion Addon detected at {mobile_addon}")
    else:
        print("  [i] Mobile Companion Addon not installed (optional).")

    print("\n[OK] Bootstrap health check completed successfully.")


if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    is_custom = "--custom" in sys.argv or "-c" in sys.argv or "/c" in sys.argv

    if is_custom:
        run_customization_wizard(interactive=not is_dry)
    else:
        run_bootstrap(dry_run=is_dry)
