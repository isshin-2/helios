with open("core/audio/voice_manager.py", "r", encoding="utf-8") as f:
    vm_content = f.read()

# Add is_currently_speaking
is_speaking_code = """
    def is_currently_speaking(self):
        return (not self._tts_queue.empty()) or (not self.player.audio_queue.empty()) or (len(self._text_buffer) > 0)

    def interrupt(self):"""

vm_content = vm_content.replace("    def interrupt(self):", is_speaking_code)

with open("core/audio/voice_manager.py", "w", encoding="utf-8") as f:
    f.write(vm_content)

with open("core/audio/stt/google.py", "r", encoding="utf-8") as f:
    google_content = f.read()

old_barge_in = """                        # BARGE-IN: If speech started, interrupt HELIOS immediately
                        logger.info("VAD detected speech onset!")
                        self.voice_manager.interrupt()"""

new_barge_in = """                        # BARGE-IN: Only interrupt if HELIOS is actually talking
                        if hasattr(self.voice_manager, 'is_currently_speaking') and self.voice_manager.is_currently_speaking():
                            logger.info("VAD detected speech onset! Interrupting HELIOS.")
                            self.voice_manager.interrupt()
                        else:
                            logger.info("VAD detected speech onset (Listening...)")"""

google_content = google_content.replace(old_barge_in, new_barge_in)

old_send = """            if text.strip():
                cleaned = text.lower().strip()
                if cleaned in ["cancel", "nevermind", "stop", "abort", "ignore"]:
                    logger.info("Command cancelled by user.")
                else:
                    self._send_to_helios(text)"""

new_send = """            if text.strip():
                cleaned = text.lower().strip()
                
                # Check for cancellation
                if cleaned in ["cancel", "nevermind", "stop", "abort", "ignore"]:
                    logger.info("Command cancelled by user.")
                    return
                    
                # Wake word logic
                # We always require "helios" or "computer" to trigger a command
                if "helios" in cleaned or "computer" in cleaned:
                    logger.info("Wake word detected!")
                    self._send_to_helios(text)
                else:
                    logger.info(f"Ignored (no wake word 'helios' or 'computer'): {text}")"""

google_content = google_content.replace(old_send, new_send)

with open("core/audio/stt/google.py", "w", encoding="utf-8") as f:
    f.write(google_content)

print("Patched!")
