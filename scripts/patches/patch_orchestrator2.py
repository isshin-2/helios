import re

with open('core/orchestrator.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add _handle_user_input
handle_input_method = """
    async def _handle_user_input(self, question: str, event_bus: EventBus) -> str:
        request_id = self.permission_manager.approval_manager.generate_request_id()
        import asyncio
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self.permission_manager.approval_manager.register_pending(request_id, future)
        
        await event_bus.publish("input_request", {
            "request_id": request_id,
            "question": question
        })
        
        try:
            # Wait a long time for the user to answer
            response = await asyncio.wait_for(future, timeout=300.0)
            return response.get("text", "")
        except asyncio.TimeoutError:
            return "User did not respond in time."
        except Exception as e:
            return f"Error waiting for input: {e}"
"""
content = content.replace('    async def _handle_tool_approval', handle_input_method + '\n    async def _handle_tool_approval')

# 2. Intercept INPUT_REQUIRED
interceptor = """
                    if res_text.startswith("INPUT_REQUIRED::"):
                        parts = res_text.split("::", 1)
                        question = parts[1] if len(parts) > 1 else "Please provide input:"
                        user_reply = await self._handle_user_input(question, event_bus)
                        res_text = f"User responded: {user_reply}"
"""
content = content.replace('                    if res_text.startswith("APPROVAL_REQUIRED::"):', interceptor + '\n                    if res_text.startswith("APPROVAL_REQUIRED::"):')

with open('core/orchestrator.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated orchestrator.py for INPUT_REQUIRED")
