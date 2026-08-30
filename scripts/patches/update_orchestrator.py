import re, os

with open('core/orchestrator.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('self.tool_router = tool_router', 'self.tool_router = tool_router\n        self.cancellation_events = {}')

cancel_method = """
    def cancel_current_request(self, session_id: int):
        if session_id in self.cancellation_events:
            self.cancellation_events[session_id].set()
"""
content = content.replace('    async def _handle_tool_approval', cancel_method + '\n    async def _handle_tool_approval')

reset_event = """
        if session_id not in self.cancellation_events:
            self.cancellation_events[session_id] = asyncio.Event()
        self.cancellation_events[session_id].clear()
"""
content = content.replace('        if not messages or not user_id or not session_id:\n            return', '        if not messages or not user_id or not session_id:\n            return\n' + reset_event)

stream_check = r"""
                async for chunk in stream:
                    if self.cancellation_events[session_id].is_set():
                        await event_bus.publish("chunk", "\n\n[System: Generation stopped by user.]")
                        full_response += "\n\n[System: Generation stopped by user.]"
                        break
"""
content = content.replace('                async for chunk in stream:', stream_check)

outer_check = """
                if self.cancellation_events[session_id].is_set():
                    break
"""
content = content.replace('                if not tool_calls:', outer_check + '\n                if not tool_calls:')

with open('core/orchestrator.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated orchestrator.py")
