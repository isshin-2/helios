import os
import sys
import time
import subprocess

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    colors = {
        'BLUE': '\033[94m',
        'CYAN': '\033[96m',
        'GREEN': '\033[92m',
        'RESET': '\033[0m',
        'BOLD': '\033[1m'
    }
    
    logo = rf"""
{colors['CYAN']}{colors['BOLD']}
  _  _   ___   _       ___   ___    ___  
 | || | | __| | |     |_ _| / _ \  / __| 
 | __ | | _|  | |__    | | | (_) | \__ \ 
 |_||_| |___| |____|  |___| \___/  |___/ 
{colors['RESET']}
"""
    print(logo)
    print(f"{colors['BLUE']}Welcome to the HELIOS AI Router!{colors['RESET']}")
    print("Let's get your AI environment configured.\n")

def get_input(prompt, default="", is_secret=False):
    bold = '\033[1m'
    reset = '\033[0m'
    
    display_default = default
    if default and is_secret:
        display_default = default[:4] + "*" * (len(default) - 8) + default[-4:] if len(default) > 8 else "***"
        
    if default:
        res = input(f"{bold}{prompt}{reset} [{display_default}]: ").strip()
        return res if res else default
    return input(f"{bold}{prompt}{reset}: ").strip()

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--reset', action='store_true', help='Force setup to run again')
    args = parser.parse_args()
    
    if args.reset and os.path.exists(".setup_complete"):
        os.remove(".setup_complete")

    if os.path.exists(".setup_complete"):
        return

    # Enable ANSI colors on Windows terminal
    os.system('color')

    clear_screen()
    print_header()

    print("--- 1. Operation Mode ---")
    print("hybrid : Use local models with cloud escalation for complex tasks (Recommended)")
    print("local  : 100% private, offline execution using local hardware")
    print("online : 100% cloud-based using external APIs (no local GPU required)")
    
    # Load existing env for defaults
    env_vars = {}
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if "=" in line:
                    key, val = line.split("=", 1)
                    env_vars[key.strip()] = val.strip()

    mode = env_vars.get("DEPLOYMENT_MODE", "hybrid")
    while True:
        user_mode = get_input("Select Deployment Mode (hybrid/local/online)", mode).lower()
        if user_mode in ['hybrid', 'local', 'online']:
            mode = user_mode
            break

    provider = env_vars.get("LLM_PROVIDER", "ollama")
    ollama_host = env_vars.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    vllm_api_base = env_vars.get("VLLM_API_BASE", "http://127.0.0.1:8000/v1")
    gemini_key = env_vars.get("GEMINI_API_KEY", "")
    openrouter_key = env_vars.get("OPENROUTER_API_KEY", "")

    if mode in ['hybrid', 'local']:
        print("\n--- 2. Local Provider Configuration ---")
        while True:
            user_prov = get_input("Select your local LLM Provider (ollama/vllm)", provider).lower()
            if user_prov in ['ollama', 'vllm']:
                provider = user_prov
                break
        
        if provider == 'ollama':
            ollama_host = get_input("Ollama Host URL", ollama_host)
        else:
            vllm_api_base = get_input("vLLM/LMStudio API Base", vllm_api_base)

    if mode in ['hybrid', 'online']:
        print("\n--- 3. Cloud Provider Configuration ---")
        if mode == 'hybrid':
            print("HELIOS will seamlessly escalate to these providers when local models struggle.")
        gemini_key = get_input("Gemini API Key", gemini_key, is_secret=True)
        openrouter_key = get_input("OpenRouter API Key", openrouter_key, is_secret=True)

    print("\n--- 4. Vision Model ---")
    vision_default = env_vars.get("VISION_MODEL", "gemini-3.7-flash" if mode == 'online' else "qwen2.5vl:3b")
    vision_model = get_input("Vision Model (used for Computer Control)", vision_default)

    print("\n--- 5. Personalization ---")
    bot_name = get_input("Assistant Name", env_vars.get("BOT_NAME", "HELIOS"))
    wake_word = get_input("Wake Word (for voice activation)", env_vars.get("WAKE_WORD", "helios")).lower()
    print("\nAvailable Personalities:")
    print("1) Default   (Helpful, professional, and concise)")
    print("2) JARVIS    (Highly efficient, formal, British butler-like)")
    print("3) Sarcastic (Witty, mildly cynical but ultimately helpful)")
    print("4) GLaDOS    (Cold, calculating, passive-aggressive)")
    print("5) Custom    (Type your own traits or paste a Character Card summary)")
    
    pers_choice = get_input("Choose a personality [1-5]", "1")
    if pers_choice == "2":
        personality = "highly efficient, formal, British butler-like"
    elif pers_choice == "3":
        personality = "witty, mildly cynical but ultimately helpful"
    elif pers_choice == "4":
        personality = "cold, calculating, passive-aggressive"
    elif pers_choice == "5":
        personality = get_input("Enter custom personality traits", env_vars.get("PERSONALITY", "helpful, professional, and concise"))
    else:
        personality = "helpful, professional, and concise"
    
    voice_enabled_str = env_vars.get("VOICE_ENABLED", "true").lower()
    voice_enabled = get_input("Enable Voice Output? (true/false)", voice_enabled_str).lower() == "true"
    
    voice_backend = env_vars.get("VOICE_BACKEND", "kokoro")
    voice_name = env_vars.get("VOICE_NAME", "am_michael")
    voice_speed = env_vars.get("VOICE_SPEED", "1.0")
    
    if voice_enabled:
        voice_backend = get_input("Voice Backend Engine (e.g. kokoro)", voice_backend)
        print("\nAvailable Kokoro Voice Profiles:")
        print("1) am_michael (American Male - Default, Professional)")
        print("2) af_bella   (American Female - Warm, Friendly)")
        print("3) af_sarah   (American Female - Crisp, Clear)")
        print("4) am_adam    (American Male - Deep, Resonant)")
        print("5) bm_george  (British Male - Formal)")
        print("6) bf_emma    (British Female - Calm)")
        print("7) Custom     (Enter a specific profile name)")
        
        v_choice = get_input("Choose a voice profile [1-7]", "1")
        if v_choice == "2":
            voice_name = "af_bella"
        elif v_choice == "3":
            voice_name = "af_sarah"
        elif v_choice == "4":
            voice_name = "am_adam"
        elif v_choice == "5":
            voice_name = "bm_george"
        elif v_choice == "6":
            voice_name = "bf_emma"
        elif v_choice == "7":
            voice_name = get_input("Enter Voice Profile Name", voice_name)
        else:
            voice_name = "am_michael"
        voice_speed = get_input("Voice Speed multiplier", voice_speed)

    print("\n\033[96mSaving Configuration...\033[0m")
    
    env_content = f"""DEPLOYMENT_MODE={mode}
GEMINI_API_KEY={gemini_key}
OPENROUTER_API_KEY={openrouter_key}
LLM_PROVIDER={provider}
OLLAMA_HOST={ollama_host}
VLLM_API_BASE={vllm_api_base}
VISION_MODEL={vision_model}
BOT_NAME={bot_name}
WAKE_WORD={wake_word}
PERSONALITY={personality}
VOICE_ENABLED={str(voice_enabled).lower()}
VOICE_BACKEND={voice_backend}
VOICE_NAME={voice_name}
VOICE_SPEED={voice_speed}
"""
    with open(".env", "w") as f:
        f.write(env_content)
        
    time.sleep(0.5)
    print("\033[92mConfiguration Saved!\033[0m")
    
    print("\033[96mInitializing Neural Database...\033[0m")
    import db
    db.init_db()
    
    with open(".setup_complete", "w") as f:
        f.write("Setup complete.")
        
    print(f"\n\033[1m\033[92m{bot_name} is ready in {mode.upper()} mode.\033[0m Let's go!")
    time.sleep(1)

if __name__ == "__main__":
    main()
