import asyncio
import os
import sys

from core.audio.voice_manager import VoiceManager
from core.audio.tts.manager import TTSBackendManager

async def test():
    mgr = TTSBackendManager()
    ready = mgr.initialize()
    print("TTS Manager Initialized Status:", ready)
    print("Active Backend:", mgr._active_backend_name)
    print("Residency:", mgr.residency_state)
    print("GPT-SoVITS Status:", mgr.gpt_sovits.get_status())
    
    text = "Hello Krithik! I am Airi, running live on your dedicated NVIDIA RTX 5060 Ti workstation."
    print("Synthesizing speech for Airi:", text)
    chunks = []
    async for audio, sr in mgr.synthesize(text, voice="airi", speed=1.05):
        chunks.append((audio, sr))
    print(f"Synthesis complete! Generated {len(chunks)} audio segments.")

if __name__ == "__main__":
    asyncio.run(test())
