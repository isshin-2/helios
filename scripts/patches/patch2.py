with open("core/audio/stt/google.py", "r", encoding="utf-8") as f:
    google_content = f.read()

google_content = google_content.replace(
    "audio_buffer = []\n        is_recording = False",
    "audio_buffer = []\n        is_recording = False\n        was_barge_in = False"
)

google_content = google_content.replace(
    "                            logger.info(\"VAD detected speech onset! Interrupting HELIOS.\")\n                            self.voice_manager.interrupt()",
    "                            logger.info(\"VAD detected speech onset! Interrupting HELIOS.\")\n                            self.voice_manager.interrupt()\n                            was_barge_in = True"
)

old_send = """                # Wake word logic
                # We always require "helios" or "computer" to trigger a command
                if "helios" in cleaned or "computer" in cleaned:
                    logger.info("Wake word detected!")
                    self._send_to_helios(text)
                else:
                    logger.info(f"Ignored (no wake word 'helios' or 'computer'): {text}")"""

new_send = """                # Wake word logic
                # If we interrupted the AI (barge-in), we don't require the wake word
                if getattr(self, '_current_barge_in', False) or "helios" in cleaned or "computer" in cleaned:
                    logger.info("Wake word or barge-in detected!")
                    self._send_to_helios(text)
                else:
                    logger.info(f"Ignored (no wake word 'helios' or 'computer'): {text}")"""

google_content = google_content.replace(
    "self._process_audio(b\"\".join(audio_buffer), sample_rate)",
    "self._current_barge_in = was_barge_in\n                                self._process_audio(b\"\".join(audio_buffer), sample_rate)\n                                was_barge_in = False"
)

google_content = google_content.replace(old_send, new_send)

with open("core/audio/stt/google.py", "w", encoding="utf-8") as f:
    f.write(google_content)
print("Patched barge-in wake word logic!")
