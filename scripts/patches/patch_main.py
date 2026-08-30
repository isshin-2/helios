import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace legacy voice import and endpoints
old_voice_code = """try:
    from voice.assistant import VoiceAssistant
    voice_assistant = VoiceAssistant()
except ImportError:
    voice_assistant = None
    logger.warning("Voice module could not be loaded. Voice features disabled.")

@app.on_event("startup")
async def startup_event():
    if voice_assistant:
        voice_assistant.start()
        logger.info("Voice assistant auto-started on server startup.")

@app.post("/api/voice/start")
async def start_voice():
    if not voice_assistant:
        raise HTTPException(status_code=501, detail="Voice features are not available.")
    voice_assistant.start()
    return {"status": "success", "message": "Voice assistant started."}

@app.post("/api/voice/stop")
async def stop_voice():
    if not voice_assistant:
        raise HTTPException(status_code=501, detail="Voice features are not available.")
    voice_assistant.stop()
    return {"status": "success", "message": "Voice assistant stopped."}

@app.post("/api/voice/trigger")
async def trigger_voice():
    if not voice_assistant:
        raise HTTPException(status_code=501, detail="Voice features are not available.")
    if not voice_assistant.is_running:
        raise HTTPException(status_code=400, detail="Voice assistant is not running. Please start it first.")
    voice_assistant.trigger()
    return {"status": "success", "message": "Voice assistant triggered for one command."}"""

new_voice_code = """from core.audio.voice_manager import VoiceManager
from core.audio.stt.google import VoiceInput
from config import VOICE_ENABLED

voice_manager = VoiceManager()
voice_input = VoiceInput(voice_manager)

@app.on_event("startup")
async def startup_event():
    if VOICE_ENABLED:
        voice_input.start()
        logger.info("Voice input auto-started on server startup.")

@app.post("/api/voice/start")
async def start_voice():
    voice_input.start()
    return {"status": "success", "message": "Voice assistant started."}

@app.post("/api/voice/stop")
async def stop_voice():
    voice_input.stop()
    return {"status": "success", "message": "Voice assistant stopped."}
"""

content = content.replace(old_voice_code, new_voice_code)

# Add event_bus subscriptions in headless API
old_headless = """    # Custom EventBus to capture events synchronously-ish for the HTTP response
    class CaptureEventBus(EventBus):
        def __init__(self):
            super().__init__()
            self.events = []
            
        async def publish(self, event_type: str, data: Any = None):
            self.events.append({"type": event_type, "data": data})
            await super().publish(event_type, data)
            
    bus = CaptureEventBus()"""

new_headless = """    # Custom EventBus to capture events synchronously-ish for the HTTP response
    class CaptureEventBus(EventBus):
        def __init__(self):
            super().__init__()
            self.events = []
            
        async def publish(self, event_type: str, data: Any = None):
            self.events.append({"type": event_type, "data": data})
            await super().publish(event_type, data)
            
    bus = CaptureEventBus()
    if VOICE_ENABLED:
        bus.subscribe("chunk", voice_manager._on_chunk)
        bus.subscribe("done", voice_manager._on_done)
        bus.subscribe("status", voice_manager._on_status)"""

content = content.replace(old_headless, new_headless)

# Add event_bus subscriptions in websocket
old_ws = """    # Subscribe websocket sender to all event types
    event_bus.subscribe("status", lambda d: asyncio.create_task(ws_sender({"type": "status", "text": d})))
    event_bus.subscribe("chunk", lambda d: asyncio.create_task(ws_sender({"type": "chunk", "content": d})))
    event_bus.subscribe("meta", lambda d: asyncio.create_task(ws_sender({"type": "meta", **d})))"""

new_ws = """    # Subscribe websocket sender to all event types
    event_bus.subscribe("status", lambda d: asyncio.create_task(ws_sender({"type": "status", "text": d})))
    event_bus.subscribe("chunk", lambda d: asyncio.create_task(ws_sender({"type": "chunk", "content": d})))
    event_bus.subscribe("meta", lambda d: asyncio.create_task(ws_sender({"type": "meta", **d})))
    
    if getattr(voice_manager, "_on_chunk", None):
        try:
            from config import VOICE_ENABLED
            if VOICE_ENABLED:
                event_bus.subscribe("chunk", voice_manager._on_chunk)
                event_bus.subscribe("done", voice_manager._on_done)
                event_bus.subscribe("status", voice_manager._on_status)
        except Exception:
            pass"""

content = content.replace(old_ws, new_ws)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched main.py")
