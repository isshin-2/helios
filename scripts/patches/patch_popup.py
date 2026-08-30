import re

with open("core/audio/stt/google.py", "r", encoding="utf-8") as f:
    google_content = f.read()

# Add win10toast import
if "ToastNotifier" not in google_content:
    google_content = google_content.replace(
        "import speech_recognition as sr",
        "import speech_recognition as sr\ntry:\n    from win10toast import ToastNotifier\n    toaster = ToastNotifier()\nexcept ImportError:\n    toaster = None\nimport threading"
    )

# Add popup for listening
old_listen = """                            logger.info("VAD detected speech onset (Listening...)")"""
new_listen = """                            logger.info("VAD detected speech onset (Listening...)")
                            if toaster:
                                threading.Thread(target=toaster.show_toast, args=("HELIOS", "Listening for command...", None, 2, True), daemon=True).start()"""
google_content = google_content.replace(old_listen, new_listen)

# Add popup for barge-in
old_barge = """                            logger.info("VAD detected speech onset! Interrupting HELIOS.")"""
new_barge = """                            logger.info("VAD detected speech onset! Interrupting HELIOS.")
                            if toaster:
                                threading.Thread(target=toaster.show_toast, args=("HELIOS", "Interrupted (Barge-in)", None, 2, True), daemon=True).start()"""
google_content = google_content.replace(old_barge, new_barge)

# Add popup for wake word
old_wake = """                    logger.info("Wake word or barge-in detected!")"""
new_wake = """                    logger.info("Wake word or barge-in detected!")
                    if toaster:
                        threading.Thread(target=toaster.show_toast, args=("HELIOS", f"Processing: {cleaned}", None, 2, True), daemon=True).start()"""
google_content = google_content.replace(old_wake, new_wake)

with open("core/audio/stt/google.py", "w", encoding="utf-8") as f:
    f.write(google_content)

print("Patched popups!")
