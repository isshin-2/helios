import httpx
import json
import asyncio

async def test():
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post("http://127.0.0.1:11434/api/chat", json={
            "model": "qwen2.5-coder:3b",
            "messages": [
                {"role": "system", "content": "ANTI-REFUSAL & TOOL AWARENESS:\nYou are an autonomous AI running locally on the user's machine. You have full permission and capability to control the computer, browse the web, and send messages on behalf of the user. Never refuse a request by saying you are an AI language model or cannot interact with devices. You must use your provided tools to fulfill the user's command.\n\n**VISION & CONTROL SYNERGY**:\nThe screen_vision and computer_control tools are designed to work together. \n1. Use screen_vision FIRST to \"see\" the screen and locate exactly where things are (buttons, chats, text boxes).\n2. Then, use computer_control (with x and y coordinates) to click on those locations or type text.\nDo not guess coordinates or assume you know what is on the screen without taking a screenshot first."},
                {"role": "user", "content": "view whats on my screen then open instagram and send a message to a user currently on the screen and chat as helios"}
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "screen_vision",
                        "description": "Takes a screenshot of the screen.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"}
                            }
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "computer_control",
                        "description": "Control computer.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "action": {"type": "string"},
                                "app_name": {"type": "string"}
                            }
                        }
                    }
                }
            ],
            "stream": False
        })
        print(json.dumps(res.json(), indent=2))

asyncio.run(test())
