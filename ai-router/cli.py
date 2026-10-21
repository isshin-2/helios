import os
import sys
import json
import argparse
import urllib.request
import urllib.error

# Default configuration
DEFAULT_API_URL = "http://127.0.0.1:8000"
import socket
import subprocess
import time

def ensure_server_running(api_url: str):
    """If pointing to localhost and port 8000 is down, automatically boot HELIOS server."""
    if "127.0.0.1" not in api_url and "localhost" not in api_url:
        return

    # Check port 8000
    is_up = False
    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=0.5):
            is_up = True
    except (OSError, socket.timeout):
        is_up = False

    if not is_up:
        print("[*] HELIOS server is offline. Starting HELIOS daemon in background...")
        base_dir = os.path.dirname(os.path.abspath(__file__))
        python_exe = os.path.join(base_dir, "venv", "Scripts", "python.exe")
        if not os.path.exists(python_exe):
            python_exe = sys.executable

        # Spawn uvicorn server in background
        subprocess.Popen(
            [python_exe, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
            cwd=base_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )

        # Poll until port is open (up to 15s)
        for _ in range(30):
            time.sleep(0.5)
            try:
                with socket.create_connection(("127.0.0.1", 8000), timeout=0.5):
                    print("[OK] HELIOS server online.")
                    return
            except (OSError, socket.timeout):
                pass
        print("[!] Warning: HELIOS server took longer than expected to start.")

USER_ID = 1  # Assuming a default user

def create_new_session(api_url):
    """Force creates a brand new session with zero conversational clutter."""
    ensure_server_running(api_url)
    try:
        req = urllib.request.Request(f"{api_url}/api/users/{USER_ID}/sessions", method="POST")
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                return data["id"]
    except Exception as e:
        print(f"Error creating new session: {e}")
        return None

def get_or_create_session(api_url, force_new=False):
    """Get the latest session or create a new one."""
    if force_new:
        return create_new_session(api_url)
    ensure_server_running(api_url)
    try:
        req = urllib.request.Request(f"{api_url}/api/users/{USER_ID}/sessions")
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                sessions = json.loads(response.read().decode())
                if sessions:
                    return sessions[0]["id"]
    except Exception as e:
        pass
        
    return create_new_session(api_url)

def chat_loop(api_url, force_new=False):
    print("=" * 60)
    print("HELIOS Terminal Chat Interface")
    print(f"Connecting to: {api_url}")
    print("Commands: 'exit'/'quit' to exit | '/new' for a fresh session")
    print("=" * 60)
    
    session_id = get_or_create_session(api_url, force_new=force_new)
    if not session_id:
        print("Failed to initialize session. Ensure HELIOS is running.")
        return
        
    print(f"[Session: {session_id}]\n")
    
    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ["exit", "quit"]:
                break
            if user_input.strip().lower() in ["/new", "new", "/clear", "clear"]:
                session_id = create_new_session(api_url)
                print(f"\n[Started Fresh Session: {session_id}]\n")
                continue
            if not user_input.strip():
                continue
                
            print("HELIOS is thinking...")
            
            payload = {
                "user_id": USER_ID,
                "session_id": session_id,
                "message": user_input
            }
            
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                f"{api_url}/api/chat/headless",
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            
            try:
                with urllib.request.urlopen(req) as response:
                    resp_data = json.loads(response.read().decode())
                    
                    # Display Tool Activity
                    tools = resp_data.get("tools_used", [])
                    if tools:
                        print("\n[Activity Log]")
                        for t in tools:
                            print(f"  - {t}")
                        print()
                        
                    # Display Final Response
                    response_text = resp_data.get("response", "").strip()
                    if response_text:
                        # Clean up internal tags for cleaner CLI output
                        import re
                        response_text = re.sub(r'INPUT_REQUIRED::', '[?] ', response_text, flags=re.IGNORECASE)
                        response_text = re.sub(r'APPROVAL_REQUIRED::', '[!] ACTION REQUIRED: ', response_text, flags=re.IGNORECASE)
                        
                        print(f"HELIOS:\n{response_text}\n")
                    else:
                        print("HELIOS: [No response generated]\n")
                        
            except urllib.error.HTTPError as e:
                error_text = e.read().decode()
                print(f"API Error ({e.code}): {error_text}\n")
            except urllib.error.URLError as e:
                print(f"Connection Error: {e.reason}\n")
                    
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\nUnexpected Error: {e}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HELIOS Headless Terminal Chat")
    parser.add_argument("--url", default=os.getenv("HELIOS_API_URL", DEFAULT_API_URL),
                        help="The base URL of the HELIOS API")
    parser.add_argument("--new", "-n", action="store_true",
                        help="Start a clean new chat session")
    args = parser.parse_args()
    
    try:
        chat_loop(args.url, force_new=args.new)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
