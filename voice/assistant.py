import asyncio
import logging
import os
import threading
import queue
import tempfile
import json
import httpx

logger = logging.getLogger(__name__)

class VoiceAssistant:
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.is_running = False
        self._thread = None
        
        # Audio queues
        self.stt_queue = queue.Queue()
        self.tts_queue = queue.Queue()
        
    def start(self):
        """Starts the voice assistant in a background thread."""
        if self.is_running:
            return
            
        self.is_running = True
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
            
            logger.info("Voice pipeline active. Listening for wake word: 'helios'...")
            
            while self.is_running:
                # 1. Wait for Wake Word
                try:
                    with microphone as source:
                        audio = recognizer.listen(source, timeout=1, phrase_time_limit=3)
                    
                    # PocketSphinx is local and fast for wake word
                    text = recognizer.recognize_sphinx(audio).lower()
                    
                    if "helios" in text:
                        logger.info("Wake word detected!")
                        # Play a 'boop' sound here ideally
                        
                        # 2. Listen for actual command
                        logger.info("Listening for command...")
                        with microphone as source:
                            command_audio = recognizer.listen(source, timeout=5, phrase_time_limit=15)
                            
                        # 3. Whisper STT (Could be local Whisper or an API)
                        # For now, using Sphinx as placeholder if local whisper isn't configured
                        # In production: command_text = recognizer.recognize_whisper(command_audio)
                        command_text = recognizer.recognize_sphinx(command_audio)
                        logger.info(f"Heard: {command_text}")
                        
                        if command_text.strip():
                            # 4. Send to HELIOS API
                            self._send_to_helios(command_text)
                            
                except sr.WaitTimeoutError:
                    continue
                except sr.UnknownValueError:
                    # Speech was unintelligible
                    continue
                except Exception as e:
                    logger.error(f"Error in voice pipeline: {e}")
                    
        except ImportError:
            logger.error("Voice dependencies missing. Please run: pip install SpeechRecognition pocketsphinx pyaudio")
            self.is_running = False
            
    def _send_to_helios(self, text: str):
        """Send recognized text to the HELIOS backend."""
        # This would typically communicate with the WebSocket or a dedicated REST endpoint.
        # For this modular setup, we can use a REST endpoint if we create one, or WS.
        logger.info(f"Sending to HELIOS: {text}")
        
        # We need a synchronous HTTP request since we're in a thread
        try:
            # Mocking the request. In reality, we'd need a specific user_id and session_id
            payload = {
                "message": text,
                "user_id": 1,
                "session_id": 1
            }
            # Placeholder for actual API call
            # response = httpx.post(f"{self.api_url}/api/voice/chat", json=payload)
            # self._speak(response.json().get("reply"))
            logger.info("HELIOS API call skipped in template.")
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
