import re

with open("core/audio/stt/google.py", "r", encoding="utf-8") as f:
    google_content = f.read()

# Add Vosk import and model load
if "import vosk" not in google_content:
    google_content = google_content.replace(
        "import speech_recognition as sr",
        "import speech_recognition as sr\nimport json\ntry:\n    import vosk\n    vosk_model = vosk.Model('.models/vosk-model-small-en-us-0.15')\nexcept Exception as e:\n    logger.error(f'Could not load Vosk: {e}')\n    vosk_model = None"
    )

old_init_vars = """        audio_buffer = []
        is_recording = False
        was_barge_in = False"""

new_init_vars = """        audio_buffer = []
        is_recording = False
        was_barge_in = False
        vosk_recognizer = None"""

google_content = google_content.replace(old_init_vars, new_init_vars)

old_barge_in = """                        # BARGE-IN: Only interrupt if HELIOS is actually talking
                        if hasattr(self.voice_manager, 'is_currently_speaking') and self.voice_manager.is_currently_speaking():
                            logger.info("VAD detected speech onset! Interrupting HELIOS.")
                            if toaster:
                                threading.Thread(target=toaster.show_toast, args=("HELIOS", "Interrupted (Barge-in)", None, 2, True), daemon=True).start()
                            self.voice_manager.interrupt()
                            was_barge_in = True
                        else:
                            logger.info("VAD detected speech onset (Listening...)")
                            if toaster:
                                threading.Thread(target=toaster.show_toast, args=("HELIOS", "Listening for command...", None, 2, True), daemon=True).start()
                    else:
                        silence_counter = 0
                        
                    audio_buffer.append(raw_data)"""

new_barge_in = """                        # Setup Vosk for keyword spotting
                        if vosk_model:
                            vosk_recognizer = vosk.KaldiRecognizer(vosk_model, sample_rate)
                            
                        # If HELIOS is talking, we DO NOT interrupt immediately anymore.
                        # We wait for Vosk to hear 'stop'.
                        if hasattr(self.voice_manager, 'is_currently_speaking') and self.voice_manager.is_currently_speaking():
                            logger.info("VAD detected speech onset (Checking for barge-in wake word...)")
                            was_barge_in = True
                        else:
                            logger.info("VAD detected speech onset (Listening...)")
                            if toaster:
                                threading.Thread(target=toaster.show_toast, args=("HELIOS", "Listening for command...", None, 2, True), daemon=True).start()
                    else:
                        silence_counter = 0
                        
                    audio_buffer.append(raw_data)
                    
                    # Feed chunk to Vosk for parallel wake word spotting
                    if vosk_recognizer and was_barge_in and hasattr(self.voice_manager, 'is_currently_speaking') and self.voice_manager.is_currently_speaking():
                        if vosk_recognizer.AcceptWaveform(raw_data):
                            res = json.loads(vosk_recognizer.Result())
                            if "stop" in res.get("text", "") or "wait" in res.get("text", "") or "helios" in res.get("text", ""):
                                logger.info("Vosk detected barge-in wake word! Interrupting HELIOS.")
                                if toaster:
                                    threading.Thread(target=toaster.show_toast, args=("HELIOS", "Interrupted (Barge-in)", None, 2, True), daemon=True).start()
                                self.voice_manager.interrupt()
                        else:
                            res = json.loads(vosk_recognizer.PartialResult())
                            if "stop" in res.get("partial", "") or "wait" in res.get("partial", "") or "helios" in res.get("partial", ""):
                                logger.info("Vosk detected partial barge-in wake word! Interrupting HELIOS.")
                                if toaster:
                                    threading.Thread(target=toaster.show_toast, args=("HELIOS", "Interrupted (Barge-in)", None, 2, True), daemon=True).start()
                                self.voice_manager.interrupt()"""

google_content = google_content.replace(old_barge_in, new_barge_in)

with open("core/audio/stt/google.py", "w", encoding="utf-8") as f:
    f.write(google_content)

print("Patched Vosk parallel STT!")
