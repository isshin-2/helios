with open("core/audio/stt/google.py", "r", encoding="utf-8") as f:
    content = f.read()

old_toaster = """                            if toaster:
                                threading.Thread(target=toaster.show_toast, args=("HELIOS", "Listening for command...", None, 2, True), daemon=True).start()"""

new_toaster = """                            import subprocess, sys
                            try:
                                subprocess.Popen([sys.executable, "scripts/ui_overlay.py"])
                            except Exception:
                                pass"""

if old_toaster in content:
    content = content.replace(old_toaster, new_toaster)
    with open("core/audio/stt/google.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched listening state!")
else:
    print("Could not find listening state code!")
