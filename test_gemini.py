import asyncio
from models.gemini_client import GeminiClient
import logging
logging.basicConfig(level=logging.DEBUG)

async def main():
    client = GeminiClient()
    tools = [{
        "type": "function",
        "function": {
            "name": "manage_accounts",
            "description": "Manage Google accounts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string"}
                }
            }
        }
    }]
    messages = [{"role": "user", "content": "hello"}]
    try:
        resp = await client.chat(model="gemini-1.5-pro", messages=messages, tools=tools)
        print(resp)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(main())
