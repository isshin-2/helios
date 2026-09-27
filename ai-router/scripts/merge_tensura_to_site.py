import re

with open('static/AI-Core-System.html', 'r', encoding='utf-8') as f:
    tensura = f.read()

with open('static/app.html', 'r', encoding='utf-8') as f:
    app_html = f.read()

# 1. Extract CSS
style_match = re.search(r'<style>(.*?)</style>', tensura, re.DOTALL)
tensura_css = style_match.group(1) if style_match else ""

# Remove body/html global overrides from tensura CSS to avoid breaking the site
tensura_css = re.sub(r'body, html\s*{[^}]+}', '', tensura_css)
tensura_css = re.sub(r'body\s*{[^}]+}', '', tensura_css)

# 2. Extract AI Section (No Menu)
body_match = re.search(r'<div class="ai-section">.*?</div>\s*<!-- RIGHT MENU PANEL', tensura, re.DOTALL)
if body_match:
    tensura_dom = body_match.group(0).replace('<!-- RIGHT MENU PANEL', '')
else:
    tensura_dom = ""

# 3. Extract JS functions
js_match = re.search(r'function setAIState.*?}', tensura, re.DOTALL)
tensura_js = js_match.group(0) if js_match else ""
# Make sure setAIState is safe if statusText is missing
tensura_js = tensura_js.replace(
    "document.getElementById('statusText').innerText = state;",
    "let statusEl = document.getElementById('statusText'); if(statusEl) statusEl.innerText = state;"
)

# 4. Inject CSS into app.html (ONLY AT THE FIRST </style>)
app_html = app_html.replace('</style>', f'\n/* TENSURA CSS */\n{tensura_css}\n</style>', 1)

# 5. Inject DOM into app.html inside #main, just before #chat-container
tensura_wrapper = f"""
    <div id="tensura-bg" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%) scale(0.65); pointer-events: none; opacity: 0.15; z-index: 0; display: flex; justify-content: center; align-items: center; width: 540px; height: 540px;">
        <div class="widget-container" style="border: none; box-shadow: none; background: transparent;">
            <div class="widget-rotator" style="pointer-events: none;">
                {tensura_dom}
            </div>
        </div>
    </div>
"""
if 'id="tensura-bg"' not in app_html:
    app_html = app_html.replace('<div id="chat-container"', f'{tensura_wrapper}\n        <div id="chat-container"', 1)

# 6. Inject JS state changes
if 'function setAIState' not in app_html:
    app_html = app_html.replace('<script>', f'<script>\n        {tensura_js}\n', 1)

# 7. Hook into websocket to change states
# In app.html, when user sends message, set 'thinking'
app_html = app_html.replace('ws.send(JSON.stringify({', 'document.body.classList.add("state-thinking"); document.body.classList.remove("state-idle", "state-speaking", "state-listening", "state-menu", "state-error");\n                    ws.send(JSON.stringify({')
app_html = app_html.replace('ws.send(JSON.stringify(payload));', 'document.body.classList.add("state-thinking"); document.body.classList.remove("state-idle", "state-speaking", "state-listening", "state-menu", "state-error");\n                    ws.send(JSON.stringify(payload));')

# When receiving message chunk, set 'speaking'
if 'state-speaking' not in app_html:
    app_html = app_html.replace('if (msg.event === "chunk") {', 'if (msg.event === "chunk") {\n                document.body.classList.add("state-speaking"); document.body.classList.remove("state-thinking");')

# When finished (status idle), set 'idle'
if 'state-idle' not in app_html:
    app_html = app_html.replace('if (msg.event === "status" && msg.status === "idle") {', 'if (msg.event === "status" && msg.status === "idle") {\n                document.body.classList.add("state-idle"); document.body.classList.remove("state-speaking", "state-thinking");')

with open('static/app.html', 'w', encoding='utf-8') as f:
    f.write(app_html)

print("Injected Tensura Widget into app.html cleanly!")
