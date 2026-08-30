import asyncio
import logging
try:
    import emoji
except ImportError:
    emoji = None
import re
from typing import Optional
import threading

from .tts.kokoro import KokoroTTS
from .playback import AudioPlayer
from config import VOICE_ENABLED, VOICE_NAME, VOICE_SPEED

logger = logging.getLogger(__name__)

class VoiceManager:
    """
    Central manager for Voice operations.
    Coordinates between the EventBus, KokoroTTS, and AudioPlayback.
    Implements sentence-level buffering to stream audio cleanly.
    """
    def __init__(self, event_bus=None):
        self.tts = KokoroTTS()
        self.player = AudioPlayer()
        self.event_bus = event_bus
        self.is_speaking = False
        self.hide_overlay = None # Will be set by VoiceInput
        
        self._text_buffer = ""
        self._tts_queue = asyncio.Queue()
        self._synthesis_task = None
        
        # State tracking for scrubbing
        self._in_think_block = False
        self._in_code_block = False
        
        # We split by sentence-ending punctuation to preserve natural intonation.
        # Splitting on commas causes the TTS to treat them as full stops.
        self.sentence_pattern = re.compile(r'([.?!]+[\s\n]+|\n\n+)')

        if self.event_bus:
            # Subscribe to the orchestrator's chunk stream
            self.event_bus.subscribe("chunk", self._on_chunk)
            self.event_bus.subscribe("done", self._on_done)
            self.event_bus.subscribe("status", self._on_status)

    def _on_chunk(self, data):
        """Called when a new chunk of text arrives from the LLM."""
        if not VOICE_ENABLED:
            return
            
        content = data
        if isinstance(data, dict) and "content" in data:
            content = data["content"]
            
        self._text_buffer += content
        self._process_buffer(force=False)
        
    def _on_done(self, data):
        """Called when the LLM finishes generating the response."""
        if not VOICE_ENABLED:
            return
            
        # Flush whatever is left in the buffer
        self._process_buffer(force=True)
        # Put a sentinel value in the queue so the worker knows the stream is done
        try:
            asyncio.get_event_loop().call_soon_threadsafe(
                self._tts_queue.put_nowait, "<END_OF_STREAM>"
            )
        except RuntimeError:
            self._tts_queue.put_nowait("<END_OF_STREAM>")

    def _on_status(self, data):
        """Reset state if we get a new input request status, just in case."""
        if isinstance(data, str) and "Generating" in data:
            # Start fresh for a new response
            self._text_buffer = ""
            self._in_think_block = False
            self._in_code_block = False
            if not self._synthesis_task or self._synthesis_task.done():
                try:
                    self._synthesis_task = asyncio.create_task(self._synthesis_worker())
                except RuntimeError:
                    pass

    def _clean_and_queue(self, sentence: str):
        """Handles stateful markdown parsing and queues clean text."""
        # State transitions
        if "<think>" in sentence:
            self._in_think_block = True
            sentence = sentence.split("<think>")[0] # Keep anything before the tag
        
        if "</think>" in sentence:
            self._in_think_block = False
            sentence = sentence.split("</think>")[-1] # Keep anything after the tag
            
        # Count code block ticks
        tick_count = sentence.count("```")
        if tick_count % 2 == 1:
            self._in_code_block = not self._in_code_block
            
        # If we are in a block, don't speak!
        if self._in_think_block or self._in_code_block:
            return
            
        # Clean up the sentence
        clean_sentence = re.sub(r'```.*?```', ' [Code] ', sentence, flags=re.DOTALL)
        clean_sentence = re.sub(r'```', '', clean_sentence)
        # Convert interactive buttons into spoken options
        clean_sentence = re.sub(r'<button>(.*?)</button>', r'Option: \1.', clean_sentence, flags=re.IGNORECASE)
        clean_sentence = re.sub(r'<[^>]+>', '', clean_sentence) # Remove stray HTML tags
        clean_sentence = re.sub(r'[*_#~]', '', clean_sentence)
        clean_sentence = re.sub(r'http[s]?://\S+', ' [Link] ', clean_sentence)
        if emoji:
            clean_sentence = emoji.replace_emoji(clean_sentence, replace='')
            
        clean_sentence = clean_sentence.strip()
        
        # Don't try to synthesize empty strings or pure punctuation (like '---')
        if not re.search(r'[a-zA-Z0-9]', clean_sentence):
            return
            
        if clean_sentence:
            try:
                asyncio.get_event_loop().call_soon_threadsafe(
                    self._tts_queue.put_nowait, clean_sentence
                )
            except RuntimeError:
                self._tts_queue.put_nowait(clean_sentence)

    def _process_buffer(self, force: bool = False):
        """Extracts complete sentences and sends them to the TTS queue."""
        while True:
            match = self.sentence_pattern.search(self._text_buffer)
            if match:
                end_pos = match.end()
                sentence = self._text_buffer[:end_pos].strip()
                self._text_buffer = self._text_buffer[end_pos:]
                
                if sentence:
                    self._clean_and_queue(sentence)
            else:
                break
                
        # If force is true, take the remainder
        if force and self._text_buffer.strip():
            self._clean_and_queue(self._text_buffer.strip())
            self._text_buffer = ""

    async def _synthesis_worker(self):
        """Background worker that pulls sentences and synthesizes them."""
        while True:
            try:
                sentence = await self._tts_queue.get()
                
                if sentence is None:  # Shutdown signal
                    break
                    
                if sentence == "<END_OF_STREAM>":
                    # Finished generating and queuing all sentences for this turn.
                    # Wait for physical audio playback to finish so we can hide the overlay.
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, self.player.wait_until_done)
                    self.is_speaking = False
                    if self.hide_overlay:
                        self.hide_overlay()
                    self._tts_queue.task_done()
                    continue
                    
                self.is_speaking = True
                logger.info(f"Synthesizing: {sentence}")
                try:
                    print(f"[HELIOS]: {sentence}")
                except Exception:
                    pass
                
                # Consume the async generator natively
                async for samples, sample_rate in self.tts.synthesize(sentence, voice=VOICE_NAME, speed=VOICE_SPEED):
                    if not self.is_speaking:
                        logger.info("TTS Synthesis aborted mid-sentence due to interrupt.")
                        break
                    self.player.enqueue(samples, sample_rate)
                        
                self._tts_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in synthesis worker: {e}")

    def is_currently_speaking(self):
        return (not self._tts_queue.empty()) or (not self.player.audio_queue.empty()) or (len(self._text_buffer) > 0) or self.is_speaking

    def interrupt(self):
        """
        Barge-in: Stop speaking immediately.
        1. Cancels/terminates audio playback
        2. Clears the TTS queue
        3. Clears text buffer
        """
        logger.info("[VoiceManager] Interrupting current speech!")
        self.is_speaking = False
        
        # Stop physical audio immediately
        self.player.stop()
        
        # Hide overlay if active
        if self.hide_overlay:
            self.hide_overlay()
            
        # Clear the text buffer
        self._text_buffer = ""
        
        # Empty the TTS queue
        while not self._tts_queue.empty():
            try:
                self._tts_queue.get_nowait()
                self._tts_queue.task_done()
            except asyncio.QueueEmpty:
                break
