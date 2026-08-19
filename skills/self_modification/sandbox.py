import sys
import os
import socket
import subprocess

def _audit_hook(event, args):
    # Block writing files
    if event == "open" and len(args) > 1:
        mode = args[1]
        if any(m in mode for m in ('w', 'a', '+', 'x')):
            raise PermissionError(f"Sandbox restricted file modification: mode '{mode}'")

    # Block specific database access (defense in depth)
    if event == "sqlite3.connect":
        db_name = str(args[0])
        if "helios.db" in db_name:
            raise PermissionError("Sandbox restricted access to helios.db")

    # Block network
    if event in ("socket.connect", "socket.bind"):
        raise PermissionError(f"Sandbox restricted network operation: {event}")

    # Block subprocess creation
    if event == "subprocess.Popen" or event.startswith("os.spawn") or event == "os.system":
        raise PermissionError(f"Sandbox restricted process creation: {event}")

    # Block native/ctypes access to prevent sandbox escape
    if event.startswith("ctypes"):
        raise PermissionError(f"Sandbox restricted native reflection: {event}")

try:
    sys.addaudithook(_audit_hook)
except Exception as e:
    print(f"Failed to initialize sandbox: {e}", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python sandbox.py <script_to_run>", file=sys.stderr)
        sys.exit(1)
        
    script_path = sys.argv[1]
    # Shift argv
    sys.argv = sys.argv[1:]
    
    with open(script_path, "r") as f:
        code = f.read()
        
    # Execute the target script
    # We use exec in __main__ namespace to simulate running it directly
    exec(code, {"__name__": "__main__", "__file__": script_path})
