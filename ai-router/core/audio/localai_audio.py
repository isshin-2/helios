import httpx
import logging

logger = logging.getLogger(__name__)

class LocalAIAudio:
    def __init__(self, base_url="http://localhost:8080/v1"):
        self.base_url = base_url

    async def generate_tts(self, text: str, voice: str = "en-US") -> bytes:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/audio/speech",
                    json={"model": "tts-1", "input": text, "voice": voice}
                )
                response.raise_for_status()
                return response.content
        except Exception as e:
            logger.error(f"LocalAI TTS Error: {e}")
            return b""
            
    async def synthesize(self, text: str, voice: str = "en-US") -> bytes:
        return await self.generate_tts(text, voice)

    async def transcribe_stt(self, audio_file_path: str) -> str:
        try:
            async with httpx.AsyncClient() as client:
                with open(audio_file_path, "rb") as f:
                    response = await client.post(
                        f"{self.base_url}/audio/transcriptions",
                        data={"model": "whisper-1"},
                        files={"file": ("audio.wav", f, "audio/wav")}
                    )
                    response.raise_for_status()
                return response.json().get("text", "")
        except Exception as e:
            logger.error(f"LocalAI STT Error: {e}")
            return ""
