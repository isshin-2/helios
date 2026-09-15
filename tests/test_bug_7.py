import asyncio
import logging
from models.manager import ModelManager
from providers.ollama import OllamaProvider
from health.monitor import SystemMonitor

logging.basicConfig(level=logging.DEBUG)

async def test():
    provider = OllamaProvider()
    manager = ModelManager(provider, SystemMonitor(provider))
    messages = [{"role": "user", "content": "open whatsapp"}]
    tools = [{
        "type": "function",
        "function": {
            "name": "computer_control",
            "description": "Clicks on screen",
            "parameters": {
                "type": "object",
                "properties": { "action": { "type": "string" } }
            }
        }
    }]
    try:
        stream = await manager.execute_request("qwen2.5-coder:3b", messages, 4096, stream=True, tools=tools)
        async for chunk in stream:
            print(chunk)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"FAILED: {e}")
    
    await manager.provider.close()

asyncio.run(test())
