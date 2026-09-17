import sys
import os
import webview
import json
import threading
import asyncio
import websockets

# Load the HTML
html_path = os.path.join(os.path.dirname(__file__), "static", "tensura_style.html")
with open(html_path, "r", encoding="utf-8") as f:
    base_html = f.read()

# Add a chat log box and tweak the input field
css_injection = """
<style>
    .chat-log {
        position: absolute;
        top: 10%;
        left: 5%;
        width: 400px;
        height: 60vh;
        overflow-y: auto;
        z-index: 50;
        display: flex;
        flex-direction: column;
        gap: 15px;
        font-family: 'Consolas', monospace;
    }
    .msg-user {
        align-self: flex-end;
        background: rgba(0, 229, 255, 0.1);
        border: 1px solid #00e5ff;
        padding: 10px;
        color: #00e5ff;
        border-radius: 10px 10px 0 10px;
        text-shadow: 0 0 5px rgba(0,229,255,0.5);
    }
    .msg-helios {
        align-self: flex-start;
        background: rgba(255, 204, 0, 0.1);
        border: 1px solid #FFCC00;
        padding: 10px;
        color: #FFCC00;
        border-radius: 10px 10px 10px 0;
        text-shadow: 0 0 5px rgba(255,204,0,0.5);
        max-width: 90%;
    }
    .custom-input-container {
        position: absolute;
        bottom: 10%;
        left: 50%;
        transform: translateX(-50%);
        z-index: 50;
        display: flex;
        gap: 10px;
    }
    .custom-input {
        background: #0a1a2f;
        border: 1px solid #00e5ff;
        color: #00e5ff;
        padding: 15px 25px;
        font-size: 18px;
        font-family: 'Consolas', monospace;
        width: 500px;
        outline: none;
        border-radius: 30px;
    }
    .custom-input:focus {
        box-shadow: 0 0 15px rgba(0, 229, 255, 0.5);
    }
    .btn-submit {
        background: transparent;
        border: 1px solid #00e5ff;
        color: #00e5ff;
        padding: 10px 20px;
        border-radius: 30px;
        cursor: pointer;
        font-weight: bold;
    }
    .btn-submit:hover {
        background: rgba(0, 229, 255, 0.2);
    }
</style>
"""

input_html = """
<div class="chat-log" id="chatLog"></div>
<div class="custom-input-container">
    <input type="text" id="customInput" class="custom-input" placeholder="Communicate with HELIOS..." onkeypress="if(event.key === 'Enter') submitChat()">
    <button class="btn-submit" onclick="submitChat()">SEND</button>
    <button class="btn-submit" onclick="pywebview.api.close_app()">EXIT</button>
</div>
<script>
    function submitChat() {
        var el = document.getElementById('customInput');
        var val = el.value.trim();
        if(val) {
            appendMessage(val, 'user');
            pywebview.api.send_message(val);
            el.value = '';
            setState('thinking');
        }
    }
    function appendMessage(text, sender) {
        var log = document.getElementById('chatLog');
        var div = document.createElement('div');
        div.className = sender === 'user' ? 'msg-user' : 'msg-helios';
        div.innerText = text;
        log.appendChild(div);
        log.scrollTop = log.scrollHeight;
    }
</script>
"""

html = base_html.replace("</head>", css_injection + "</head>")
html = html.replace('<div class="controls">', input_html + '\n<div class="controls">')

# We want the window to just run and look cool.
# Remove the debug buttons from the bottom
controls_start = html.find('<div class="controls">')
if controls_start != -1:
    controls_end = html.find('</div>', controls_start) + 6
    html = html[:controls_start] + html[controls_end:]

class DesktopApi:
    def __init__(self):
        import random
        self._window = None
        self._ws = None
        self._loop = asyncio.new_event_loop()
        self._current_message = ""
        self._messages = []
        self._session_id = random.randint(10000, 999999)
        threading.Thread(target=self.start_loop, daemon=True).start()

    def start_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self.connect_ws())

    def _safe_eval(self, js):
        if self._window:
            try:
                self._window.evaluate_js(js)
            except Exception as e:
                print(f"JS Eval Error: {e}")

    async def connect_ws(self):
        uri = "ws://localhost:8000/ws"
        try:
            async with websockets.connect(uri) as websocket:
                self._ws = websocket
                await websocket.send(json.dumps({"type": "init", "user_id": 1}))
                
                while True:
                    try:
                        msg = await websocket.recv()
                        data = json.loads(msg)
                        msg_type = data.get("type")
                        
                        if msg_type == "ui_state":
                            state = data.get("state")
                            self._safe_eval(f"setState('{state}');")
                        elif msg_type == "chunk":
                            self._current_message += data.get("content", "")
                        elif msg_type == "done":
                            if self._current_message:
                                safe_content = json.dumps(self._current_message)
                                self._safe_eval(f"appendMessage({safe_content}, 'helios');")
                                self._messages.append({"role": "assistant", "content": self._current_message})
                                self._current_message = ""
                            self._safe_eval("setState('idle');")
                        elif msg_type == "message":
                            # Full message received
                            content = data.get("content", "")
                            safe_content = json.dumps(content)
                            self._safe_eval(f"appendMessage({safe_content}, 'helios');")
                            self._messages.append({"role": "assistant", "content": content})
                    except Exception as loop_e:
                        print(f"WS Loop inner error: {loop_e}")
                        # Don't break the connection on parsing/rendering errors
                        pass
        except Exception as e:
            print(f"WS Error: {e}")
            self._safe_eval("appendMessage(`Failed to connect to backend on port 8000. Is HELIOS running?`, 'helios');")

    def send_message(self, text):
        if self._ws:
            self._messages.append({"role": "user", "content": text})
            payload = json.dumps({
                "type": "message", 
                "messages": self._messages,
                "user_id": 1,
                "session_id": self._session_id,
                "agent_mode": True
            })
            asyncio.run_coroutine_threadsafe(self._ws.send(payload), self._loop)
            
    def close_app(self):
        if self._window:
            self._window.destroy()

api = DesktopApi()

import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass
user32 = ctypes.windll.user32
screen_w = user32.GetSystemMetrics(0)
screen_h = user32.GetSystemMetrics(1)

print("Launching HELIOS Desktop App...")
window = webview.create_window(
    "HELIOS Main", 
    html=html, 
    js_api=api,
    width=screen_w,
    height=screen_h,
    x=0,
    y=0,
    frameless=True,
    transparent=True
)
api._window = window

webview.start(gui="edgechromium")
