import asyncio
import websockets
import json

async def send_to_helios():
    uri = "ws://127.0.0.1:8000/ws"
    try:
        async with websockets.connect(uri) as ws:
            payload = {
                "messages": [{"role": "user", "content": "Open instagram in opera gx (its already opend just navagate)\nthen open the current chat and send a message as helios"}],
                "user_id": 1,
                "session_id": 1,
                "agent_mode": True
            }
            await ws.send(json.dumps(payload))
            print("Sent prompt to local HELIOS.")
            
            while True:
                response = await ws.recv()
                data = json.loads(response)
                if data.get("type") == "chunk":
                    print(data.get("content", ""), end="", flush=True)
                elif data.get("type") == "done":
                    print("\n[Done]")
                    break
                elif data.get("type") == "status":
                    print(f"\n[Status] {data.get('text')}")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(send_to_helios())
