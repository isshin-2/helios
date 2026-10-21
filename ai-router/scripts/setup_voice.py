"""
HELIOS Voice Setup & Profile Manager
Allows users to add custom reference voices (GPT-SoVITS voice cloning),
select Kokoro presets, download voice packs, and test voice output.
"""

import os
import sys
import shutil
import yaml

# ANSI Colors
CYAN = "\033[1;36m"
BLUE = "\033[1;34m"
WHITE = "\033[1;37m"
GREEN = "\033[1;32m"
YELLOW = "\033[1;33m"
RED = "\033[1;31m"
RESET = "\033[0m"
BOLD = "\033[1m"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(BASE_DIR)
VOICES_DIR = os.path.join(ROOT_DIR, "voices")
ENV_PATH = os.path.join(BASE_DIR, ".env")

def load_env() -> dict:
    env = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env

def save_env_keys(updates: dict):
    lines = []
    seen = set()
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    k, v = stripped.split("=", 1)
                    k = k.strip()
                    if k in updates:
                        lines.append(f"{k}={updates[k]}\n")
                        seen.add(k)
                    else:
                        lines.append(line)
                else:
                    lines.append(line)
    
    for k, v in updates.items():
        if k not in seen:
            lines.append(f"{k}={v}\n")

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"{GREEN}[+] Updated {ENV_PATH} successfully.{RESET}")

def add_custom_reference_voice():
    print(f"\n{CYAN}--- [1] Add Custom Voice for GPT-SoVITS Cloning ---{RESET}")
    print(f"{WHITE}Supply a clean 3-10 second .wav recording of the target voice.{RESET}\n")

    voice_name = input(f"{BOLD}Enter Voice Profile Identifier (e.g. helios, airi, custom) [helios]: {RESET}").strip()
    if not voice_name:
        voice_name = "helios"
    voice_name = voice_name.lower().replace(" ", "_")

    target_dir = os.path.join(VOICES_DIR, voice_name)
    os.makedirs(target_dir, exist_ok=True)

    wav_input = input(f"{BOLD}Enter path or drag & drop reference audio file (.wav): {RESET}").strip(' "\'')
    if not wav_input or not os.path.exists(wav_input):
        print(f"{RED}[X] Audio file '{wav_input}' not found. Aborting.{RESET}")
        return

    dest_wav = os.path.join(target_dir, "reference.wav")
    try:
        shutil.copy2(wav_input, dest_wav)
        print(f"{GREEN}[+] Copied audio to: {dest_wav}{RESET}")
    except Exception as e:
        print(f"{RED}[X] Failed to copy audio file: {e}{RESET}")
        return

    ref_text = input(f"{BOLD}Enter exact spoken transcript of this audio snippet: {RESET}").strip()
    if not ref_text:
        ref_text = "Hello! I am your AI assistant. System diagnostics are fully operational."

    dest_txt = os.path.join(target_dir, "reference.txt")
    with open(dest_txt, "w", encoding="utf-8") as f:
        f.write(ref_text + "\n")
    print(f"{GREEN}[+] Wrote transcript to: {dest_txt}{RESET}")

    accent = input(f"{BOLD}Enter accent/style (ja/en/anime/neutral) [ja]: {RESET}").strip() or "ja"
    gender = input(f"{BOLD}Enter gender (female/male) [female]: {RESET}").strip() or "female"

    metadata = {
        "name": voice_name,
        "language": "en",
        "accent": accent,
        "style": {
            "age": "young_adult",
            "gender": gender,
            "energy": "medium",
            "friendliness": "high",
            "expressiveness": "high",
        },
        "model_type": "gpt_sovits",
        "description": f"Custom {gender} voice profile with {accent} accent.",
    }

    dest_meta = os.path.join(target_dir, "metadata.yaml")
    with open(dest_meta, "w", encoding="utf-8") as f:
        yaml.safe_dump(metadata, f, default_flow_style=False)
    print(f"{GREEN}[+] Wrote metadata to: {dest_meta}{RESET}")

    # Set as active in .env
    save_env_keys({
        "VOICE_ENABLED": "true",
        "VOICE_BACKEND": "gpt_sovits",
        "VOICE_NAME": voice_name,
        "GPT_SOVITS_REF_AUDIO": dest_wav,
        "GPT_SOVITS_REF_TEXT": ref_text,
    })

    print(f"\n{GREEN}[V] Voice profile '{voice_name}' is now active via GPT-SoVITS!{RESET}")

