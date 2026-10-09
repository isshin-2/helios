import httpx
import json
import asyncio

async def test():
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post("http://127.0.0.1:11434/api/chat", json={
            "model": "qwen2.5-coder:3b",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant with access to tools."},
                {"role": "user", "content": "Take a screenshot using screen_vision."}
            ],
            "tools": [{
                "type": "function",
                "function": {
                    "name": "screen_vision",
                    "description": "Takes a screenshot of the screen.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "The question"}
                        },
                        "required": ["query"]
                    }
                }
            }],
            "stream": False
        })
        print(json.dumps(res.json(), indent=2))

asyncio.run(test())
