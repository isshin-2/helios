import asyncio
import websockets
import json

async def run_test():
    uri = "ws://127.0.0.1:8000/ws"
    async with websockets.connect(uri) as websocket:
        msg = {
            "type": "chat",
            "message": "view whats on my screen then open instagram and send a message to a user currently on the screen and chat as helios",
            "agent_mode": True
        }
        await websocket.send(json.dumps(msg))
        
        while True:
            try:
                response = await websocket.recv()
                print(response)
                if "[Done]" in response or "System Error" in response or "Warning" in response:
                    break
            except websockets.exceptions.ConnectionClosed:
                print("Connection closed")
                break

asyncio.run(run_test())
