import speech_recognition as sr
import threading
import logging
import json
import time
import httpx
import subprocess
import sys
import os

try:
    import pyaudio
    import vosk
except ImportError:
    pyaudio = None
    vosk = None

logger = logging.getLogger(__name__)

class VoiceInput:
    def __init__(self, voice_manager, api_url: str = "http://localhost:8000"):
        self.voice_manager = voice_manager
        self.api_url = api_url
        self.is_running = False
        self._current_session_id = None
        self._cached_session_id = None  # Persists across voice commands
        self._http_client = httpx.Client(timeout=httpx.Timeout(connect=5.0, read=300.0, write=60.0, pool=None))
        self.recognizer = sr.Recognizer()
        
        self.overlay_process = None
        
        # We need to hide overlay when AI finishes
        # Hacky way: attach hide_overlay to voice_manager so it can call it
        self.voice_manager.hide_overlay = self._hide_overlay
        
        # Load VAD
        try:
            from core.audio.vad import SileroVAD
            self.vad = SileroVAD()
        except ImportError:
            self.vad = None
            logger.warning("SileroVAD not available.")

    def _show_overlay(self):
        if self.overlay_process:
            return
        try:
            script_path = os.path.abspath("scripts/ui_overlay.py")
            self.overlay_process = subprocess.Popen([sys.executable, script_path])
        except Exception as e:
            logger.error(f"Failed to spawn Siri overlay: {e}")

    def _hide_overlay(self):
        if self.overlay_process:
            try:
                self.overlay_process.terminate()
            except Exception:
                pass
            self.overlay_process = None

    def start(self):
        if self.is_running or not pyaudio:
            return
        self.is_running = True
        threading.Thread(target=self._mic_loop, daemon=True).start()
        logger.info("Voice input started.")

    def stop(self):
        self.is_running = False
        self._hide_overlay()
        
    def _mic_loop(self):
        pa = pyaudio.PyAudio()
        sample_rate = 16000
        chunk_size = 1024 # 64ms chunks
        
        try:
            stream = pa.open(format=pyaudio.paInt16,
                             channels=1,
                             rate=sample_rate,
                             input=True,
                             frames_per_buffer=chunk_size)
        except OSError as e:
            logger.error(f"Microphone access denied or unavailable: {e}. Check Windows Privacy settings or connected devices.")
            self.is_running = False
            return
                         
        vosk_model = None
        vosk_recognizer = None
        try:
            # Fast Vosk model for wake word & barge-in
            model_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".models", "vosk-model-small-en-us-0.15")
            if os.path.exists(model_path):
                vosk_model = vosk.Model(model_path)
                vosk_recognizer = vosk.KaldiRecognizer(vosk_model, sample_rate)
            else:
                logger.warning("Vosk model not found, offline wake word disabled.")
        except Exception as e:
            logger.error(f"Failed to load Vosk: {e}")

        logger.info("Microphone loop active (Waiting for 'helios'...).")
        
        state = "IDLE" # IDLE or LISTENING
        audio_buffer = []
        silence_counter = 0
        has_spoken = False
        max_silence_chunks = int((sample_rate / chunk_size) * 2.0) # Increased to 2.0s for slower speech
        max_wait_chunks = int((sample_rate / chunk_size) * 8.0) # Increased to 8.0s initial wait
        
        while self.is_running:
            try:
                raw_data = stream.read(chunk_size, exception_on_overflow=False)
                
                # Check for Barge-in when AI is speaking
                if hasattr(self.voice_manager, 'is_currently_speaking') and self.voice_manager.is_currently_speaking():
                    if vosk_recognizer:
                        if vosk_recognizer.AcceptWaveform(raw_data):
                            res = json.loads(vosk_recognizer.Result())
                            text = res.get("text", "")
                        else:
                            res = json.loads(vosk_recognizer.PartialResult())
                            text = res.get("partial", "")
                            
                        if any(w in text for w in ["stop", "wait", "helios"]):
                            logger.info("Barge-in detected! Interrupting.")
                            self.voice_manager.interrupt()
                            
                            # Cancel the actual LLM generation on the server
                            if self._current_session_id is not None:
                                def _cancel_call():
                                    try:
                                        self._http_client.post(f"{self.api_url}/api/chat/cancel/{self._current_session_id}", timeout=2.0)
                                    except Exception as e:
                                        logger.warning(f"Failed to cancel LLM generation: {e}")
                                threading.Thread(target=_cancel_call, daemon=True).start()
                                
                            if "helios" in text:
                                state = "LISTENING" # Go straight to listening
                                audio_buffer = []
                                has_spoken = False
                                silence_counter = 0
                                self._show_overlay()
                            else:
                                state = "IDLE"
                                self._hide_overlay()
                                audio_buffer = []
                                
                            # Reset recognizer
                            vosk_recognizer = vosk.KaldiRecognizer(vosk_model, sample_rate)
                    continue
                    
                if state == "IDLE":
                    # Feed chunk to Vosk for Wake Word
                    if vosk_recognizer:
                        if vosk_recognizer.AcceptWaveform(raw_data):
                            res = json.loads(vosk_recognizer.Result())
                            if "helios" in res.get("text", "") or "computer" in res.get("text", ""):
                                logger.info("Wake word detected!")
                                state = "LISTENING"
                                audio_buffer = []
                                silence_counter = 0
                                has_spoken = False
                                self._show_overlay()
                        else:
                            res = json.loads(vosk_recognizer.PartialResult())
                            if "helios" in res.get("partial", "") or "computer" in res.get("partial", ""):
                                logger.info("Wake word detected (partial)!")
                                state = "LISTENING"
                                audio_buffer = []
                                silence_counter = 0
                                has_spoken = False
                                # Reset recognizer to clear the partial
                                vosk_recognizer = vosk.KaldiRecognizer(vosk_model, sample_rate)
                                self._show_overlay()
                
                elif state == "LISTENING":
                    audio_buffer.append(raw_data)
                    
                    if self.vad and self.vad.is_speech(raw_data, frame_rate=sample_rate, sample_width=2):
                        silence_counter = 0
                        has_spoken = True
                    else:
                        silence_counter += 1
                        
                    should_cut_off = False
                    if has_spoken and silence_counter > max_silence_chunks:
                        should_cut_off = True
                    elif not has_spoken and silence_counter > max_wait_chunks:
                        should_cut_off = True
                        logger.info("Listening timed out (no speech detected).")
                        
                    if should_cut_off:
                        if len(audio_buffer) > int((sample_rate / chunk_size) * 0.5): # At least 0.5s of audio
                            self._process_audio(b"".join(audio_buffer), sample_rate)
                        else:
                            self._hide_overlay()
                        
                        state = "IDLE"
                        audio_buffer = []
                        silence_counter = 0
                        has_spoken = False
                        # Reset Vosk recognizer to clear old noise
                        if vosk_model:
                            vosk_recognizer = vosk.KaldiRecognizer(vosk_model, sample_rate)
                            
            except Exception as e:
                logger.error(f"Error in mic loop: {e}")
                time.sleep(0.1)

        stream.stop_stream()
        stream.close()
        pa.terminate()

    def _process_audio(self, raw_bytes: bytes, sample_rate: int):
        audio_data = sr.AudioData(raw_bytes, sample_rate, 2)
        try:
            logger.info("Sending to Google STT...")
            text = self.recognizer.recognize_google(audio_data)
            logger.info(f"Heard: {text}")
            print(f"\n[🗣️ You]: {text}\n")
            
            if text.strip():
                cleaned = text.lower().strip()
                if cleaned in ["cancel", "nevermind", "stop", "abort", "ignore"]:
                    logger.info("Command cancelled.")
                    self._hide_overlay()
                    return
                self._send_to_helios(text)
            else:
                self._hide_overlay()
        except sr.UnknownValueError:
            logger.debug("Google STT could not understand audio.")
            self._hide_overlay()
        except sr.RequestError as e:
            logger.error(f"Could not request results from Google STT; {e}")
            self._hide_overlay()
            
    def _send_to_helios(self, text: str):
        logger.info(f"Sending to HELIOS: {text}")
        def do_post():
            try:
                user_id = 1
                session_id = self._cached_session_id
                
                # Only look up session if we don't have one cached
                if not session_id:
                    try:
                        res = self._http_client.get(f"{self.api_url}/api/users/{user_id}/sessions")
                        if res.status_code == 200 and res.json():
                            session_id = res.json()[0]["id"]
                    except Exception:
                        pass
                    
                    if not session_id:
                        res = self._http_client.post(f"{self.api_url}/api/users/{user_id}/sessions")
                        if res.status_code == 200:
                            session_id = res.json()["id"]
                        
                if not session_id:
                    logger.error("Could not get a session ID.")
                    self._hide_overlay()
                    return
                
                self._current_session_id = session_id
                self._cached_session_id = session_id  # Cache for next command
                    
                payload = {
                    "message": text,
                    "user_id": user_id,
                    "session_id": session_id
                }
                
                # Note: VoiceManager is listening globally to the EventBus
                self._http_client.post(f"{self.api_url}/api/chat/headless", json=payload)
            except Exception as e:
                logger.error(f"Failed to communicate with HELIOS: {e}")
                self._hide_overlay()
                
        threading.Thread(target=do_post, daemon=True).start()
