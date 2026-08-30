import asyncio
import httpx
import json

from models.gemini_client import GeminiClient

async def main():
    gc = GeminiClient()
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={gc.api_key}"
    
    async with httpx.AsyncClient() as client:
        res = await client.get(url)
        print(f"Status: {res.status_code}")
        try:
            data = res.json()
            models = [m['name'] for m in data.get('models', [])]
            print(f"Models: {models}")
        except Exception as e:
            print(f"Response: {res.text}")

if __name__ == "__main__":
    asyncio.run(main())
