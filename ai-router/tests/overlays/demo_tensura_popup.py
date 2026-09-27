import subprocess
import os
import sys

def run_demo():
    print("=======================================")
    print("   Tensura Overlay Demo (CLI Tool)   ")
    print("=======================================")
    print("This will spawn the fullscreen Tensura-style interactive popup overlay.")
    print("You can interact with it using your mouse or keyboard.")
    print("")
    
    question = input("Enter a question to ask the user (or press Enter for default): ")
    if not question:
        question = "Do you wish to acquire the skill [Auto-Battle]?"
        
    options_raw = input("Enter comma-separated options (or press Enter for default): ")
    options = options_raw if options_raw else "Yes,No,Maybe"
    
    # Path to the overlay script
    overlay_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "overlays", "tensura_popup.py")
    
    print("\nSpawning overlay...")
    try:
        # Run it and capture the output
        result = subprocess.run([sys.executable, overlay_path, question, options], capture_output=True, text=True)
        
        print("\n--- RESULT ---")
        answer = result.stdout.strip()
        if not answer or answer == "CANCELLED":
            print("User hit Esc or cancelled the prompt.")
        else:
            print(f"User selected/typed: {answer}")
            
    except Exception as e:
        print(f"Failed to launch overlay: {e}")

if __name__ == '__main__':
    run_demo()
