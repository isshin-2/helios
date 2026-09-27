import os
import sys
import time
import subprocess
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def demo_autonomous_overlay():
    print("Starting Autonomous Banner Overlay...")
    # Make sure state is 1
    with open("overlay_state.txt", "w") as f:
        f.write("1")
    
    proc = subprocess.Popen([sys.executable, "scripts/autonomous_overlay.py"])
    
    print("Banner should be visible at the top of the screen.")
    print("Flashing banner (toggling state) in 3 seconds...")
    time.sleep(3)
    
    for i in range(3):
        with open("overlay_state.txt", "w") as f:
            f.write("0")
        time.sleep(0.5)
        with open("overlay_state.txt", "w") as f:
            f.write("1")
        time.sleep(0.5)
        
    print("Closing banner...")
    proc.terminate()
    if os.path.exists("overlay_state.txt"):
        os.remove("overlay_state.txt")

if __name__ == "__main__":
    demo_autonomous_overlay()
