import os
import sys
import json
import argparse
import urllib.request
import urllib.error

# Default configuration
DEFAULT_API_URL = "http://127.0.0.1:8000"
USER_ID = 1 # Assuming a default user

def get_or_create_session(api_url):
    """Get the latest session or create a new one."""
    try:
        req = urllib.request.Request(f"{api_url}/api/users/{USER_ID}/sessions")
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                sessions = json.loads(response.read().decode())
                if sessions:
                    return sessions[0]["id"]
    except Exception as e:
        pass
        
    try:
        req = urllib.request.Request(f"{api_url}/api/users/{USER_ID}/sessions", method="POST")
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                return data["id"]
    except Exception as e:
        print(f"Error connecting to HELIOS API: {e}")
        return None

def chat_loop(api_url):
    print("=" * 60)
    print("HELIOS Command Line Interface")
    print(f"Connecting to: {api_url}")
    print("Type 'exit' or 'quit' to exit.")
    print("=" * 60)
    
    session_id = get_or_create_session(api_url)
    if not session_id:
        print("Failed to initialize session. Ensure HELIOS is running.")
        return
        
    print(f"[Session: {session_id}]\n")
    
    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ["exit", "quit"]:
                break
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
    parser = argparse.ArgumentParser(description="HELIOS Headless CLI")
    parser.add_argument("--url", default=os.getenv("HELIOS_API_URL", DEFAULT_API_URL),
                        help="The base URL of the HELIOS API")
    args = parser.parse_args()
    
    try:
        chat_loop(args.url)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
