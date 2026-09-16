import sys
import os
import webview
import json

def get_user_input(question, options=None):
    # Load the Tensura HTML template
    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tensura style.txt")
    with open(html_path, "r", encoding="utf-8") as f:
        base_html = f.read()

    # Modify the HTML to include the question and options
    # We will inject a question div, and replace the controls with our options
    
    # CSS additions for the question and input field
    css_injection = """
    <style>
        .question-box {
            position: absolute;
            top: 20%;
            width: 80%;
            text-align: center;
            z-index: 50;
            font-size: 32px;
            font-weight: 700;
            color: #00e5ff;
            text-shadow: 0 0 10px rgba(0, 229, 255, 0.5);
        }
        .controls {
            margin-top: 50px; /* Adjust from 100px to fit input */
            flex-wrap: wrap;
            justify-content: center;
        }
        .controls button {
            font-size: 16px;
            padding: 12px 30px;
            border-color: #00e5ff;
            color: #00e5ff;
        }
        .controls button:hover {
            background: rgba(0, 229, 255, 0.2);
            box-shadow: 0 0 15px rgba(0, 229, 255, 0.5);
        }
        .custom-input-container {
            position: absolute;
            bottom: 15%;
            z-index: 50;
            display: flex;
            gap: 10px;
        }
        .custom-input {
            background: #0a1a2f;
            border: 1px solid #00e5ff;
            color: #00e5ff;
            padding: 10px 20px;
            font-size: 16px;
            font-family: 'Consolas', monospace;
            width: 300px;
            outline: none;
        }
        .custom-input:focus {
            box-shadow: 0 0 10px rgba(0, 229, 255, 0.3);
        }
    </style>
    """
    
    # Generate the buttons HTML
    buttons_html = ""
    if options:
        for opt in options:
            # We use pywebview api to send the result back
            buttons_html += f'<button onclick="pywebview.api.submit({opt})">{opt}</button>\n'
            
    # Input field HTML
    input_html = """
    <div class="custom-input-container">
        <input type="text" id="customInput" class="custom-input" placeholder="Or type response..." onkeypress="if(event.key === 'Enter') submitCustom()">
        <button onclick="submitCustom()">SUBMIT</button>
    </div>
    <script>
        function submitCustom() {
            var val = document.getElementById('customInput').value.trim();
            if(val) {
                pywebview.api.submit(val);
            }
        }
        // Force the state to speaking to look cool when asking a question
        window.onload = function() {
            setTimeout(() => setState('speaking'), 100);
        }
    </script>
    """
    
    # Inject into the HTML
    html = base_html.replace("</head>", css_injection + "</head>")
    
    question_html = f'<div class="question-box">{question}</div>'
    html = html.replace("<!-- UI Controls -->", question_html + "<!-- UI Controls -->")
    
    # Replace the controls div contents
    controls_start = html.find('<div class="controls">')
    if controls_start != -1:
        controls_end = html.find('</div>', controls_start) + 6
        html = html[:controls_start] + f'<div class="controls">{buttons_html}</div>{input_html}' + html[controls_end:]

    class Api:
        def __init__(self):
            self.result = None
            self.window = None
            
        def submit(self, choice):
            self.result = choice
            self.window.destroy()

    api = Api()
    
    # Create fullscreen borderless window
    window = webview.create_window(
        "HELIOS Notice", 
        html=html, 
        js_api=api,
        fullscreen=True,
        frameless=True,
        transparent=True,
        on_top=True
    )
    api.window = window
    
    # Esc to cancel
    def on_closed():
        pass
    window.events.closed += on_closed
    
    webview.start(gui="edgechromium") # use edgechromium on windows for best modern css support
    
    return api.result if api.result else "CANCELLED"

if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "Is this the correct Tensura design?"
    opts = sys.argv[2].split(",") if len(sys.argv) > 2 and sys.argv[2] else None
    
    ans = get_user_input(q, options=opts)
    print(ans)
