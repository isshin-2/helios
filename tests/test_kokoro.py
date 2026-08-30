import asyncio
from kokoro_onnx import Kokoro
import inspect

async def main():
    kokoro = Kokoro(".models/kokoro/kokoro-v0_19.onnx", ".models/kokoro/voices.bin")
    print("create_stream type:", type(kokoro.create_stream))
    print("is_asyncgenfunction:", inspect.isasyncgenfunction(kokoro.create_stream))
    
    stream = kokoro.create_stream("Hello world", voice="af_heart")
    print("stream type:", type(stream))

asyncio.run(main())
