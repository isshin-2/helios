import asyncio
from providers.ollama import OllamaProvider
from health.monitor import SystemMonitor
import time

async def check():
    provider = OllamaProvider()
    monitor = SystemMonitor(provider)
    status = await monitor.get_full_status()
    print(status)
    await provider.close()

asyncio.run(check())
