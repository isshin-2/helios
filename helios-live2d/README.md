# HELIOS 3D VRM / Live2D Companion (`helios-live2d`)

An autonomous 3D VRM visual companion add-on for **HELIOS** (built on the Riko architecture). It renders an interactive 3D character in a borderless/web canvas, streams low-latency voice audio via **Kokoro ONNX**, computes phoneme/viseme timelines for real-time lip-sync, and choreographs spatial movement and FBX animations.

---

## ✨ Features

* **Structured Sequence Protocol**: Converts LLM responses into multi-step JSON action sequences (`speak`, `navigate`, `play_animation`, `wait`).
* **Spatial Movement & Animations**:
  * **Movements**: `idle`, `walk_to_user`, `step_back`, `circle_user`, `return_center`
  * **Animations**: `idle`, `walk`, `smug_pose`, `wave`, `backflip`, `dance_shikano`, `hug_attempt`, `refuse`, `think_pose`, `peace`, `cheer`, `shrug`, `bow`, `nod`, `confident`, `shy`
  * **Expressions**: `neutral`, `happy`, `angry`, `sad`, `relaxed`, `surprised`
* **Kokoro ONNX Streaming TTS**: Automatically loads the Kokoro ONNX model and voice pack from `../ai-router/.models/kokoro/` and streams synchronized audio + viseme weights to the frontend.
* **HELIOS Core Bridge**: Connects to the main `ai-router` server (`http://localhost:8000`) while serving the 3D viewer on `http://localhost:8080`.

---

## 📁 Directory Structure

```text
helios-live2d/
├── ai_server.py            # FastAPI + WebSocket companion backend & Kokoro TTS engine (Port 8080)
├── start_vrm_addon.bat     # Windows launcher (uses ../ai-router/venv)
├── PLAN.md                 # Original Live2D / VRM integration design notes
└── viewer/                 # Frontend 3D VRM / WebGL viewer
    ├── index.html          # Viewer UI & canvas
    ├── app.js              # Three.js / VRM loader, animation mixer, and WebSocket client
    ├── style.css           # Viewer styling
    └── models/             # VRM character model (Yu1_1.vrm), FBX animations, and voice samples
```

---

## 🚀 Running the Companion Server

Ensure `ai-router` has been set up first (so `../ai-router/venv` and `.models/kokoro` exist), then run:

```powershell
.\start_vrm_addon.bat
```

Or manually with Python:

```powershell
..\ai-router\venv\Scripts\python.exe ai_server.py
```

Then open **[http://localhost:8080](http://localhost:8080)** in your browser.
