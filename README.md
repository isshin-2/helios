<div align="center">
  <img src="https://img.shields.io/badge/HELIOS-Ecosystem-00e5ff?style=for-the-badge&logo=openai" alt="HELIOS Ecosystem">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Ollama-Local_AI-orange?style=for-the-badge" alt="Ollama">
  <img src="https://img.shields.io/badge/Three.js-3D_VRM_Avatar-black?style=for-the-badge&logo=threedotjs" alt="3D VRM">
  <img src="https://img.shields.io/badge/Expo-React_Native-4630EB?style=for-the-badge&logo=expo" alt="Expo Mobile">
  <br><br>
  <strong>A locally-hosted, multi-modal AI ecosystem with task-based model routing, zero-trust tool execution, an autonomous 3D VRM avatar companion, and a hybrid online/offline mobile app.</strong>
</div>

<br>

---

## 📂 Repository Structure

This monorepo unites the three core pillars of the **HELIOS** platform:

```text
HELIOS/
├── ai-router/       # Core AI Router, Orchestrator, Sandbox, Desktop UI & Tool Ecosystem (Port 8000)
├── helios-live2d/   # 3D VRM Autonomous Companion Add-On with Kokoro TTS & Lip-Sync (Port 8080)
├── mobile_v2/       # Expo / React Native Mobile Companion with Offline GGUF Fallback
└── start_helios.bat # Quick-start launcher for Windows
```

| Module | Description | Tech Stack |
| :--- | :--- | :--- |
| **[`ai-router/`](./ai-router)** | Core backend server, intelligent LLM router, vector memory (SQLite RAG), zero-trust sandbox, MCP client, and PyQt5 desktop overlays. | Python, FastAPI, Uvicorn, Ollama, SQLite, PyQt5 |
| **[`helios-live2d/`](./helios-live2d)** | Standalone & bridged 3D VRM companion server (`Riko` architecture) featuring structured action sequences, FBX animations, spatial movement, and real-time Kokoro ONNX viseme lip-sync. | FastAPI, WebSockets, Three.js / VRM, Kokoro ONNX |
| **[`mobile_v2/`](./mobile_v2)** | Cross-platform mobile app featuring the interactive AI Core WebView HUD, real-time WebSocket streaming to HELIOS Core, and offline on-device GGUF model execution. | React Native 0.86, Expo 57, TypeScript, `llama.rn` |

---

## ✨ Key Features

### 🧠 1. Core AI Router (`ai-router`)
* **Task-Based Model Routing**: Automatically classifies prompts (`coding`, `reasoning`, `vision`, `general`) and routes them to the optimal local or cloud model.
* **Hardware-Aware Auto-Provisioner & `llmfit`**: Scans CPU, RAM, VRAM, and Disk on startup to right-size and provision compatible local models automatically.
* **Zero-Trust Sandbox**: Restricts filesystem access to allowed directories, blocks system paths, and requires explicit human approval for high-risk shell or file modifications.
* **Vector Memory (RAG)**: Persists long-term facts, user preferences, and session context in local SQLite embeddings.
* **Desktop App & AI Core Overlay**: Includes both a full PyQt5 desktop client (`desktop_app.py`) and a frameless, click-through floating HUD overlay (`helios_desktop.py`, toggled via `Ctrl+Shift+Space`).
* **Rich Tool Ecosystem & MCP**: Built-in tools for Computer Vision (Set-of-Mark screen analysis), Stateful Shell, GitHub, Google Drive, CAD, 3D Printing (OctoPrint / BambuLabs), Self-Modification, and Model Context Protocol (MCP) servers.

### 🎭 2. 3D VRM Companion Add-On (`helios-live2d`)
* **Structured Sequence Protocol**: Translates LLM responses into multi-step JSON sequences combining speech, facial expressions (`happy`, `smug`, `relaxed`, `surprised`, etc.), spatial movement (`walk_to_user`, `circle_user`), and FBX animations (`wave`, `dance_shikano`, `backflip`, `hug_attempt`).
* **Streaming Kokoro ONNX TTS & Visemes**: Synthesizes low-latency voice audio and streams synchronized phoneme/viseme timelines for accurate 3D mouth movement.
* **HELIOS Core Bridge**: Auto-connects to `ai-router` on `http://localhost:8000` so tool executions and chat replies drive the 3D companion in real time.

### 📱 3. Mobile Companion (`mobile_v2`)
* **Hybrid Online / Offline Architecture**: Connects over WebSockets (`ws://<host>:8000/ws`) to the HELIOS desktop backend when on the same network, and seamlessly falls back to on-device inference via `llama.rn` (`.gguf` models) when offline.
* **AI Core HUD**: Embeds the interactive AI Core visualizer (`AICoreWebView.tsx`) alongside a native chat & model management view.

---

## 🚀 Quick Start

### Prerequisites
1. **[Python 3.11+](https://www.python.org/downloads/)** (ensure **"Add python.exe to PATH"** is checked on Windows).
2. **[Ollama](https://ollama.com/download)** installed and running locally.
3. **[Node.js 18+](https://nodejs.org/)** *(optional, required only for `mobile_v2`)*.

---

### 1️⃣ Start HELIOS Core (`ai-router`)
From the repository root on Windows, double-click **`start_helios.bat`** or run:

```powershell
cd ai-router
.\start.bat
```

* Creates and activates the Python virtual environment (`ai-router/venv`), installs dependencies, runs first-time hardware provisioning, and launches the server at **[http://localhost:8000](http://localhost:8000)**.
* To launch the full Desktop Window or floating AI Core overlay manually:
  ```powershell
  cd ai-router
  .\venv\Scripts\python.exe desktop_app.py      # Full Desktop UI
  .\venv\Scripts\python.exe helios_desktop.py   # Floating AI Core Overlay (Ctrl+Shift+Space)
  ```

---

### 2️⃣ Start the 3D VRM Companion (`helios-live2d`)
Once `ai-router` is set up, launch the 3D VRM add-on server:

```powershell
cd helios-live2d
.\start_vrm_addon.bat
```

* Opens the 3D VRM viewer server at **[http://localhost:8080](http://localhost:8080)** and bridges automatically to HELIOS Core at `http://localhost:8000`.

---

### 3️⃣ Run the Mobile App (`mobile_v2`)
```powershell
cd mobile_v2
npm install
npx expo start
```

* Use `npx expo run:android` or `npx expo run:ios` for native builds with `llama.rn` on-device GGUF model support.

---

## 📖 Documentation

* **[AI Router Guide](./ai-router/README.md)** — Setup, hardware tiers, and desktop overlay controls.
* **[Architecture Deep-Dive](./ai-router/ARCHITECTURE.md)** — Request lifecycle, zero-trust sandbox, VRAM offloading, and self-modification pipeline.
* **[3D VRM / Live2D Companion Guide](./helios-live2d/README.md)** — Avatar server endpoints, animation catalog, and Kokoro TTS setup.
* **[Mobile v2 Guide](./mobile_v2/README.md)** — Mobile app configuration, WebSocket bridge, and offline GGUF usage.
