import asyncio
import base64
import httpx
import json

from models.gemini_client import GeminiClient

async def main():
    print("1. Downloading a sample image of a cat...")
    async with httpx.AsyncClient() as client:
        # Download a small public domain image of a cat
        res = await client.get("https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Cat03.jpg/320px-Cat03.jpg")
        image_data = res.content
        base64_img = base64.b64encode(image_data).decode('utf-8')
        mime_type = "image/jpeg"
        
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Can you describe what is in this image?"},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_img}"}}
            ]
        }
    ]
    
    gc = GeminiClient()
    print(f"Payload messages: {json.dumps(gc._format_messages(messages))[:500]}")
    
    try:
        async for chunk in gc.stream_chat(messages):
            print(chunk)
    except Exception as e:
        print(e)
        if hasattr(e, 'response'):
            await e.response.aread()
            print("ERROR BODY:", e.response.text)

if __name__ == "__main__":
    asyncio.run(main())
