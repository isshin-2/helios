import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

from config import OLLAMA_HOST, LLM_PROVIDER
from providers.ollama import OllamaProvider
from health.monitor import SystemMonitor
from models.manager import ModelManager
from router.memory import MemoryManager
from security.permissions import PermissionManager
from core.tool_router import ToolRouter
from core.orchestrator import ConversationOrchestrator
from core.events import EventBus

class PrintBus(EventBus):
    def __init__(self):
        super().__init__()
        self.events = []
        
    async def publish(self, event_type: str, data=None):
        self.events.append({"type": event_type, "data": data})
        if event_type == "chunk":
            print(data, end="", flush=True)
        elif event_type == "status":
            print(f"\n[STATUS] {data}")
        elif event_type == "meta":
            print(f"\n[META] model={data.get('model')} category={data.get('category')}")
        elif event_type == "error":
            print(f"\n[ERROR] {data}")
        await super().publish(event_type, data)

async def main():
    print(f"Connecting to provider with OLLAMA_HOST={OLLAMA_HOST}...")
    provider = OllamaProvider()
    monitor = SystemMonitor(provider=provider)
    manager = ModelManager(provider=provider, monitor=monitor)
    permission_manager = PermissionManager()
    tool_router = ToolRouter(provider=provider, monitor=monitor, permission_manager=permission_manager)
    memory_manager = MemoryManager(provider=provider)
    
    orchestrator = ConversationOrchestrator(
        manager, None, memory_manager, permission_manager, tool_router
    )
    
    bus = PrintBus()
    
    print("\n--- Submitting User Prompt: 'open calculator and type 1+1 and tell me the result' ---")
    messages = [{"role": "user", "content": "open calculator and type 1+1 and tell me the result"}]
    
    await orchestrator.process_request(
        session_id=999999,
        user_id=1,
        messages=messages,
        event_bus=bus,
        headless=True,
        agent_mode=False
    )
    
    print("\n\n--- COMPLETED ---")
    await provider.close()

if __name__ == "__main__":
    asyncio.run(main())
