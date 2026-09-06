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
    
    mode = ""
    while mode not in ['hybrid', 'local', 'online']:
        mode = get_input("Select Deployment Mode (hybrid/local/online)", "hybrid").lower()

    provider = "ollama"
    ollama_host = "http://127.0.0.1:11434"
    vllm_api_base = "http://127.0.0.1:8000/v1"
    
    gemini_key = ""
    openrouter_key = ""
    
    # Load existing env for defaults
    existing_gemini = ""
    existing_or = ""
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if line.startswith("GEMINI_API_KEY="):
                    existing_gemini = line.split("=")[1].strip()
                elif line.startswith("OPENROUTER_API_KEY="):
                    existing_or = line.split("=")[1].strip()

    if mode in ['hybrid', 'local']:
        print("\n--- 2. Local Provider Configuration ---")
        provider = ""
        while provider not in ['ollama', 'vllm']:
            provider = get_input("Select your local LLM Provider (ollama/vllm)", "ollama").lower()
        
        if provider == 'ollama':
            ollama_host = get_input("Ollama Host URL", ollama_host)
        else:
            vllm_api_base = get_input("vLLM/LMStudio API Base", vllm_api_base)

    if mode in ['hybrid', 'online']:
        print("\n--- 3. Cloud Provider Configuration ---")
        if mode == 'hybrid':
            print("HELIOS will seamlessly escalate to these providers when local models struggle.")
        gemini_key = get_input("Gemini API Key", existing_gemini, is_secret=True)
        openrouter_key = get_input("OpenRouter API Key", existing_or, is_secret=True)

    print("\n--- 4. Vision Model ---")
    vision_default = "gemini-3.7-flash" if mode == 'online' else "qwen2.5vl:3b"
    vision_model = get_input("Vision Model (used for Computer Control)", vision_default)

    print("\n\033[96mSaving Configuration...\033[0m")
    
    env_content = f"""DEPLOYMENT_MODE={mode}
GEMINI_API_KEY={gemini_key}
OPENROUTER_API_KEY={openrouter_key}
LLM_PROVIDER={provider}
OLLAMA_HOST={ollama_host}
VLLM_API_BASE={vllm_api_base}
VISION_MODEL={vision_model}
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
        
    print(f"\n\033[1m\033[92mHELIOS is ready in {mode.upper()} mode.\033[0m Let's go!")
    time.sleep(1)

if __name__ == "__main__":
    main()
