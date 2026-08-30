import re

with open('static/app.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Add HTML for stop button
stop_btn_html = """        <div id="input-container">
            <div style="display: flex; justify-content: center; margin-bottom: 8px;">
                <button id="stop-btn" class="btn btn-secondary" style="display: none; padding: 6px 16px; border-radius: 20px; font-size: 13px; background: var(--bg-card); align-items: center; cursor: pointer;">
                    <svg viewBox="0 0 24 24" style="width: 14px; height: 14px; margin-right: 6px; fill: currentColor;"><path d="M6 6h12v12H6z"/></svg>
                    Stop Generating
                </button>
            </div>"""
html = html.replace('        <div id="input-container">', stop_btn_html)

# 2. Add Stop button DOM element
html = html.replace("const sendBtn = document.getElementById('send-btn');", 
                    "const sendBtn = document.getElementById('send-btn');\n        const stopBtn = document.getElementById('stop-btn');")

# 3. Add to sendPrompt
html = html.replace("chatContainer.appendChild(loadingCardElement);", 
                    "chatContainer.appendChild(loadingCardElement);\n            stopBtn.style.display = 'flex';")

# 4. Hide stop button on 'done'
html = html.replace("else if (data.type === 'done') {", 
                    "else if (data.type === 'done') {\n                    stopBtn.style.display = 'none';")

# 5. Add Stop button event listener
stop_listener = """
        stopBtn.addEventListener('click', () => {
            if (ws && ws.readyState === WebSocket.OPEN && currentSessionId) {
                ws.send(JSON.stringify({ type: 'stop', session_id: currentSessionId }));
                stopBtn.style.display = 'none';
                if (loadingCardElement) loadingCardElement.remove();
            }
        });
"""
html = html.replace("sendBtn.addEventListener('click', sendPrompt);", 
                    stop_listener + "\n        sendBtn.addEventListener('click', sendPrompt);")

with open('static/app.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Updated app.html")
