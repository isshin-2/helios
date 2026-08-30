import asyncio
import base64
import json
import io
import websockets
from PIL import ImageGrab

async def test_screen_vision():
    print("1. Capturing current screen...")
    screenshot = ImageGrab.grab()
    
    # Resize screen slightly if it's too large to save bandwidth
    screenshot.thumbnail((1920, 1080))
    
    buffered = io.BytesIO()
    screenshot.save(buffered, format="JPEG", quality=80)
    base64_img = base64.b64encode(buffered.getvalue()).decode("utf-8")
    mime_type = "image/jpeg"
        
    print("2. Connecting to HELIOS WebSocket...")
    uri = "ws://localhost:8000/ws"
    
    try:
        async with websockets.connect(uri, max_size=10*1024*1024) as websocket:
            
            payload = {
                "user_id": 1,
                "session_id": 9999,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "What do you see on my screen right now? Describe it in detail."},
                            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_img}"}}
                        ]
                    }
                ]
            }
            
            print("3. Sending Screen Request to HELIOS...")
            await websocket.send(json.dumps(payload))
            
            print("\n--- HELIOS RESPONSE STREAM ---\n")
            while True:
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=60.0)
                    data = json.loads(msg)
                    
                    if data.get("type") == "chunk":
                        print(data.get("content", ""), end="", flush=True)
                    elif data.get("type") == "done":
                        print("\n\n--- STREAM COMPLETE ---")
                        break
                    elif data.get("type") == "error":
                        print(f"\n[ERROR] {data.get('message')}")
                        break
                except asyncio.TimeoutError:
                    print("\n[TIMEOUT] Waiting for response.")
                    break
    except ConnectionRefusedError:
        print("Error: HELIOS server is not running on port 8000. Start it with start.bat first.")

if __name__ == "__main__":
    asyncio.run(test_screen_vision())
