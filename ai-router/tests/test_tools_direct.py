import asyncio
import sys
import logging

# We will import the tools directly and execute them to prove HELIOS can use them
from tools.web_search import WebSearchTool
from tools.subagent import SubAgentTool

logging.basicConfig(level=logging.INFO)

async def test_tools():
    print("Testing WebSearchTool...", flush=True)
    web_tool = WebSearchTool()
    
    try:
        result, name = await web_tool.execute(user_id=1, query="current weather in Tokyo", max_results=2)
        print(f"\n[WebSearchTool Result]:\n{result}", flush=True)
    except Exception as e:
        print(f"WebSearchTool failed: {e}", flush=True)
        
    print("\n-------------------------------------------------\n", flush=True)
    
    print("Testing SubAgentTool...", flush=True)
    # Subagent doesn't actually use the provider argument deeply in execute, but we can pass a dummy
    sub_tool = SubAgentTool(provider=None)
    
    try:
        result, name = await sub_tool.execute(user_id=1, task="print 'hello from subagent'", budget=1)
        print(f"\n[SubAgentTool Result]:\n{result}", flush=True)
    except Exception as e:
        print(f"SubAgentTool failed: {e}", flush=True)

if __name__ == "__main__":
    asyncio.run(test_tools())
