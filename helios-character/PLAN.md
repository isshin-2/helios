# HELIOS Character Addon Integration Plan

This document outlines the step-by-step plan to provide an optional VRM / Live2D visual character addon for the HELIOS desktop application. We keep this in `helios-character` so the presentation layer remains decoupled from `ai-router`.

## 📁 Directory Structure
Inside this `helios-character` folder:
```text
helios-character/
├── PLAN.md                 # This document
├── ai_server.py            # Stateless Character Protocol bridge server
├── viewer/                 # The frontend VRM & Live2D web viewer
│   ├── index.html          # Main HTML for the transparent canvas
│   ├── app.js              # VRM + Live2D logic & WebSocket listener
│   ├── vrm/                # Modular VRM renderer, animation, expressions, humanizer, lip_sync
│   ├── live2d/             # Live2D renderer adapter
│   ├── style.css           # CSS to ensure transparent, borderless rendering
│   └── models/             # Directory to store VRM & Live2D character assets + manifest.json
```

## 🛠️ Implementation Steps

### Phase 1: Standalone Web Viewer (Isolation Testing)
Before touching HELIOS, we build the Live2D viewer as a standard webpage.
1. **Include Libraries:** Use `PixiJS` and `pixi-live2d-display` via CDN in `index.html`.
2. **Setup Canvas:** Create a transparent WebGL canvas that fills the screen.
3. **Load Model:** Write Javascript in `app.js` to load a `.model3.json` Live2D asset.
4. **Local Server:** Since browsers block loading local files via `file://` due to CORS, create a tiny `server.py` to serve the `viewer/` directory over `http://localhost:8080`.

### Phase 2: Connecting to HELIOS State Engine
HELIOS uses WebSockets to sync states (`idle`, `listening`, `thinking`, `speaking`).
1. **WebSocket Client:** Add a WebSocket client in `app.js` that connects to the HELIOS backend.
2. **Animation Triggers:** Map HELIOS states to Live2D expressions/motions.
   - `listening` -> Model leans in, ears perk up.
   - `thinking` -> Model looks up/away, hand on chin.
   - `idle` -> Normal breathing loop.

### Phase 3: Lip-Sync & Audio Integration
When HELIOS speaks (via Kokoro TTS), the model's mouth should move.
1. **Audio Routing:** Instead of HELIOS playing audio directly through Python, it can send the audio file URL or base64 audio data over the WebSocket to the `app.js` frontend.
2. **Audio Analyzer:** Use the browser's Web Audio API (`AudioContext` and `AnalyserNode`) to measure the volume/frequencies of the playing audio.
3. **Parameter Mapping:** Feed the volume data directly into the Live2D model's `ParamMouthOpen` parameter in real-time frame-by-frame.

### Phase 4: Merging into HELIOS
Once the standalone viewer works perfectly in a normal browser:
1. **Copy Assets:** Move the `viewer/` folder into `ai-router/static/live2d/`.
2. **Serve from HELIOS:** Update `ai-router/main.py` (or FastAPI backend) to serve the Live2D static assets.
3. **Update PyWebView:** Modify `helios_desktop.py` to load the new Live2D `index.html` as the primary UI overlay, ensuring `transparent=True` is maintained.
4. **Performance Tuning:** Adjust frame limits (e.g., cap at 30 FPS) if the Ollama models and the WebGL renderer fight for GPU resources.

## 🚀 Next Actions
If you agree with this plan, we can start by scaffolding the `viewer/` directory, writing the `index.html` and `app.js`, and downloading a free sample Live2D model to test with!
