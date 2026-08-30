import asyncio
import base64
import json
import websockets

async def test_vision():
    # 1x1 transparent GIF base64
    base64_img = "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
    mime_type = "image/gif"
        
    print("2. Connecting to HELIOS WebSocket...")
    uri = "ws://localhost:8000/ws"
    
    try:
        async with websockets.connect(uri) as websocket:
            
            payload = {
                "user_id": 1,
                "session_id": 9999,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Is this image mostly empty space?"},
                            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_img}"}}
                        ]
                    }
                ]
            }
            
            print("3. Sending Vision Request to HELIOS...")
            await websocket.send(json.dumps(payload))
            
            print("\n--- HELIOS RESPONSE STREAM ---")
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
    asyncio.run(test_vision())
