import asyncio
import json
import logging
import subprocess
import sys
import websockets

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Sidecar")

HELIOS_URL = "ws://localhost:8000/sidecar/ws"

DANGEROUS_COMMANDS = [
    "rm", "rmdir", "del", "format", "diskpart", 
    "shutdown", "restart", "poweroff", "init", "mkfs"
]

def is_safe_command(command: str) -> bool:
    # Basic safety check
    parts = command.lower().split()
    if not parts:
        return False
    # Check if the base command is dangerous
    if parts[0] in DANGEROUS_COMMANDS:
        return False
    # Check for dangerous flags
    for part in parts:
        if part in ["-rf", "/s", "/q"] and ("rm" in parts[0] or "del" in parts[0] or "rmdir" in parts[0]):
            return False
    return True

async def execute_command(command: str) -> dict:
    if not is_safe_command(command):
        logger.warning(f"Blocked dangerous command: {command}")
        return {"error": f"Command '{command}' is blocked by Sidecar safety policy."}
        
    logger.info(f"Executing: {command}")
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        output = stdout.decode('utf-8', errors='replace')
        err_output = stderr.decode('utf-8', errors='replace')
        
        full_output = output
        if err_output:
            full_output += f"\nSTDERR:\n{err_output}"
            
        return {"output": full_output}
    except Exception as e:
        logger.error(f"Execution error: {e}")
        return {"error": str(e)}

async def main():
    logger.info(f"Connecting to HELIOS Sidecar endpoint at {HELIOS_URL}...")
    while True:
        try:
            async with websockets.connect(HELIOS_URL) as websocket:
                logger.info("Connected securely to HELIOS.")
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)
                    req_id = data.get("request_id")
                    action = data.get("action")
                    payload = data.get("payload", {})
                    
                    if action == "run_command":
                        cmd = payload.get("command", "")
                        result = await execute_command(cmd)
                        
                        response = {
                            "request_id": req_id,
                            **result
                        }
                        await websocket.send(json.dumps(response))
                        
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Connection closed by HELIOS. Reconnecting in 5s...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Connection error: {e}. Retrying in 5s...")
            await asyncio.sleep(5)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Sidecar shutting down.")
