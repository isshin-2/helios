import asyncio
from models.openai_client import OpenAICompatibleClient
from config import NVIDIA_API_KEY
import logging
logging.basicConfig(level=logging.DEBUG)

async def main():
    client = OpenAICompatibleClient("https://integrate.api.nvidia.com/v1/chat/completions", NVIDIA_API_KEY)
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
        resp = await client.chat(model="llama-3.1-nemotron-70b-instruct", messages=messages, tools=tools)
        print(resp)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(main())
