import sys
import os
import webview
import json
import threading
import asyncio
import websockets

# Load the HTML
html_path = os.path.join(os.path.dirname(__file__), "tensura style.txt")
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
html = html.replace("<!-- UI Controls -->", input_html)

# We want the window to just run and look cool.
# Remove the debug buttons from the bottom
controls_start = html.find('<div class="controls">')
if controls_start != -1:
    controls_end = html.find('</div>', controls_start) + 6
    html = html[:controls_start] + html[controls_end:]

class DesktopApi:
    def __init__(self):
        self.window = None
        self.ws = None
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.start_loop, daemon=True).start()

    def start_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.connect_ws())

    async def connect_ws(self):
        uri = "ws://localhost:8000/ws"
        try:
            async with websockets.connect(uri) as websocket:
                self.ws = websocket
                await websocket.send(json.dumps({"type": "init", "user_id": 1}))
                
                while True:
                    msg = await websocket.recv()
                    data = json.loads(msg)
                    if data.get("type") == "token":
                        # streaming token
                        pass
                    elif data.get("type") == "message":
                        # Full message received
                        content = data.get("content", "")
                        self.window.evaluate_js(f"appendMessage({content.replace('', '')}, 'helios');")
                        self.window.evaluate_js("setState('speaking');")
                        await asyncio.sleep(2)
                        self.window.evaluate_js("setState('listening');")
        except Exception as e:
            print(f"WS Error: {e}")
            if self.window:
                self.window.evaluate_js("appendMessage(`Failed to connect to backend on port 8000. Is HELIOS running?`, 'helios');")

    def send_message(self, text):
        if self.ws:
            payload = json.dumps({"type": "message", "content": text})
            asyncio.run_coroutine_threadsafe(self.ws.send(payload), self.loop)
            
    def close_app(self):
        if self.window:
            self.window.destroy()

api = DesktopApi()

print("Launching HELIOS Desktop App...")
window = webview.create_window(
    "HELIOS Main", 
    html=html, 
    js_api=api,
    fullscreen=True,
    frameless=True,
    transparent=True,
    on_top=True
)
api.window = window

webview.start(gui="edgechromium")
