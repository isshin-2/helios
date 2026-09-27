import re

with open('static/tensura_style.html', 'r', encoding='utf-8') as f:
    tensura_html = f.read()

with open('pwa/index.html', 'r', encoding='utf-8') as f:
    pwa_html = f.read()

# Extract the <style> from tensura
style_match = re.search(r'<style>(.*?)</style>', tensura_html, re.DOTALL)
tensura_style = style_match.group(1) if style_match else ''

# Extract the body content of tensura (the widget-container)
body_match = re.search(r'<div class="widget-container".*?</div>\s*<!-- END WIDGET -->', tensura_html, re.DOTALL)
if not body_match:
    body_match = re.search(r'<div class="widget-container".*?</script>', tensura_html, re.DOTALL)
    tensura_body = tensura_html[tensura_html.find('<div class="widget-container"'):tensura_html.find('<script>')]
else:
    tensura_body = body_match.group(0)

# Extract JS functions from tensura
script_match = re.search(r'<script>(.*?)</script>', tensura_html, re.DOTALL)
tensura_script = script_match.group(1) if script_match else ''

# Clean up tensura_body to not have the split-bg-container or controls if they are there
tensura_body = re.sub(r'<div class="split-bg-container">.*?</div>', '', tensura_body, flags=re.DOTALL)
tensura_body = re.sub(r'<div class="controls">.*?</div>', '', tensura_body, flags=re.DOTALL)

new_pwa_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>HELIOS Core</title>
    <link rel="manifest" href="manifest.json">
    <style>
{tensura_style}
        /* Override PWA body */
        body, html {{
            margin: 0; padding: 0;
            width: 100%; height: 100%;
            background-color: #050507 !important;
            display: flex;
            justify-content: center;
            align-items: center;
            flex-direction: column;
            overflow: hidden;
        }}
        
        /* Make widget container center in PWA */
        .widget-container {{
            transform: none !important;
            margin: 0 auto;
        }}
        
        #mic-btn {{
            margin-top: 40px;
            padding: 15px 30px;
            border-radius: 30px;
            background: rgba(255,255,255,0.1);
            color: white;
            border: 1px solid rgba(255,255,255,0.2);
            font-size: 16px;
            cursor: pointer;
            z-index: 100;
        }}
        
        #subtitle-text {{
            margin-top: 20px;
            color: #EBF0F5;
            font-size: 18px;
            text-align: center;
            max-width: 80%;
            min-height: 24px;
            z-index: 100;
        }}
    </style>
</head>
<body class="mode-core state-idle">

{tensura_body}

<div id="subtitle-text"></div>
<button id="mic-btn">Tap to Speak</button>

<script>
    const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
        ? 'http://127.0.0.1:8000' 
        : window.location.origin;
        
    const subtitleText = document.getElementById('subtitle-text');
    const micBtn = document.getElementById('mic-btn');

{tensura_script}

    // PWA Logic ported to use Tensura states
    let recognition;
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {{
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = 'en-US';

        recognition.onstart = () => {{
            setAIState('listening');
            subtitleText.innerText = "Listening...";
            micBtn.style.display = 'none';
        }};

        recognition.onresult = (event) => {{
            let interimTranscript = '';
            let finalTranscript = '';
            for (let i = event.resultIndex; i < event.results.length; ++i) {{
                if (event.results[i].isFinal) finalTranscript += event.results[i][0].transcript;
                else interimTranscript += event.results[i][0].transcript;
            }}
            subtitleText.innerText = finalTranscript || interimTranscript;
            
            if (finalTranscript) {{
                setAIState('thinking');
                sendToHelios(finalTranscript);
            }}
        }};

        recognition.onerror = (event) => {{
            setAIState('idle');
            subtitleText.innerText = "Error: " + event.error;
            micBtn.style.display = 'block';
        }};

        recognition.onend = () => {{
            if(document.body.classList.contains('state-listening')) {{
                setAIState('idle');
                subtitleText.innerText = "Didn't catch that.";
                micBtn.style.display = 'block';
            }}
        }};
    }} else {{
        subtitleText.innerText = "Speech recognition not supported on this browser.";
        micBtn.style.display = 'none';
    }}

    micBtn.addEventListener('click', () => {{
        if (recognition) recognition.start();
    }});

    async function sendToHelios(text) {{
        try {{
            let sessionId = localStorage.getItem('helios_session');
            const userId = 1;
            if (!sessionId) {{
                const sessRes = await fetch(`${{API_BASE}}/api/users/${{userId}}/sessions`, {{ method: 'POST' }});
                if (sessRes.ok) {{
                    const sessData = await sessRes.json();
                    sessionId = sessData.id;
                    localStorage.setItem('helios_session', sessionId);
                }}
            }}

            const res = await fetch(`${{API_BASE}}/api/chat/headless`, {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ message: text, user_id: userId, session_id: sessionId }})
            }});

            if (res.ok) {{
                const data = await res.json();
                const reply = data.response.replace(/[*_#`\\[\\]]/g, '');
                subtitleText.innerText = reply;
                setAIState('speaking');
                speak(reply);
            }} else {{
                setAIState('error');
                subtitleText.innerText = "Server Error";
                setTimeout(() => {{ setAIState('idle'); micBtn.style.display = 'block'; }}, 2000);
            }}
        }} catch (err) {{
            setAIState('error');
            subtitleText.innerText = "Connection Failed";
            setTimeout(() => {{ setAIState('idle'); micBtn.style.display = 'block'; }}, 2000);
        }}
    }}

    function speak(text) {{
        if ('speechSynthesis' in window) {{
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.onend = () => {{
                setAIState('idle');
                subtitleText.innerText = "";
                micBtn.style.display = 'block';
            }};
            utterance.onerror = () => {{
                setAIState('idle');
                micBtn.style.display = 'block';
            }};
            window.speechSynthesis.speak(utterance);
        }} else {{
            setTimeout(() => {{ setAIState('idle'); micBtn.style.display = 'block'; }}, 3000);
        }}
    }}
</script>
</body>
</html>
"""

with open('pwa/index.html', 'w', encoding='utf-8') as f:
    f.write(new_pwa_html)

print("Merged successfully!")
