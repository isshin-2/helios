import asyncio
import logging
import os
import threading
import queue
import json
import httpx
import sys
import os
import subprocess

logger = logging.getLogger(__name__)

class VoiceAssistant:
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.is_running = False
        self._thread = None
        
        # Audio queues
        self.stt_queue = queue.Queue()
        self.tts_queue = queue.Queue()
        
        self.manual_trigger = False
        self.overlay_process = None
        
    def _show_overlay(self, text="HELIOS Listening..."):
        if self.overlay_process:
            return
            
        script_path = os.path.join(os.path.dirname(__file__), 'overlay_webview.py')
        # Use sys.executable to run it inside the current virtual environment
        self.overlay_process = subprocess.Popen([sys.executable, script_path])
        
    def _hide_overlay(self):
        if self.overlay_process:
            try:
                self.overlay_process.terminate()
            except Exception:
                pass
            self.overlay_process = None

    def trigger(self):
        """Manually bypass the wake word."""
        self.manual_trigger = True
        
    def start(self):
        """Starts the voice assistant in a background thread."""
        if self.is_running:
            return
            
        self.is_running = True
        self.manual_trigger = False
        self._thread = threading.Thread(target=self._run_pipeline, daemon=True)
        self._thread.start()
        logger.info("Voice assistant started.")
        
    def stop(self):
        """Stops the voice assistant."""
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("Voice assistant stopped.")
        
    def _run_pipeline(self):
        """Main loop for the voice pipeline."""
        try:
            # We would import speech_recognition, porcupine, etc. here
            # to keep dependencies optional if voice is disabled.
            import speech_recognition as sr
            
            # Use pocketsphinx for wake word detection (offline)
            # or Porcupine if the user has an access key.
            # For this modular template, we use basic PocketSphinx via SpeechRecognition
            
            recognizer = sr.Recognizer()
            microphone = sr.Microphone()
            
            with microphone as source:
                recognizer.adjust_for_ambient_noise(source)
            
            logger.info("Voice pipeline active. Listening for wake word: 'helios' or 'computer'...")
            
            while self.is_running:
                # 1. Wait for Wake Word
                try:
                    if not self.manual_trigger:
                        with microphone as source:
                            audio = recognizer.listen(source, timeout=1, phrase_time_limit=3)
                        
                        # Switching from Sphinx to Google API because Sphinx's acoustic model is mishearing everything
                        text = recognizer.recognize_google(audio).lower()
                        
                        if text.strip():
                            logger.info(f"[DEBUG] Google heard: '{text}'")
                        
                        if "helios" not in text and "computer" not in text and "assistant" not in text:
                            continue
                            
                    self.manual_trigger = False
                    logger.info("Wake word detected or manually triggered!")
                    # Play a 'boop' sound here ideally
                    
                    # 2. Listen for actual command
                    logger.info("Listening for command...")
                    self._show_overlay()
                    
                    try:
                        with microphone as source:
                            command_audio = recognizer.listen(source, timeout=5, phrase_time_limit=15)
                            
                        # 3. Google STT for command
                        command_text = recognizer.recognize_google(command_audio)
                        logger.info(f"Heard: {command_text}")
                        
                        if command_text.strip():
                            cleaned_command = command_text.lower().strip()
                            # Check if the user wants to abort the command
                            if cleaned_command in ["cancel", "nevermind", "stop", "abort", "never mind", "ignore"]:
                                logger.info("Command cancelled by user. Returning to standby.")
                            else:
                                # 4. Send to HELIOS API
                                self._send_to_helios(command_text)
                    finally:
                        self._hide_overlay()
                        
                except sr.WaitTimeoutError:
                    # Normal if no one is speaking, but good to know it's cycling
                    continue
                except sr.UnknownValueError:
                    logger.warning("Microphone picked up audio, but couldn't understand it (UnknownValueError).")
                    continue
                except Exception as e:
                    logger.error(f"Error in voice pipeline: {e}")
                    
        except ImportError:
            logger.error("Voice dependencies missing. Please run: pip install SpeechRecognition pocketsphinx pyaudio")
            self.is_running = False
            
    def _send_to_helios(self, text: str):
        """Send recognized text to the HELIOS backend."""
        logger.info(f"Sending to HELIOS: {text}")
        
        try:
            user_id = 1
            # 1. Get or create a session
            session_id = None
            try:
                res = httpx.get(f"{self.api_url}/api/users/{user_id}/sessions")
                if res.status_code == 200 and res.json():
                    session_id = res.json()[0]["id"]
            except Exception:
                pass
                
            if not session_id:
                res = httpx.post(f"{self.api_url}/api/users/{user_id}/sessions")
                if res.status_code == 200:
                    session_id = res.json()["id"]
                    
            if not session_id:
                logger.error("Could not get a session ID.")
                return
                
            # 2. Send the message via headless API
            payload = {
                "message": text,
                "user_id": user_id,
                "session_id": session_id
            }
            
            # Using a long timeout for LLM generation
            response = httpx.post(f"{self.api_url}/api/chat/headless", json=payload, timeout=300.0)
            
            if response.status_code == 200:
                data = response.json()
                reply_text = data.get("response", "")
                
                # Strip out markdown formatting for cleaner speech
                import re
                clean_text = re.sub(r'[*_#`\[\]]', '', reply_text)
                
                logger.info(f"HELIOS replied: {clean_text}")
                self._speak(clean_text)
            else:
                logger.error(f"HELIOS returned status {response.status_code}")
                
        except Exception as e:
            logger.error(f"Failed to communicate with HELIOS: {e}")
            
    def _speak(self, text: str):
        """TTS using Piper or pyttsx3."""
        if not text:
            return
            
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except ImportError:
            logger.error("pyttsx3 not installed. Cannot speak.")
