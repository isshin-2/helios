import React from "react";
import { View, StyleSheet, Platform, SafeAreaView } from "react-native";
import { WebView } from "react-native-webview";

export function AICoreWebView() {
    const htmlContent = `
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=0.65, maximum-scale=0.65, user-scalable=no">
<title>AI Core - Popup Overlay</title>
<style>
    :root {
        /* Core Palette */
        --bg-slate: #0D0E12;
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
        
        /* Base Dimensions */
        --widget-w: 540px;
        --widget-h: 540px;
        --widget-rot: 0deg;
        --widget-shape: 80px;
    }

    body, html {
        margin: 0; padding: 0;
        width: 100%; height: 100%;
        background-color: var(--bg-slate);
        color: var(--off-white);
        font-family: 'Helvetica Neue Extended', DIN, -apple-system, sans-serif;
        display: flex; flex-direction: column;
        justify-content: center; align-items: center;
        box-sizing: border-box;
        overflow: hidden;
    }

    .widget-container {
        position: relative;
        width: var(--widget-w); 
        height: var(--widget-h);
        background: linear-gradient(135deg, #1a1c23 0%, #0D0E12 100%);
        border: 1px solid var(--charcoal);
        box-shadow: 0 40px 80px rgba(0,0,0,0.8);
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
        width: 440px; height: 440px;
        left: 50%; top: 50%;
        transform: translate(-50%, -50%) rotate(calc(var(--widget-rot) * -1));
        transition: top 0.7s cubic-bezier(0.25, 1, 0.25, 1),
                    left 0.7s cubic-bezier(0.25, 1, 0.25, 1),
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

    .status-badge {
        position: absolute;
        bottom: -25px; left: 50%;
        transform: translateX(-50%);
        display: flex; align-items: center; gap: 10px;
        padding: 8px 20px; background: var(--bg-slate);
        border: 1px solid var(--charcoal); z-index: 20;
        transition: bottom 0.4s ease, top 0.7s cubic-bezier(0.25,1,0.25,1), opacity 0.4s ease;
    }
    .status-dot {
        width: 8px; height: 8px; background: var(--accent-color);
        box-shadow: 0 0 10px var(--accent-color);
        animation: pulse var(--pulse-speed) ease-in-out infinite alternate;
        transition: background 0.4s ease, box-shadow 0.4s ease;
    }
    .status-text { font-size: 12px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; color: var(--off-white); }
    @keyframes pulse { 0% { opacity: 0.2; transform: scale(0.8); } 100% { opacity: 1; transform: scale(1.2); } }

    /* LAYOUT MODE: QUESTIONS/MENU (600x540) */
    body.mode-menu .widget-container {
        width: 600px !important;
        height: 540px !important;
        border-radius: 40px !important;
        transform: rotate(0deg) !important;
        border-color: var(--accent-cyan) !important;
    }
    body.mode-menu .widget-inner {
        top: 25% !important;
        transform: translate(-50%, -50%) rotate(0deg) scale(0.55) !important;
    }
    body.mode-menu .status-badge {
        bottom: auto !important;
        top: 48% !important;
        border-radius: 20px !important;
        opacity: 1 !important;
    }

    .options-panel {
        position: absolute;
        left: 50%; bottom: 30px;
        transform: translateX(-50%) translateY(30px);
        width: 520px;
        display: flex; flex-direction: column; gap: 12px;
        opacity: 0; pointer-events: none;
        transition: opacity 0.5s ease, transform 0.5s cubic-bezier(0.25,1,0.25,1);
    }
    body.mode-menu .options-panel {
        opacity: 1; pointer-events: auto;
        transform: translateX(-50%) translateY(0);
        transition-delay: 0.2s;
    }

    .options-header {
        font-size: 12px; font-weight: 700; letter-spacing: 4px; color: rgba(255,255,255,0.4);
        margin-bottom: 15px; text-transform: uppercase; border-bottom: 1px solid var(--charcoal); padding-bottom: 8px;
    }

    .option-btn {
        background: rgba(255,255,255,0.02);
        border: 1px solid var(--charcoal);
        color: var(--off-white);
        padding: 18px 24px; width: 100%;
        text-align: left; font-family: inherit; font-size: 14px; font-weight: 600;
        letter-spacing: 2px; text-transform: uppercase;
        cursor: pointer; transition: all 0.3s ease;
        display: flex; justify-content: space-between; align-items: center;
        border-radius: 8px;
    }
    .option-btn::after {
        content: "+"; font-size: 18px; font-weight: 300; opacity: 0.5; transition: 0.3s;
    }
    .option-btn:hover {
        background: rgba(255,255,255,0.08); border-color: var(--accent-color);
        padding-left: 32px; color: var(--pure-white);
    }
    .option-btn:hover::after { opacity: 1; color: var(--accent-color); transform: rotate(90deg); }
    
    .text-input-row { display: flex; gap: 5px; margin-top: 5px; }
    .text-input-row input {
        flex: 1; background: rgba(0,0,0,0.3); border: 1px solid var(--charcoal);
        color: #FFFFFF; padding: 16px 20px; font-family: inherit; font-size: 14px;
        outline: none; border-radius: 8px; transition: border-color 0.3s;
    }
    .text-input-row input:focus { border-color: var(--accent-cyan); }
    .text-input-row button {
        background: rgba(0, 229, 255, 0.1); border: 1px solid var(--accent-cyan);
        color: var(--accent-cyan); padding: 0 20px; cursor: pointer; font-weight: bold;
        border-radius: 8px; transition: all 0.3s; font-size: 14px;
    }
    .text-input-row button:hover { background: var(--accent-cyan); color: #000; }

    /* State 0: IDLE */
    body.state-idle {
        --widget-w: 300px; --widget-h: 540px; --widget-shape: 150px; --widget-rot: 0deg;
        --spin-speed: 20s; --accent-color: var(--charcoal); --horizon-glow: 0 0 0px transparent;
    }
    body.state-idle .black-hole-svg { animation: breathe 6s ease-in-out infinite alternate; opacity: 0.3;}
    @keyframes breathe { 0% { transform: scale(0.88); } 100% { transform: scale(0.92); } }
    body.state-idle:not(.mode-menu) .status-badge { opacity: 0; pointer-events: none; bottom: 0px;}

    /* State 1: LISTENING */
    body.state-listening {
        --widget-w: 540px; --widget-h: 540px; --widget-shape: 80px; --widget-rot: 0deg;
        --accent-color: var(--accent-cyan); --spin-speed: 8s; --horizon-glow: 0 0 15px rgba(0, 229, 255, 0.2);
    }
    body.state-listening .status-badge { border-radius: 25px; }
    body.state-listening .widget-container { border-color: rgba(0, 229, 255, 0.3); }

    /* State 2: THINKING */
    body.state-thinking {
        --widget-w: 440px; --widget-h: 440px; --widget-shape: 0px; --widget-rot: 45deg;
        --spin-speed: 1.2s; --pulse-speed: 0.1s; --horizon-glow: 0 0 35px rgba(255, 204, 0, 0.3);
        --accent-color: var(--accent-amber);
    }
    body.state-thinking .widget-container { border-color: var(--accent-amber); }
    body.state-thinking .spin-slow { stroke-dasharray: 4 20; }
    body.state-thinking:not(.mode-menu) .status-badge { border-radius: 0px; bottom: -45px;}

    /* State 3: SPEAKING */
    body.state-speaking {
        --widget-w: 540px; --widget-h: 540px; --widget-shape: 50%; --widget-rot: 0deg;
        --spin-speed: 4s; --wave-opacity: 0.7; --horizon-glow: 0 0 25px rgba(50, 150, 250, 0.4);
        --accent-color: var(--accent-blue); --svg-scale: 1.1;
    }
    body.state-speaking .widget-container { border-color: var(--accent-blue); border-width: 2px;}
    body.state-speaking .status-dot { animation: none; transform: scale(1); }
    body.state-speaking .status-badge { border-radius: 25px; }
</style>
</head>
<body class="mode-core state-idle">
    <div class="widget-container">
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
        <div class="status-badge">
            <span class="status-dot"></span>
            <span class="status-text" id="statusText">Idle</span>
        </div>
        <div class="options-panel">
            <div class="options-header" id="questionHeader">System Access</div>
            <div id="options-list"></div>
        </div>
    </div>
    <script>
        function setQuestion(text) {
            document.getElementById("questionHeader").innerText = text;
        }

        function addOption(text) {
            const container = document.getElementById("options-list");
            const btn = document.createElement("button");
            btn.className = "option-btn";
            btn.innerText = text;
            btn.onclick = () => { 
                if(window.ReactNativeWebView) {
                    window.ReactNativeWebView.postMessage(JSON.stringify({ type: 'submit', value: text }));
                }
            };
            container.appendChild(btn);
        }

        function addTextInput() {
            const container = document.getElementById("options-list");
            const row = document.createElement("div");
            row.className = "text-input-row";
            
            const inp = document.createElement("input");
            inp.type = "text"; inp.placeholder = "Type response...";
            inp.onkeypress = (e) => {
                if (e.key === "Enter" && inp.value.trim() && window.ReactNativeWebView) {
                    window.ReactNativeWebView.postMessage(JSON.stringify({ type: 'submit', value: inp.value.trim() }));
                }
            };
            
            const btn = document.createElement("button");
            btn.innerText = "OK";
            btn.onclick = () => {
                if (inp.value.trim() && window.ReactNativeWebView) {
                    window.ReactNativeWebView.postMessage(JSON.stringify({ type: 'submit', value: inp.value.trim() }));
                }
            };
            
            row.appendChild(inp); row.appendChild(btn); container.appendChild(row);
            setTimeout(() => inp.focus(), 800);
        }

        function toggleLayoutMode(enabled) {
            if (enabled) {
                setAIState('listening');
                document.body.classList.replace("mode-core", "mode-menu");
            } else {
                document.body.classList.replace("mode-menu", "mode-core");
            }
        }

        function setAIState(state) {
            document.body.className = document.body.className.replace(/state-\w+/g, '');
            document.body.classList.add(\`state-\${state}\`);
            document.getElementById('statusText').innerText = state;
        }

        document.body.addEventListener('click', () => {
            if (!document.body.classList.contains('mode-menu')) {
                toggleLayoutMode(true);
                setQuestion('System Demo');
                document.getElementById('options-list').innerHTML = '';
                addOption('Accept');
                addOption('Reject');
            } else {
                toggleLayoutMode(false);
            }
        });
    </script>
</body>
</html>
`;

    return (
        <SafeAreaView style={styles.container}>
            <WebView
                originWhitelist={['*']}
                source={{ html: htmlContent }}
                style={styles.webview}
                scrollEnabled={false}
                onMessage={(event) => console.log("Message from WebView:", event.nativeEvent.data)}
            />
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: "#0D0E12",
    },
    webview: {
        flex: 1,
        backgroundColor: "transparent",
    }
});
