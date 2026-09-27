import re

user_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Core - Dynamic Layouts & States</title>
<style>
    :root {
        /* Core Palette */
        --bg-slate: transparent;
        --core-black: #050507;
        --charcoal: #2C3038;
        --off-white: #EBF0F5;
        --pure-white: #FFFFFF;
        
        /* State Accents */
        --accent-amber: #FFCC00;
        --accent-blue: #3296fa;
        --accent-cyan: #00e5ff;
        
        /* Shared variables */
        --spin-speed: 8s;
        --pulse-speed: 2s;
        --wave-opacity: 0;
        --horizon-glow: 0 0 10px rgba(235, 240, 245, 0.1);
        --accent-color: var(--off-white);
        
        /* Background & Shape Variables */
        --bg-color-top: var(--bg-slate);
        --bg-color-bot: var(--bg-slate);
        --clip-top: polygon(0 0, 100% 0, 100% 100%, 0 100%);
        --clip-bot: polygon(0 0, 100% 0, 100% 100%, 0 100%);
        --emblem-scale: 1;
        --emblem-rot: 0deg;
        --text-slide: 0%;
        
        /* Default Core Transforms (Overwritten by states) */
        --widget-w: 250px;
        --widget-h: 250px;
        --widget-rot: 0deg;
        --widget-shape: 46px;
    }

    /* =========================================
       DYNAMIC BACKGROUND LAYOUT
       ========================================= */
    .split-bg-container {
        position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 0; overflow: hidden;
    }
    .split-card {
        position: absolute; width: 100%; height: 100%;
        transition: clip-path 0.8s cubic-bezier(0.19, 1, 0.22, 1), background-color 0.8s ease;
        display: flex; justify-content: center; align-items: center;
    }
    .card-top { background: var(--bg-color-top); clip-path: var(--clip-top); z-index: 2; }
    .card-bottom { background: var(--bg-color-bot); clip-path: var(--clip-bot); z-index: 1; }
    
    .emblem {
        position: absolute; width: 70vmin; height: 70vmin;
        border: 1px solid rgba(255,255,255,0.05); border-radius: 50%;
        display: flex; justify-content: center; align-items: center;
        transition: transform 0.8s cubic-bezier(0.19, 1, 0.22, 1),
                    top 0.8s cubic-bezier(0.19, 1, 0.22, 1),
                    bottom 0.8s cubic-bezier(0.19, 1, 0.22, 1),
                    left 0.8s cubic-bezier(0.19, 1, 0.22, 1),
                    right 0.8s cubic-bezier(0.19, 1, 0.22, 1),
                    opacity 0.8s ease;
        transform: scale(var(--emblem-scale)) rotate(var(--emblem-rot));
    }
    .emblem::before, .emblem::after {
        content: ''; position: absolute; width: 80%; height: 80%;
        border: 1px dashed rgba(255,255,255,0.1); transition: transform 0.8s ease;
    }
    .emblem::before { transform: rotate(45deg); }
    .emblem::after { transform: rotate(-45deg); width: 60%; height: 60%; border-style: solid; border-color: rgba(255,255,255,0.03);}

    .kinetic-text {
        position: absolute; font-size: 14vw; font-weight: 900; letter-spacing: 1vw;
        color: rgba(255,255,255,0.02); text-transform: uppercase; white-space: nowrap; pointer-events: none;
        transition: transform 0.8s cubic-bezier(0.19, 1, 0.22, 1), opacity 0.5s ease;
    }
    .card-top .kinetic-text { top: 5%; left: 0%; transform: translateX(var(--text-slide, 0)); }
    .card-bottom .kinetic-text { bottom: 5%; right: 0%; transform: rotate(180deg) translateX(var(--text-slide, 0)); }

    /* =========================================
       AI LOGO CORE (SHAPE SHIFTING CONTAINER)
       ========================================= */
    .widget-container {
        position: relative;
        width: var(--widget-w); 
        height: var(--widget-h);
        background: linear-gradient(135deg, #1a1c23 0%, #0D0E12 100%);
        border: 1px solid var(--charcoal);
        box-shadow: 0 30px 60px rgba(0,0,0,0.8);
        z-index: 10;
        border-radius: var(--widget-shape);
        transform: rotate(var(--widget-rot));
        transition: width 0.7s cubic-bezier(0.25, 1, 0.25, 1),
                    height 0.7s cubic-bezier(0.25, 1, 0.25, 1),
                    border-radius 0.7s cubic-bezier(0.25, 1, 0.25, 1),
                    transform 0.7s cubic-bezier(0.25, 1, 0.25, 1),
                    border-color 0.4s ease, box-shadow 0.4s ease;
    }

    .widget-inner {
        position: absolute;
        width: 250px; height: 250px;
        left: 50%; top: 50%;
        transform: translate(-50%, -50%) rotate(calc(var(--widget-rot) * -1));
        transition: left 0.7s cubic-bezier(0.25, 1, 0.25, 1),
                    transform 0.7s cubic-bezier(0.25, 1, 0.25, 1);
        display: flex; justify-content: center; align-items: center;
    }

    .black-hole-svg {
        width: 100%; height: 100%;
        transform: scale(var(--svg-scale, 0.9));
        transition: transform 0.5s cubic-bezier(0.16, 1, 0.3, 1);
    }

    .event-horizon {
        fill: var(--core-black); stroke: var(--charcoal); stroke-width: 2;
        transition: stroke 0.4s ease, filter 0.4s ease;
        filter: drop-shadow(var(--horizon-glow));
    }
    .ring-line { fill: none; stroke: var(--pure-white); transition: stroke-dasharray 0.4s ease, stroke-opacity 0.4s ease; }
    .ring-back { stroke: var(--charcoal); }

    .spin-slow { stroke-dasharray: 60 120; animation: orbit var(--spin-speed) linear infinite; }
    .spin-fast { stroke-dasharray: 10 30; animation: orbitFront calc(var(--spin-speed) * 0.6) linear infinite; stroke: var(--accent-color); transition: stroke 0.4s ease; }

    @keyframes orbit { 0% { stroke-dashoffset: 360; } 100% { stroke-dashoffset: 0; } }
    @keyframes orbitFront { 0% { stroke-dashoffset: 0; } 100% { stroke-dashoffset: 360; } }

    .speak-wave { fill: none; stroke: var(--accent-color); stroke-width: 1.5; opacity: 0; transform-origin: center; }
    @keyframes speakPulse { 0% { transform: scale(0.8); opacity: var(--wave-opacity); } 100% { transform: scale(2.5); opacity: 0; } }
    .speak-wave-1 { animation: speakPulse 1.8s cubic-bezier(0.16, 1, 0.3, 1) infinite; }
    .speak-wave-2 { animation: speakPulse 1.8s cubic-bezier(0.16, 1, 0.3, 1) infinite 0.6s; }

    /* UI Badge */
    .status-badge {
        position: absolute;
        bottom: -20px; left: 50%;
        transform: translateX(-50%);
        display: flex; align-items: center; gap: 8px;
        padding: 6px 16px; background: rgba(13, 14, 18, 0.8);
        border: 1px solid var(--charcoal); z-index: 20;
        transition: bottom 0.4s ease, opacity 0.4s ease, left 0.7s cubic-bezier(0.25,1,0.25,1);
    }
    .status-dot {
        width: 6px; height: 6px; background: var(--accent-color);
        box-shadow: 0 0 8px var(--accent-color);
        animation: pulse var(--pulse-speed) ease-in-out infinite alternate;
        transition: background 0.4s ease, box-shadow 0.4s ease;
    }
    .status-text { font-size: 10px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; color: var(--off-white); }
    @keyframes pulse { 0% { opacity: 0.2; transform: scale(0.8); } 100% { opacity: 1; transform: scale(1.2); } }

    /* =========================================
       AI STATES (IDLE, LISTENING, THINKING, SPEAKING)
       ========================================= */

    /* State 0: IDLE
       - Steep angular shear split
       - Shrunk, retracted aperture emblems
       - Shifted typography slide */
    body.state-idle {
        --bg-color-top: rgba(8, 9, 12, 0.5); 
        --bg-color-bot: var(--bg-slate);
        --clip-top: polygon(0 0, 100% 0, 100% 18%, 0 82%); /* Asymmetrical angle */
        --emblem-scale: 0.65;
        --emblem-rot: -90deg;
        --text-slide: -25%; /* Slid out to left */
        --widget-w: 160px; --widget-h: 300px; --widget-shape: 100px; --widget-rot: 0deg;
        --spin-speed: 20s; --accent-color: var(--charcoal); --horizon-glow: 0 0 0px transparent;
    }
    body.state-idle .card-top .emblem {
        top: -15%;
        opacity: 0.15;
    }
    body.state-idle .card-bottom .emblem {
        bottom: -15%;
        opacity: 0.15;
    }
    body.state-idle .emblem, body.state-idle .black-hole-svg { 
        animation: breathe 6s ease-in-out infinite alternate; 
    }
    @keyframes breathe { 0% { transform: scale(0.88); } 100% { transform: scale(0.92); } }
    body.state-idle .kinetic-text::after { content: "STANDBY"; }
    body.state-idle:not(.mode-menu) .status-badge { opacity: 0; pointer-events: none; bottom: 0px;}

    /* State 1: LISTENING
       - Levels out to clean 50/50 horizontal card split
       - Emblems glide inwards to center axis, rotate 90°, expand to full 1.0
       - Typography glides in to 0% */
    body.state-listening {
        --bg-color-top: rgba(21, 24, 33, 0.5); 
        --bg-color-bot: rgba(35, 39, 48, 0.5);
        --clip-top: polygon(0 0, 100% 0, 100% 50%, 0 50%); /* Clean horizontal snap */
        --emblem-scale: 1;
        --emblem-rot: 0deg;
        --text-slide: 0%; /* Glides into center */
        --widget-w: 250px; --widget-h: 250px; --widget-shape: 46px; --widget-rot: 0deg;
        --accent-color: var(--accent-cyan); --spin-speed: 8s; --horizon-glow: 0 0 15px rgba(0, 229, 255, 0.2);
    }
    body.state-listening .card-top .emblem { 
        top: 0%; 
        transform: translateY(-50%) scale(var(--emblem-scale)) rotate(var(--emblem-rot)); 
        opacity: 0.45;
    }
    body.state-listening .card-bottom .emblem { 
        bottom: 0%; 
        transform: translateY(50%) scale(var(--emblem-scale)) rotate(var(--emblem-rot)); 
        opacity: 0.45;
    }
    body.state-listening .kinetic-text::after { content: "RESONANCE"; }
    body.state-listening .status-badge { border-radius: 20px; }
    body.state-listening .widget-container { border-color: rgba(0, 229, 255, 0.3); }

    /* State 2: THINKING */
    body.state-thinking {
        --bg-color-top: rgba(10, 11, 13, 0.5); --bg-color-bot: var(--bg-slate);
        --clip-top: polygon(0 0, 100% 0, 100% 100%, 0 0);
        --emblem-scale: 1.2; --emblem-rot: 45deg;
        --widget-w: 250px; --widget-h: 250px; --widget-shape: 0px; --widget-rot: 45deg;
        --spin-speed: 1.2s; --pulse-speed: 0.1s; --horizon-glow: 0 0 25px rgba(255, 204, 0, 0.3);
        --accent-color: var(--accent-amber); --text-slide: -8%;
    }
    body.state-thinking .card-top .emblem { top: -10%; right: -10%; opacity: 0.3; }
    body.state-thinking .card-bottom .emblem { bottom: -10%; left: -10%; opacity: 0.3; }
    body.state-thinking .widget-container { border-color: var(--accent-amber); }
    body.state-thinking .spin-slow { stroke-dasharray: 4 20; }
    body.state-thinking .kinetic-text::after { content: "PARADOX"; }
    body.state-thinking:not(.mode-menu) .status-badge { border-radius: 0px; bottom: -35px;}

    /* State 3: SPEAKING */
    body.state-speaking {
        --bg-color-top: var(--bg-slate); --bg-color-bot: rgba(44, 48, 56, 0.5);
        --clip-top: polygon(0 0, 50% 0, 50% 100%, 0 100%); 
        --emblem-scale: 0.8; --emblem-rot: 90deg;
        --widget-w: 250px; --widget-h: 250px; --widget-shape: 50%; --widget-rot: 0deg;
        --spin-speed: 4s; --wave-opacity: 0.7; --horizon-glow: 0 0 20px rgba(50, 150, 250, 0.4);
        --accent-color: var(--accent-blue); --text-slide: 8%; --svg-scale: 1.1;
    }
    body.state-speaking .card-top .emblem { left: 0; top: 50%; transform: translate(-50%, -50%) scale(var(--emblem-scale)) rotate(var(--emblem-rot)); opacity: 0.3; }
    body.state-speaking .card-bottom .emblem { right: 0; top: 50%; transform: translate(50%, -50%) scale(var(--emblem-scale)) rotate(var(--emblem-rot)); opacity: 0.3; }
    body.state-speaking .widget-container { border-color: var(--accent-blue); border-width: 2px;}
    body.state-speaking .status-dot { animation: none; transform: scale(1); }
    body.state-speaking .kinetic-text::after { content: "PROMISE"; color: rgba(50,150,250,0.05); }
    body.state-speaking .status-badge { border-radius: 20px; }
"""

css_match = re.search(r'<style>([\s\S]*?)</style>', user_html)
new_css = css_match.group(1) if css_match else ""

# Remove the body/html block that overrides the main layout
new_css = re.sub(r'body,\s*html\s*\{[\s\S]*?\}', '', new_css)
new_css = new_css.strip()

new_dom = """
    <!-- Split Background -->
    <div class="split-bg-container">
        <div class="split-card card-top"><div class="kinetic-text"></div><div class="emblem"></div></div>
        <div class="split-card card-bottom"><div class="kinetic-text"></div><div class="emblem"></div></div>
    </div>

    <!-- MAIN AI WIDGET CONTAINER -->
    <div class="widget-container" id="tensura-bg" style="z-index: 10;">
        <!-- SVG Inner Wrapper -->
        <div class="widget-inner">
            <svg class="black-hole-svg" viewBox="0 0 240 240">
                <circle cx="120" cy="120" r="42" class="speak-wave speak-wave-1" />
                <circle cx="120" cy="120" r="42" class="speak-wave speak-wave-2" />
                <g transform="rotate(-15 120 120)">
                    <path d="M 20,120 A 100,30 0 0,1 220,120" class="ring-line ring-back" stroke-width="1" />
                    <path d="M 35,120 A 85,22 0 0,1 205,120" class="ring-line ring-back spin-slow" stroke-width="1.5" />
                    <circle cx="120" cy="120" r="44" class="event-horizon" />
                    <path d="M 50,120 A 70,16 0 0,0 190,120" class="ring-line" stroke-dasharray="2 6" stroke-width="1" stroke-opacity="0.5" />
                    <path d="M 20,120 A 100,30 0 0,0 220,120" class="ring-line spin-slow" stroke-width="1.5" />
                    <path d="M 35,120 A 85,22 0 0,0 205,120" class="ring-line spin-fast" stroke-width="2" />
                </g>
                <line x1="120" y1="65" x2="120" y2="70" stroke="#EBF0F5" stroke-width="1" opacity="0.4"/>
                <line x1="120" y1="170" x2="120" y2="175" stroke="#EBF0F5" stroke-width="1" opacity="0.4"/>
                <line x1="65" y1="120" x2="70" y2="120" stroke="#EBF0F5" stroke-width="1" opacity="0.4"/>
                <line x1="170" y1="120" x2="175" y2="120" stroke="#EBF0F5" stroke-width="1" opacity="0.4"/>
            </svg>
        </div>
        
        <!-- Attached Status Badge -->
        <div class="status-badge">
            <span class="status-dot"></span>
            <span class="status-text" id="statusText">Idle</span>
        </div>
    </div>
"""

with open('static/app.html', 'r', encoding='utf-8') as f:
    app_html = f.read()

# Replace old CSS
start_css = app_html.find('/* TENSURA CSS */')
end_css = app_html.find('</style>', start_css)
if start_css != -1 and end_css != -1:
    app_html = app_html[:start_css] + "/* TENSURA CSS */\n" + new_css + "\n" + app_html[end_css:]
else:
    print("Could not find CSS block")

# Replace old DOM
# We want to replace everything from <div id="tensura-pane" ...> to </div> just before <!-- Workspace Pane
start_pane = app_html.find('<div id="tensura-pane"')
if start_pane != -1:
    end_pane = app_html.find('<!-- Workspace Pane', start_pane)
    if end_pane != -1:
        # Actually we just want to replace the inside of tensura-pane, or we can replace the whole tensura-pane block
        pane_header = app_html[start_pane:app_html.find('HELIOS AI CORE</div>', start_pane) + len('HELIOS AI CORE</div>')]
        
        # We need to backtrack to the closing </div> of tensura-pane which is right before <!-- Workspace Pane
        # Instead, let's just find <div id="tensura-bg"
        start_bg = app_html.find('<div id="tensura-bg"', start_pane)
        # Find the </div> that closes tensura-pane
        # We know from earlier that the structure is completely flat now!
        # So right before <!-- Workspace Pane --> is the closing tag for tensura-pane
        # Wait, no, tensura-pane is closed. Let's just find the closing tag right before Workspace Pane
        end_bg = app_html.rfind('</div>', start_pane, end_pane)
        
        app_html = app_html[:start_bg] + new_dom + "\n    " + app_html[end_bg:]
        print("DOM replaced.")

with open('static/app.html', 'w', encoding='utf-8') as f:
    f.write(app_html)

print("Applied!")
