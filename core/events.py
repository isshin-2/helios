import asyncio
from typing import Callable, Dict, List, Any

class EventBus:
    """
    Lightweight asynchronous Event Bus for decoupling HELIOS components.
    Allows modules (like the Orchestrator) to publish events without tightly coupling to the WebSocket.
    """
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, callback: Callable):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)

    async def publish(self, event_type: str, data: Any = None):
        if event_type in self.subscribers:
            for callback in self.subscribers[event_type]:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
