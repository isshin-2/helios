import subprocess
import json
import os
import sys
import threading
import time
from dotenv import load_dotenv

load_dotenv()

cmd = "npx.cmd" if os.name == "nt" else "npx"

process = subprocess.Popen(
    [cmd, "-y", "@aaronsb/google-workspace-mcp"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=sys.stderr,
    text=True,
    bufsize=1,
    env=os.environ.copy()
)

def send_request(method, params=None, req_id=1):
    req = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params or {}
    }
    process.stdin.write(json.dumps(req) + "\n")
    process.stdin.flush()

send_request("initialize", {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {"name": "manual_cli", "version": "1.0"}
}, req_id=1)

def read_loop():
    for line in process.stdout:
        try:
            msg = json.loads(line)
            if msg.get("id") == 1:
                process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
                process.stdin.flush()
                send_request("tools/call", {
                    "name": "manage_accounts",
                    "arguments": {
                        "operation": "add",
                        "services": "gmail,drive,contacts,calendar",
                        "access": "read"
                    }
                }, req_id=3)
            elif msg.get("id") == 3:
                print("\n\n>>> AUTH RESULT <<<")
                content = msg.get("result", {}).get("content", [])
                for block in content:
                    print(block.get("text", ""))
                print("===================\n")
                # Wait 5 more seconds to ensure everything saves then exit
                time.sleep(5)
                process.kill()
                os._exit(0)
        except Exception as e:
            pass

t = threading.Thread(target=read_loop, daemon=True)
t.start()
# Keep it alive for up to 3 minutes for the user to complete auth
time.sleep(180)
process.kill()
