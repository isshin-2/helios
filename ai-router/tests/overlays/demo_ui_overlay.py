import os
import sys
import time
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def demo_ui_overlay():
    print("Starting Desktop UI Overlay...")
    
    with open("overlay_state.txt", "w") as f:
        f.write("HELIOS initializing...")
        
    proc = subprocess.Popen([sys.executable, "scripts/ui_overlay.py"])
    
    time.sleep(2)
    
    messages = [
        "Listening for commands...",
        "Processing audio...",
        "Executing tool call...",
        "Task completed successfully!",
        "Standing by."
    ]
    
    for msg in messages:
        print(f"Updating overlay state: {msg}")
        with open("overlay_state.txt", "w") as f:
            f.write(msg)
        time.sleep(1.5)
        
    print("Closing overlay...")
    proc.terminate()
    if os.path.exists("overlay_state.txt"):
        os.remove("overlay_state.txt")

if __name__ == "__main__":
    demo_ui_overlay()
