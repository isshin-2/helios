with open("main.py", "r", encoding="utf-8") as f:
    content = f.read()

old_startup = """    logger.info("Voice input auto-started on server startup.")"""
new_startup = """    logger.info("Voice input auto-started on server startup.")
    
    # Pre-initialize Kokoro TTS in the background so the first speech is instant
    import threading
    threading.Thread(target=voice_manager.tts.initialize, daemon=True).start()
    logger.info("Eagerly loading Kokoro TTS in background...")"""

content = content.replace(old_startup, new_startup)

with open("main.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Patched main.py startup!")
