import queue
import threading
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class AudioPlayer:
    """
    A dedicated playback layer for handling audio chunks asynchronously.
    It runs in a background thread and streams from an internal queue.
    """
    def __init__(self):
        self.audio_queue = queue.Queue()
        self.is_playing = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._stream = None

    def _playback_worker(self):
        try:
            import sounddevice as sd
            
            # Use 24kHz as default since Kokoro outputs 24kHz
            self._stream = sd.OutputStream(samplerate=24000, channels=1, dtype='float32')
            self._stream.start()
            
            while not self._stop_event.is_set():
                try:
                    # Wait for audio chunks to arrive
                    chunk_data = self.audio_queue.get(timeout=0.1)
                    if chunk_data is None:  # Sentinel value to exit
                        break
                        
                    samples, sample_rate = chunk_data
                    
                    # Update samplerate if it changed
                    if self._stream.samplerate != sample_rate:
                        self._stream.stop()
                        self._stream = sd.OutputStream(samplerate=sample_rate, channels=1, dtype='float32')
                        self._stream.start()
                        
                    # Write blockingly to the output stream
                    # If stop is requested, this will finish the current chunk then check the event
                    self._stream.write(samples)
                    self.audio_queue.task_done()
                    
                except queue.Empty:
                    continue
                except sd.PortAudioError as e:
                    if not self._stop_event.is_set():
                        logger.error(f"Audio playback error: {e}")
                        
        except ImportError:
            logger.error("sounddevice not installed. Audio playback disabled.")
        except Exception as e:
            logger.error(f"Unexpected error in audio playback: {e}")
        finally:
            if self._stream:
                try:
                    self._stream.stop()
                    self._stream.close()
                except:
                    pass
            self.is_playing = False
            # Drain the queue so wait_until_done() doesn't hang if the thread crashes
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                    self.audio_queue.task_done()
                except queue.Empty:
                    break

    def start(self):
        if not self.is_playing:
            self._stop_event.clear()
            self.is_playing = True
            self._thread = threading.Thread(target=self._playback_worker, daemon=True)
            self._thread.start()

    def enqueue(self, samples, sample_rate: int):
        """Add an audio chunk to the playback queue."""
        if not self.is_playing:
            self.start()
        self.audio_queue.put((samples, sample_rate))

    def stop(self):
        """Immediately stop playback and clear the queue."""
        self._stop_event.set()
        
        # Clear the queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
                self.audio_queue.task_done()
            except queue.Empty:
                break
                
        # The thread will naturally exit due to _stop_event.is_set()
        if self._thread and self._thread.is_alive():
            # If the stream is stuck writing a chunk, abort it immediately
            if self._stream:
                try:
                    self._stream.abort()
                except:
                    pass
            self._thread.join(timeout=1.0)
            
        self.is_playing = False
        logger.info("Audio playback stopped and queue cleared.")

    def wait_until_done(self):
        """Blocks until the audio queue is fully processed."""
        self.audio_queue.join()