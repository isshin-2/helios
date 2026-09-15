import asyncio
import os
import config
from google import genai

async def main():
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    print("Has aio?:", hasattr(client, 'aio'))
    if hasattr(client, 'aio'):
        print("Has aio.models?:", hasattr(client.aio, 'models'))
    print("Has models?:", hasattr(client, 'models'))
    
asyncio.run(main())
