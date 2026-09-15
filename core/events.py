import asyncio
from typing import Callable, Dict, List, Any
import logging

logger = logging.getLogger(__name__)

class CancellationToken:
    def __init__(self):
        self._is_cancelled = False
        self._event = asyncio.Event()

    def cancel(self):
        self._is_cancelled = True
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._is_cancelled

    async def wait_for_cancel(self):
        await self._event.wait()

class EventBus:
    """
    Robust Event Bus for HELIOS Agent Platform.
    Supports standard pub/sub, strict cancellation propagation, and safe execution.
    """
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.session_tokens: Dict[str, CancellationToken] = {}

    def get_token(self, session_id: str) -> CancellationToken:
        """Get or create a cancellation token for a specific execution session."""
        session_id = str(session_id)
        if session_id not in self.session_tokens:
            self.session_tokens[session_id] = CancellationToken()
        return self.session_tokens[session_id]

    def cancel_session(self, session_id: str):
        """Signal a cancellation for a specific session."""
        session_id = str(session_id)
        if session_id in self.session_tokens:
            self.session_tokens[session_id].cancel()
            logger.info(f"Session {session_id} cancelled via EventBus.")
            asyncio.create_task(self.publish(f"cancel_{session_id}"))

    def clear_session(self, session_id: str):
        """Clean up session tracking once execution is completely terminated."""
        session_id = str(session_id)
        if session_id in self.session_tokens:
            del self.session_tokens[session_id]

    def subscribe(self, event_type: str, callback: Callable):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        if callback not in self.subscribers[event_type]:
            self.subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable):
        if event_type in self.subscribers and callback in self.subscribers[event_type]:
            self.subscribers[event_type].remove(callback)

    async def publish(self, event_type: str, data: Any = None):
        """
        Publish an event to all subscribers asynchronously.
        Catches subscriber exceptions to guarantee bus stability.
        """
        if event_type in self.subscribers:
            tasks = []
            for callback in self.subscribers[event_type]:
                if asyncio.iscoroutinefunction(callback):
                    tasks.append(asyncio.create_task(self._safe_execute_async(callback, data)))
                else:
                    self._safe_execute_sync(callback, data)
            
            if tasks:
                await asyncio.gather(*tasks)

    async def _safe_execute_async(self, callback: Callable, data: Any):
        try:
            await callback(data)
        except Exception as e:
            logger.error(f"EventBus Async Subscriber Error on {callback.__name__}: {e}")

    def _safe_execute_sync(self, callback: Callable, data: Any):
        try:
            callback(data)
        except Exception as e:
            logger.error(f"EventBus Sync Subscriber Error on {callback.__name__}: {e}")

# Global system event bus (useful for cross-cutting concerns like cancellation)
global_bus = EventBus()
