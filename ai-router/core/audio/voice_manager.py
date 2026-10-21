import asyncio
import logging
try:
    import emoji
except ImportError:
    emoji = None
import re
from typing import Optional, Tuple, Any, List
import threading

from .localai_audio import LocalAIAudio
from .tts.kokoro import KokoroTTS
from .tts.manager import TTSBackendManager
from .tts.speech_planner import SpeechPlanner, SpeechPlan
from .tts.text_normalizer import TextNormalizer, StreamingFilterState
from .tts.audio_processor import AudioProcessor
from .tts.resource_policy import resource_manager
from .playback import AudioPlayer
import config

logger = logging.getLogger(__name__)


class VoiceManager:
    """
    Central manager for Voice operations.
    Coordinates between EventBus, SpeechPlanner, TTSBackendManager, AudioProcessor, and AudioPlayer.
    Implements sentence-level buffering to stream expressive audio cleanly with low latency.
    """

    def __init__(self, event_bus=None):
        self.tts_manager = TTSBackendManager()
        self.kokoro = self.tts_manager.kokoro
        self.localai = LocalAIAudio()
        if getattr(config, "VOICE_BACKEND", "kokoro") == "localai":
            self.tts = self.localai
        else:
            self.tts = self.tts_manager
        self.player = AudioPlayer()
        self.event_bus = event_bus
        self.is_speaking = False
        self.hide_overlay = None  # Will be set by VoiceInput

        # TTS Enhancement Pipeline
        self.speech_planner = SpeechPlanner()
        self.audio_processor = AudioProcessor()
        self.normalizer = self.speech_planner.normalizer
        self.filter_state = StreamingFilterState()

        self._text_buffer = ""
        self._tts_queue = asyncio.Queue()
        self._synthesis_task = None
        self._current_turn_id: int = 0

        # Sentence segmentation
        self.sentence_pattern = re.compile(r'([.?!]+(?=[\s\n])|\n\n+)')

        if self.event_bus:
            # Subscribe to the orchestrator's chunk stream
            self.event_bus.subscribe("chunk", self._on_chunk)
            self.event_bus.subscribe("done", self._on_done)
            self.event_bus.subscribe("status", self._on_status)

    def _get_character_state(self) -> Tuple[str, float, str, bool]:
        """Fetch live emotion and safety state from CharacterManager without tight coupling."""
        emotion = "neutral"
        intensity = 0.5
        style = "natural"
        safety_locked = False
        try:
            from core.character_manager import character_manager
            if getattr(character_manager, "enabled", False):
                state = getattr(character_manager, "state", None)
                if state:
                    emotion = getattr(state, "emotion", "neutral")
                    intensity = getattr(state, "intensity", 0.5)
                    style = getattr(state, "style", "natural")
                safety_locked = bool(getattr(character_manager, "safety_locked", False))
        except Exception:
            pass
        return emotion, intensity, style, safety_locked

    def _enqueue_tts(self, item: Any):
        """Threadsafe enqueue helper that handles both running and absent event loops."""
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(self._tts_queue.put_nowait, item)
        except RuntimeError:
            self._tts_queue.put_nowait(item)

    def _on_chunk(self, data):
        """Called when a new chunk of text arrives from the LLM."""
        if not getattr(config, "VOICE_ENABLED", True):
            return

        content = data
        if isinstance(data, dict) and "content" in data:
            content = data["content"]

        self._text_buffer += content

    def _on_done(self, data):
        """Called when the LLM finishes generating the response."""
        if not getattr(config, "VOICE_ENABLED", True):
            return

        # Flush whatever is left in the buffer once LLM token generation is complete
        resource_manager.set_llm_active(False)
        self._process_buffer(force=True)
        # Put sentinel with current turn ID so worker knows the stream is done
        self._enqueue_tts((self._current_turn_id, "<END_OF_STREAM>"))

    def _on_status(self, data):
        """Reset state if we get a new input request status."""
        if isinstance(data, str) and "Generating" in data:
            # New turn started
            resource_manager.set_llm_active(True)
            self._current_turn_id += 1
            self._text_buffer = ""
            self.filter_state.reset()
            if not self._synthesis_task or self._synthesis_task.done():
                try:
                    self._synthesis_task = asyncio.create_task(self._synthesis_worker())
                except RuntimeError:
                    pass

    def _clean_and_queue(self, sentence: str):
        """Processes raw text chunk through stateful filter, plans speech, and queues plan."""
        # Handle streaming think and code blocks
        clean_text, self.filter_state = self.normalizer.filter_streaming_chunk(
            sentence, self.filter_state
        )
        if clean_text is None or not clean_text.strip():
            return

        if self.normalizer.should_mute(sentence) or self.normalizer.should_mute(clean_text):
            return

        # Fetch character emotion & safety constraints
        emotion, intensity, style, safety_locked = self._get_character_state()

        # Build comprehensive speech plan
        plan = self.speech_planner.plan(
            text=clean_text,
            emotion=emotion,
            intensity=intensity,
            style=style,
            safety_locked=safety_locked,
        )

        if plan:
            plan.turn_id = self._current_turn_id
            self._enqueue_tts(plan)

    def _process_buffer(self, force: bool = False):
        """Extracts complete sentences and sends them to the TTS queue."""
        sentences, remaining = self.speech_planner.extract_sentences(self._text_buffer, force=force)
        self._text_buffer = remaining
        for sentence in sentences:
            self._clean_and_queue(sentence)

    def _publish_bus_event(self, event_type: str, data=None):
        """Publish an event to both the local bus (if any) and global_bus safely."""
        try:
            from core.events import global_bus
            buses = [global_bus]
            if self.event_bus and self.event_bus is not global_bus:
                buses.append(self.event_bus)
            try:
                loop = asyncio.get_running_loop()
                for b in buses:
                    loop.create_task(b.publish(event_type, data))
            except RuntimeError:
                import core.events as _ce
                if _ce.main_loop and _ce.main_loop.is_running():
                    for b in buses:
                        asyncio.run_coroutine_threadsafe(b.publish(event_type, data), _ce.main_loop)
        except Exception:
            pass

    @staticmethod
    def _compute_lip_sync_metadata(samples, sample_rate: int, text: str, kokoro_instance: Optional[Any] = None) -> dict:
        """
        Compute 30-FPS RMS amplitude envelope, enhanced phoneme-to-viseme timeline,
        and 16-bit PCM WAV base64 from conditioned audio samples.
        """
        import base64
        import io
        import wave
        import numpy as np

        arr = np.asarray(samples, dtype=np.float32).flatten()
        sr = int(sample_rate or 24000)
        duration = float(len(arr)) / sr if sr > 0 else 0.0

        # 30 FPS RMS envelope
        win = max(1, sr // 30)
        rms = []
        for i in range(0, len(arr), win):
            frame = arr[i : i + win]
            val = float(np.sqrt(np.mean(frame * frame))) if len(frame) else 0.0
            rms.append(round(min(1.0, val * 3.5), 3))

        # Enhanced phoneme-to-viseme mapping for VRM blendshapes: ["aa", "ih", "ou", "ee", "oh"]
        # IPA vowel and consonant mapping table
        visemes = []
        words = [w for w in re.findall(r"[A-Za-z0-9]+", text or "") if w]
        
        # Check if Kokoro phonemize is available
        phonemes = None
        if kokoro_instance and hasattr(kokoro_instance, "phonemize"):
            try:
                phonemes = kokoro_instance.phonemize(text)
            except Exception:
                phonemes = None

        if duration > 0:
            if phonemes and isinstance(phonemes, str) and len(phonemes.strip()) > 0:
                # Map IPA characters directly to visemes
                ipa_map = {
                    "ɑ": "aa", "æ": "aa", "ʌ": "aa", "ɐ": "aa", "a": "aa",
                    "i": "ee", "ɪ": "ih", "e": "ee", "ɛ": "ee",
                    "o": "oh", "ɔ": "oh", "ɒ": "oh",
                    "u": "ou", "ʊ": "ou",
                    "s": "ih", "z": "ih", "t": "ih", "d": "ih", "n": "ih", "l": "ih",
                    "f": "ih", "v": "ih", "k": "aa", "g": "aa",
                }
                phone_tokens = [ch for ch in phonemes if ch in ipa_map]
                if phone_tokens:
                    step_t = duration / len(phone_tokens)
                    for idx, ch in enumerate(phone_tokens):
                        v = ipa_map.get(ch, "aa")
                        # Local RMS intensity weight
                        rms_idx = min(len(rms) - 1, int((idx * step_t) * 30)) if rms else 0
                        local_energy = rms[rms_idx] if rms else 0.75
                        weight = round(min(1.0, max(0.2, local_energy * 1.2)), 3)
                        visemes.append({
                            "time": round(idx * step_t, 3),
                            "duration": round(step_t * 0.9, 3),
                            "viseme": v,
                            "weight": weight,
                        })

            # Deterministic fallback when phonemes are unavailable
            if not visemes and words:
                vowels = ["aa", "ih", "ou", "ee", "oh"]
                step_t = duration / len(words)
                for idx, w in enumerate(words):
                    v = vowels[idx % len(vowels)]
                    for ch in w.lower():
                        if ch in "a":
                            v = "aa"
                            break
                        if ch in "ei":
                            v = "ee" if ch == "e" else "ih"
                            break
                        if ch in "o":
                            v = "oh"
                            break
                        if ch in "u":
                            v = "ou"
                            break
                    rms_idx = min(len(rms) - 1, int((idx * step_t) * 30)) if rms else 0
                    local_energy = rms[rms_idx] if rms else 0.75
                    visemes.append({
                        "time": round(idx * step_t, 3),
                        "duration": round(step_t * 0.85, 3),
                        "viseme": v,
                        "weight": round(min(1.0, max(0.3, local_energy * 1.1)), 3),
                    })

        # Encode 16-bit PCM WAV for remote character renderer lip-sync
        audio_b64 = None
        if len(arr) > 0:
            pcm16 = np.clip(arr * 32767.0, -32768, 32767).astype(np.int16)
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                wf.writeframes(pcm16.tobytes())
            audio_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

        return {
            "text": text,
            "sample_rate": sr,
            "duration": round(duration, 3),
            "rms": rms,
            "visemes": visemes,
            "audio_b64": audio_b64,
            "mime_type": "audio/wav",
        }

    def _broadcast_ui_state(self, state: str):
        try:
            if getattr(config, "ENABLE_DESKTOP_APP", True) or getattr(config, "CHARACTER_ENABLED", True):
                self._publish_bus_event("ui_state", state)
        except Exception:
            pass

    async def _synthesis_worker(self):
        """Background worker that pulls speech plans and synthesizes them asynchronously."""
        while True:
            try:
                item = await self._tts_queue.get()

                if item is None:  # Shutdown signal
                    break

                # Extract turn_id and payload
                if isinstance(item, tuple) and len(item) == 2:
                    turn_id, payload = item
                elif isinstance(item, SpeechPlan):
                    turn_id, payload = item.turn_id, item
                else:
                    turn_id, payload = self._current_turn_id, item

                # Discard stale queue items from previous/interrupted turns
                if turn_id != self._current_turn_id:
                    self._tts_queue.task_done()
                    continue

                if payload == "<END_OF_STREAM>":
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, self.player.wait_until_done)
                    if turn_id == self._current_turn_id:
                        self.is_speaking = False
                        self._publish_bus_event("speech_finished", {})
                        self._broadcast_ui_state("idle")
                        if self.hide_overlay:
                            self.hide_overlay()
                    self._tts_queue.task_done()
                    continue

                # Prepare speech plan
                if isinstance(payload, SpeechPlan):
                    plan = payload
                else:
                    # Raw string fallback (e.g. from tests or direct calls)
                    emotion, intensity, style, safety_locked = self._get_character_state()
                    plan = self.speech_planner.plan(
                        text=str(payload),
                        emotion=emotion,
                        intensity=intensity,
                        style=style,
                        safety_locked=safety_locked,
                    )
                    if plan is None:
                        self._tts_queue.task_done()
                        continue
                    plan.turn_id = turn_id

                if turn_id != self._current_turn_id:
                    self._tts_queue.task_done()
                    continue

                # Pre-speech pause for deliberate warning / natural cadence
                if plan.pause_before > 0:
                    await asyncio.sleep(plan.pause_before)
                    if turn_id != self._current_turn_id:
                        self._tts_queue.task_done()
                        continue

                self.is_speaking = True
                self._publish_bus_event("speech_started", {"text": plan.text})
                self._broadcast_ui_state("speaking")
                logger.info(f"Synthesizing: {plan.tts_text} (speed={plan.speed}, voice={plan.voice})")
                try:
                    print(f"[HELIOS]: {plan.text}")
                except Exception:
                    pass

                # Synthesize with KokoroTTS / backend
                async for raw_samples, sample_rate in self.tts.synthesize(
                    plan.tts_text,
                    voice=plan.voice,
                    speed=plan.speed,
                    is_phonemes=plan.is_phonemes,
                ):
                    # Check for mid-sentence interruption or turn invalidation
                    if not self.is_speaking or turn_id != self._current_turn_id:
                        logger.info("TTS Synthesis aborted mid-sentence due to interrupt.")
                        break

                    # Audio Processor Conditioning (DC removal, gentle highpass, compression, limiter)
                    samples = self.audio_processor.process(raw_samples, sample_rate)

                    # Send conditioned audio to hardware output stream
                    self.player.enqueue(samples, sample_rate)

                    # Compute enhanced lip-sync & viseme metadata and publish
                    try:
                        chunk_meta = self._compute_lip_sync_metadata(
                            samples, sample_rate, plan.text, kokoro_instance=self.kokoro
                        )
                        self._publish_bus_event("audio_chunk", chunk_meta)
                    except Exception as chunk_err:
                        logger.debug(f"Audio chunk metadata warning: {chunk_err}")

                # Post-speech pause
                if plan.pause_after > 0 and self.is_speaking and turn_id == self._current_turn_id:
                    await asyncio.sleep(plan.pause_after)

                self._tts_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in synthesis worker: {e}")

    def is_currently_speaking(self):
        return (
            (not self._tts_queue.empty())
            or (not self.player.audio_queue.empty())
            or (len(self._text_buffer) > 0)
            or self.is_speaking
        )

    def interrupt(self):
        """
        Barge-in: Stop speaking immediately.
        1. Cancels/terminates audio playback
        2. Increments turn ID so ongoing or queued synthesis is discarded
        3. Clears the TTS queue and text buffer
        4. Emits speech_interrupted so character stops mouth & speaking animation
        """
        logger.info("[VoiceManager] Interrupting current speech!")
        self._current_turn_id += 1
        self.is_speaking = False

        # Stop physical audio immediately
        self.player.stop()

        # Notify character addon & UI immediately
        self._publish_bus_event("speech_interrupted", {"reason": "barge_in"})
        self._broadcast_ui_state("idle")

        # Hide overlay if active
        if self.hide_overlay:
            self.hide_overlay()

        # Clear text buffer and filter state
        self._text_buffer = ""
        self.filter_state.reset()

        # Empty TTS queue
        while not self._tts_queue.empty():
            try:
                self._tts_queue.get_nowait()
                self._tts_queue.task_done()
            except asyncio.QueueEmpty:
                break
