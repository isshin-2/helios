import asyncio
import base64
import httpx
import json

from models.gemini_client import GeminiClient

async def main():
    base64_img = "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
    mime_type = "image/gif"
        
    messages = [
        {
            "role": "system",
            "content": "You are HELIOS, an expert."
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Is this image mostly empty space?"},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_img}"}}
            ]
        }
    ]
    
    gc = GeminiClient()
    payload = {
        "contents": gc._format_messages(messages),
        "systemInstruction": {
            "parts": [{"text": "You are HELIOS."}]
        },
        "tools": gc._format_tools([{"name": "test_tool", "description": "test", "inputSchema": {"type": "object", "properties": {}}}])
    }
    url = f"{gc.base_url}/gemini-3.6-flash:streamGenerateContent?alt=sse&key={gc.api_key}"
    print(f"Payload: {json.dumps(payload)}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
        print(f"Status: {res.status_code}")
        print(f"Response: {res.text}")

if __name__ == "__main__":
    asyncio.run(main())
