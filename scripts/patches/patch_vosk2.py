import re

with open("core/audio/stt/google.py", "r", encoding="utf-8") as f:
    google_content = f.read()

old_vosk_feed = """                    audio_buffer.append(raw_data)
                    
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
                                self.voice_manager.interrupt()
                else:
                    if is_recording:
                        audio_buffer.append(raw_data)"""

new_vosk_feed = """                    audio_buffer.append(raw_data)
                else:
                    if is_recording:
                        audio_buffer.append(raw_data)
                        
                # Feed chunk to Vosk for parallel wake word spotting (must run on all chunks while recording)
                if is_recording and vosk_recognizer and was_barge_in and hasattr(self.voice_manager, 'is_currently_speaking') and self.voice_manager.is_currently_speaking():
                    if vosk_recognizer.AcceptWaveform(raw_data):
                        res = json.loads(vosk_recognizer.Result())
                        if "stop" in res.get("text", "") or "wait" in res.get("text", "") or "helios" in res.get("text", ""):
                            logger.info("Vosk detected barge-in wake word! Interrupting HELIOS.")
                            if toaster:
                                threading.Thread(target=toaster.show_toast, args=("HELIOS", "Interrupted (Barge-in)", None, 2, True), daemon=True).start()
                            self.voice_manager.interrupt()
                            was_barge_in = False # Don't interrupt multiple times
                    else:
                        res = json.loads(vosk_recognizer.PartialResult())
                        if "stop" in res.get("partial", "") or "wait" in res.get("partial", "") or "helios" in res.get("partial", ""):
                            logger.info("Vosk detected partial barge-in wake word! Interrupting HELIOS.")
                            if toaster:
                                threading.Thread(target=toaster.show_toast, args=("HELIOS", "Interrupted (Barge-in)", None, 2, True), daemon=True).start()
                            self.voice_manager.interrupt()
                            was_barge_in = False # Don't interrupt multiple times"""

google_content = google_content.replace(old_vosk_feed, new_vosk_feed)

with open("core/audio/stt/google.py", "w", encoding="utf-8") as f:
    f.write(google_content)

print("Fixed Vosk feed block!")
