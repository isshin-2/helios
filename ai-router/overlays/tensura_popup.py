import sys
import os
import webview
import json
import time
import threading

def get_user_input(question, options=None):
    # Load the Tensura HTML template
    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "tensura_style.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    class Api:
        def __init__(self):
            self.result = None
            self.window = None
            
        def submit(self, choice):
            self.result = choice
            try:
                self.window.destroy()
            except Exception:
                pass
            # Force successful exit if pywebview hangs on destroy
            os._exit(0)

    api = Api()
    
    # Use system metrics to place it in the bottom right corner
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    try:
        user32 = ctypes.windll.user32
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
    except:
        screen_w = 1920
        screen_h = 1080
        
    # Generate options HTML
    options_js = ""
    is_demo = (question == "demo")
    q_text = "Demo Mode: Question Layout" if is_demo else question
    
    if options:
        for opt in options:
            options_js += f"addOption({json.dumps(opt)});\n"
    else:
        options_js += "addTextInput();\n"

    # Inject initialization script into HTML
    init_script = f"""
    <script>
        window.onload = function() {{
            setQuestion({json.dumps(q_text)});
            {options_js}
            
            // Start the sequence
            setTimeout(() => {{
                setAIState('listening');
            }}, 500);
            
            setTimeout(() => {{
                toggleLayoutMode(true);
            }}, 1000);
            
            // If demo mode, handle loop
            if ({str(is_demo).lower()}) {{
                const states = ['idle', 'listening', 'thinking', 'speaking'];
                let i = 0;
                setInterval(() => {{
                    setAIState(states[i % states.length]);
                    i++;
                }}, 5000);
            }}
        }};
    </script>
    """
    html = html.replace("</body>", init_script + "</body>")

    window = webview.create_window(
        'HELIOS - Question',
        html=html,
        js_api=api,
        transparent=True,
        frameless=True,
        width=screen_w,
        height=screen_h,
        x=0,
        y=0,
        on_top=True
    )
    api.window = window
    
    webview.start(gui="edgechromium")
    
    return api.result if api.result else "CANCELLED"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        q = sys.argv[1]
        opts = sys.argv[2].split(",") if len(sys.argv) > 2 else None
        print(get_user_input(q, opts))
    else:
        print(get_user_input("Are you sure you want to proceed?", ["Yes", "No"]))
