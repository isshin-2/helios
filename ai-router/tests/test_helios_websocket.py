import asyncio
import json
import websockets
import sys

sys.stdout.reconfigure(encoding='utf-8')

async def test_helios_coding():
    uri = "ws://localhost:8000/ws"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to HELIOS.", flush=True)
            
            # Request to use coding tools
            request = {
                "messages": [
                    {"role": "user", "content": "Please write a simple python script in a file called 'test_script.py' that prints the sum of 5 and 7, and then execute that script and tell me the output. This is a test of your filesystem and shell tools."}
                ],
                "user_id": "test_user",
                "session_id": "test_session_coding",
                "agent_mode": True
            }
            
            await websocket.send(json.dumps(request))
            print("Sent request. Waiting for response...", flush=True)
            
            tools_called = set()
            
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                
                # Only print interesting chunks and statuses so we don't spam
                if data.get("type") == "chunk":
                    chunk = data.get("chunk", "")
                    sys.stdout.write(chunk)
                    sys.stdout.flush()
                    if '{"name":' in chunk:
                        try:
                            import re
                            match = re.search(r'{"name":\s*"([^"]+)"', chunk)
                            if match:
                                tools_called.add(match.group(1))
                        except:
                            pass
                            
                elif data.get("type") == "status":
                    print(f"\n[Status]: {data.get('text')}", flush=True)
                    if data.get("status") == "idle":
                        break
                        
                elif data.get("type") == "error":
                    print(f"\n[Error]: {data.get('message')}", flush=True)
                    break
                    
            print(f"\n\nTest completed. Tools called: {tools_called}", flush=True)
                    
    except Exception as e:
        print(f"Error: {e}", flush=True)

if __name__ == "__main__":
    asyncio.run(test_helios_coding())
