import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from core.audio.voice_manager import VoiceManager
from core.audio.vad import SileroVAD

@pytest.fixture
def voice_manager():
    # Mock Kokoro and AudioPlayer
    with patch('core.audio.voice_manager.KokoroTTS'), \
         patch('core.audio.voice_manager.AudioPlayer'):
        vm = VoiceManager()
        yield vm

def test_voice_manager_sentence_buffering(voice_manager):
    """Test that chunks are buffered until a sentence boundary."""
    voice_manager._tts_queue = Mock()
    
    # Send partial sentence
    voice_manager._text_buffer = "This is a"
    voice_manager._process_buffer()
    assert voice_manager._tts_queue.put_nowait.call_count == 0
    
    # Complete the sentence
    voice_manager._text_buffer += " test. And another"
    voice_manager._process_buffer()
    
    # Should have queued "This is a test"
    assert voice_manager._tts_queue.put_nowait.call_count == 1
    voice_manager._tts_queue.put_nowait.assert_called_with("This is a test")
    
    # The remainder should be left in buffer
    assert voice_manager._text_buffer == " And another"

def test_voice_manager_interrupt(voice_manager):
    """Test that barge-in stops the player and clears the queue."""
    voice_manager._tts_queue = asyncio.Queue()
    voice_manager._tts_queue.put_nowait("Test sentence 1")
    voice_manager._tts_queue.put_nowait("Test sentence 2")
    voice_manager._text_buffer = "partial sentence"
    
    # Trigger barge-in
    voice_manager.interrupt()
    
    # Player should be stopped
    voice_manager.player.stop.assert_called_once()
    
    # Queue should be empty
    assert voice_manager._tts_queue.empty()
    
    # Text buffer should be cleared
    assert voice_manager._text_buffer == ""

def test_silero_vad_mocked():
    """Test the VAD logic using a mocked Torch hub."""
    with patch('torch.hub.load') as mock_load:
        # Mock the model output
        mock_model = Mock()
        mock_model.return_value.item.return_value = 0.8
        
        mock_utils = (Mock(), None, None, None, None)
        mock_load.return_value = (mock_model, mock_utils)
        
        vad = SileroVAD(threshold=0.5)
        
        # Test initialization
        assert vad.initialize() is True
        mock_load.assert_called_once()
        
        # Create a dummy 16-bit PCM chunk (512 samples)
        dummy_chunk = b'\x00\x00' * 512
        
        is_speech = vad.is_speech(dummy_chunk, frame_rate=16000, sample_width=2)
        
        assert is_speech is True
        mock_model.assert_called_once()
