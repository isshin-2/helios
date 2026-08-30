import asyncio
from core.orchestrator import ConversationOrchestrator
from providers.ollama import OllamaProvider
from models.manager import ModelManager
from health.monitor import SystemMonitor
from router.memory import MemoryManager
from core.events import EventBus

async def main():
    provider = OllamaProvider()
    monitor = SystemMonitor(provider)
    manager = ModelManager(provider, monitor)
    memory = MemoryManager(provider)
    orch = ConversationOrchestrator(manager, None, memory, None, None)
    
    event_bus = EventBus()
    print("Testing router...")
    gen = await orch.process_request('test-session', 'user-1', [{'role': 'user', 'content': 'test'}], event_bus)
    async for chunk in gen:
        print(chunk)
        
if __name__ == "__main__":
    asyncio.run(main())
