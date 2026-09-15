import asyncio
from core.events import EventBus, global_bus, CancellationToken

import pytest

@pytest.mark.asyncio
async def test_event_bus():
    bus = EventBus()
    events_received = []
    
    def sync_sub(data):
        events_received.append(("sync", data))
        
    async def async_sub(data):
        events_received.append(("async", data))
        
    bus.subscribe("test", sync_sub)
    bus.subscribe("test", async_sub)
    
    await bus.publish("test", "hello")
    await asyncio.sleep(0.1) # Let async task run
    
    assert len(events_received) == 2
    assert ("sync", "hello") in events_received
    assert ("async", "hello") in events_received
    
    # Test Cancellation
    token = global_bus.get_token("123")
    assert not token.is_cancelled
    global_bus.cancel_session("123")
    assert token.is_cancelled
    
    print("ALL TESTS PASSED")

if __name__ == '__main__':
    asyncio.run(test_event_bus())
