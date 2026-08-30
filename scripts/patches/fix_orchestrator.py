import re

with open("core/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. 404 Fix
content = content.replace("            except Exception as e:", """            except Exception as e:
                import httpx
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
                    fallback = config.MODEL_CONFIG.get("fallback")
                    if fallback and fallback != model_name:
                        logger.warning(f"Model {model_name} not found. Retrying with fallback {fallback}.")
                        route["model"] = fallback
                        continue""")

# 2. Add full_response fix
full_response_fix = """                    import json
                    messages.append({
                        "role": "tool",
                        "content": json.dumps(structured_result)
                    })
                    
                    # Ensure tool outputs are saved in the session history and displayed seamlessly
                    formatted_tool_output = f"\\n\\n[Tool Executed: {function_name}]\\n{res_text}\\n\\n"
                    full_response += formatted_tool_output
                    await event_bus.publish("chunk", formatted_tool_output)"""
content = content.replace("""                    import json
                    messages.append({
                        "role": "tool",
                        "content": json.dumps(structured_result)
                    })""", full_response_fix)

# 3. Add cancellation variables
content = content.replace('self.tool_router = tool_router', 'self.tool_router = tool_router\n        self.cancellation_events = {}')

# 4. Add cancel_current_request
cancel_method = """
    def cancel_current_request(self, session_id: int):
        if session_id in self.cancellation_events:
            self.cancellation_events[session_id].set()
"""
content = content.replace('    async def _handle_tool_approval', cancel_method + '\n    async def _handle_tool_approval')

# 5. Handle user input
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

# 6. Initialize event on process_request
reset_event = """
        if session_id not in self.cancellation_events:
            import asyncio
            self.cancellation_events[session_id] = asyncio.Event()
        self.cancellation_events[session_id].clear()
"""
content = content.replace('        if not messages or not user_id or not session_id:\n            return', '        if not messages or not user_id or not session_id:\n            return\n' + reset_event)

# 7. Check cancellation in streaming loop
stream_check = r"""
                async for chunk in stream:
                    if self.cancellation_events[session_id].is_set():
                        await event_bus.publish("chunk", "\n\n[System: Generation stopped by user.]")
                        full_response += "\n\n[System: Generation stopped by user.]"
                        break
"""
content = content.replace('                async for chunk in stream:', stream_check)

# 8. Check cancellation outer
outer_check = """
                if self.cancellation_events[session_id].is_set():
                    break
"""
content = content.replace('                if not tool_calls:', outer_check + '\n                if not tool_calls:')

# 9. Inject INPUT_REQUIRED interceptor properly indented
interceptor = """
                            if res_text.startswith("INPUT_REQUIRED::"):
                                parts = res_text.split("::", 1)
                                question = parts[1] if len(parts) > 1 else "Please provide input:"
                                user_reply = await self._handle_user_input(question, event_bus)
                                res_text = f"User responded: {user_reply}"
"""
content = content.replace('                            if res_text.startswith("APPROVAL_REQUIRED::"):', interceptor + '\n                            if res_text.startswith("APPROVAL_REQUIRED::"):')

with open("core/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated orchestrator")
