import asyncio
import websockets
import json

async def test_ws():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        print("Connected to WebSocket.")
        
        request_data = {
            "messages": [{"role": "user", "content": "hello"}],
            "user_id": 1,
            "session_id": 1
        }
        await websocket.send(json.dumps(request_data))
        print("Sent message.")
        
        # Read the first few messages
        for _ in range(5):
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"Received: {response}")
                
                data = json.loads(response)
                if data.get("type") == "done":
                    break
            except asyncio.TimeoutError:
                print("Timeout waiting for response")
                break

if __name__ == "__main__":
    asyncio.run(test_ws())