def select_kokoro_preset():
    print(f"\n{CYAN}--- [2] Select Kokoro Preset Voice ---{RESET}")
    voices = [
        ("af_heart", "American Female — Expressive, Warm (HELIOS / Airi Default)"),
        ("jf_alpha", "Japanese Female — Subtle Anime Vocal Identity"),
        ("af_bella", "American Female — Friendly, Conversational"),
        ("af_sky", "American Female — Soft, Calm, Gentle"),
        ("am_michael", "American Male — Professional, Precise"),
        ("am_adam", "American Male — Deep, Resonant"),
        ("custom", "Enter Custom Voice Code"),
    ]

    for idx, (code, desc) in enumerate(voices, 1):
        print(f"  {CYAN}[{idx}]{RESET} {WHITE}{code:12}{RESET} : {desc}")

    choice = input(f"\n{BOLD}Select preset [1-7, default=1]: {RESET}").strip()
    if choice == "2":
        sel = "jf_alpha"
    elif choice == "3":
        sel = "af_bella"
    elif choice == "4":
        sel = "af_sky"
    elif choice == "5":
        sel = "am_michael"
    elif choice == "6":
        sel = "am_adam"
    elif choice == "7":
        sel = input(f"{BOLD}Enter Kokoro voice code: {RESET}").strip() or "af_heart"
    else:
        sel = "af_heart"

    save_env_keys({
        "VOICE_ENABLED": "true",
        "VOICE_BACKEND": "kokoro",
        "VOICE_NAME": sel,
    })
    print(f"\n{GREEN}[V] Active voice set to Kokoro '{sel}'!{RESET}")

def download_kokoro_voice_pack():
    print(f"\n{CYAN}--- [3] Download / Verify Kokoro Voice Model Pack ---{RESET}")
    model_dir = os.path.join(BASE_DIR, ".models", "kokoro")
    os.makedirs(model_dir, exist_ok=True)

    import urllib.request
    files = {
        "voices-v1.0.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
        "kokoro-v1.0.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
    }

    for fname, url in files.items():
        dest = os.path.join(model_dir, fname)
        if os.path.exists(dest) and os.path.getsize(dest) > 1000000:
            print(f"  {GREEN}[V]{RESET} {fname} already downloaded ({round(os.path.getsize(dest)/(1024*1024), 1)} MB).")
        else:
            print(f"  {YELLOW}[*]{RESET} Downloading {fname} from official release...")
            try:
                urllib.request.urlretrieve(url, dest)
                print(f"  {GREEN}[+]{RESET} Successfully downloaded {fname}!")
            except Exception as e:
                print(f"  {RED}[X]{RESET} Failed to download {fname}: {e}")

def test_voice_output():
    print(f"\n{CYAN}--- [4] Test Voice Audio Generation ---{RESET}")
    sys.path.insert(0, BASE_DIR)
    try:
        import asyncio
        from core.audio.tts.manager import TTSBackendManager
        manager = TTSBackendManager()
        manager.initialize()
        print(f"Active Backend: {manager._active_backend_name}")
        test_text = "Hello! I am HELIOS. System diagnostics are complete and speech synthesis is operational."
        print(f"Synthesizing test audio: '{test_text}'...")

        async def run_test():
            chunks = []
            async for samples, sr in manager.synthesize(test_text, voice=manager.resolve_voice("af_heart")):
                chunks.append((samples, sr))
            return len(chunks)


        num_chunks = asyncio.run(run_test())
        print(f"{GREEN}[V] Successfully generated {num_chunks} audio chunks! Voice pipeline is 100% operational.{RESET}")
    except Exception as e:
        print(f"{RED}[X] Test synthesis failed: {e}{RESET}")

def main():
    if os.name == 'nt':
        os.system('color')

    print(f"{WHITE}======================================================={RESET}")
    print(f"{CYAN}           HELIOS Voice Configuration & Setup{RESET}")
    print(f"{WHITE}======================================================={RESET}")

    env = load_env()
    curr_backend = env.get("VOICE_BACKEND", "kokoro")
    curr_voice = env.get("VOICE_NAME", "af_heart")
    curr_enabled = env.get("VOICE_ENABLED", "true")
    print(f"Current Settings: Enabled={curr_enabled} | Backend={curr_backend} | Voice={curr_voice}\n")

    print(f"  {GREEN}[1]{RESET} Add Custom Reference Voice (GPT-SoVITS Voice Cloning)")
    print(f"  {WHITE}[2]{RESET} Select Preset Voice (Kokoro / Japanese Anime / Expressive)")
    print(f"  {WHITE}[3]{RESET} Download Full 54-Voice Kokoro Model Pack")
    print(f"  {WHITE}[4]{RESET} Test Voice Synthesis & Playback")
    print(f"  {WHITE}[5]{RESET} Disable Voice Output (Silent Mode)")
    print(f"  {WHITE}[0]{RESET} Back / Exit")
    print(f"{WHITE}-------------------------------------------------------{RESET}")

    choice = input(f"{BOLD}Select an option [1-5, 0 to return]: {RESET}").strip()
    if choice == "1":
        add_custom_reference_voice()
    elif choice == "2":
        select_kokoro_preset()
    elif choice == "3":
        download_kokoro_voice_pack()
    elif choice == "4":
        test_voice_output()
    elif choice == "5":
        save_env_keys({"VOICE_ENABLED": "false"})
        print(f"{YELLOW}[*] Voice output disabled.{RESET}")
    else:
        print("Returning...")

if __name__ == "__main__":
    main()
