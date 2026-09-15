import asyncio
from models.openai_client import OpenAICompatibleClient
from config import GROQ_API_KEY
import logging
logging.basicConfig(level=logging.DEBUG)

async def main():
    client = OpenAICompatibleClient("https://api.groq.com/openai/v1/chat/completions", GROQ_API_KEY)
    messages = [{"role": "user", "content": "hello"}]
    try:
        async for chunk in client.stream_chat(model="llama-3.3-70b-versatile", messages=messages):
            print(chunk)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(main())
