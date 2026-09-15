import asyncio
from core.orchestrator import ConversationOrchestrator

async def test():
    orc = ConversationOrchestrator()
    class DummyBus:
        async def publish(self, event, data):
            print(f"[{event}] {data}")
    
    await orc.process_request("test_session", 1, [{"role": "user", "content": "open whatsapp"}], DummyBus(), headless=True, agent_mode=True)

asyncio.run(test())
