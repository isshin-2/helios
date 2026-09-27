import asyncio
import time
from providers.ollama import OllamaProvider
from core.tool_router import ToolRouter
from security.permissions import PermissionManager
from health.monitor import SystemMonitor

async def run_tool_benchmarks():
    print("Running Tool Calling Benchmarks on qwen3:8b...")
    
    provider = OllamaProvider(host="http://127.0.0.1:11434")
    monitor = SystemMonitor(provider)
    pm = PermissionManager()
    
    # We need a tool schema
    tool_router = ToolRouter(provider, monitor, pm)
    tool_schemas = tool_router.get_tool_schemas()
    
    messages = [
        {"role": "user", "content": "What files are in the HELIOS directory?"}
    ]
    
    start = time.time()
    
    try:
        response = await provider.chat(
            model="qwen3:8b",
            messages=messages,
            options={"num_ctx": 4096},
            tools=tool_schemas,
            stream=False
        )
        
        end = time.time()
        
        print("Response received:")
        print(f"Latency: {(end - start):.2f}s")
        
        if "message" in response:
            msg = response["message"]
            print(f"Content: {msg.get('content')}")
            if "tool_calls" in msg and msg["tool_calls"]:
                print("Tool Calls detected!")
                for tc in msg["tool_calls"]:
                    print(f"  - {tc}")
            else:
                print("No tool calls generated.")
        else:
            print("Unexpected response format.")
            print(response)
            
    except Exception as e:
        print(f"Failed to benchmark: {e}")

if __name__ == "__main__":
    asyncio.run(run_tool_benchmarks())
