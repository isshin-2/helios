import re

with open("core/audio/stt/google.py", "r", encoding="utf-8") as f:
    content = f.read()

# Find the while loop and replace it
new_while = """        while self.is_running:
            try:
                # Read 512 samples (1024 bytes)
                raw_data = stream.read(chunk_size, exception_on_overflow=False)
                
                # Check VAD
                is_speech = self.vad.is_speech(raw_data, frame_rate=sample_rate, sample_width=2)
                
                if is_speech:
                    if not is_recording:
                        is_recording = True
                        silence_counter = 0
                        # Setup Vosk for keyword spotting
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
                else:
                    if is_recording:
                        audio_buffer.append(raw_data)
                        silence_counter += 1
                        
                        if silence_counter > max_silence_chunks:
                            # Speech ended
                            is_recording = False
                            
                            # We have enough audio? (At least 1 second total)
                            if len(audio_buffer) > int((sample_rate / chunk_size) * 0.5):
                                self._current_barge_in = was_barge_in
                                self._process_audio(b"".join(audio_buffer), sample_rate)
                                was_barge_in = False
                                
                            audio_buffer = []
                            silence_counter = 0

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
                            was_barge_in = False # Don't interrupt multiple times
            except Exception as e:
                logger.error(f"Error in microphone loop: {e}")
                time.sleep(0.1)
                
        stream.stop_stream()
        stream.close()
        pa.terminate()"""

# Replace from `while self.is_running:` to `pa.terminate()`
start_idx = content.find("        while self.is_running:")
end_idx = content.find("        pa.terminate()") + len("        pa.terminate()")

if start_idx != -1 and end_idx != -1:
    content = content[:start_idx] + new_while + content[end_idx:]
    with open("core/audio/stt/google.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Successfully replaced while loop.")
else:
    print("Could not find while loop bounds.")
