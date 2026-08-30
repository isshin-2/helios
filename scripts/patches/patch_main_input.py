import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Subscribe to input_request
sub = """
    event_bus.subscribe("input_request", lambda d: asyncio.create_task(ws_sender({"type": "input_request", **d})))
"""
content = content.replace('    event_bus.subscribe("approval_request"', sub + '    event_bus.subscribe("approval_request"')

# 2. Handle input_response
handle_input = """
            # Handle input responses
            if request_data.get("type") == "input_response":
                request_id = request_data.get("request_id")
                text = request_data.get("text", "")
                if request_id:
                    permission_manager.approval_manager.resolve_pending(
                        request_id, {"text": text}
                    )
                continue
"""
content = content.replace('            # Handle approval responses', handle_input + '\n            # Handle approval responses')

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated main.py for input")
