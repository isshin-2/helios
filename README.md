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
├── ai-router/         # Core AI Router, Sandbox, Desktop UI & Swarm Engine (Port 8000)
├── helios-character/  # Airi — 3D VRM / Live2D Avatar Presentation Addon (Port 8080)
├── mobile_v2/         # Expo / React Native Mobile Companion with Offline GGUF Fallback
├── hikari.bat         # Launcher for Hikari Autonomous Coding CLI (Claude Code style)
└── start_helios.bat   # Quick-start launcher for Windows
```

| Module | Description | Tech Stack |
| :--- | :--- | :--- |
| **[`ai-router/`](./ai-router)** | Core backend server, intelligent LLM router, vector memory (SQLite RAG), zero-trust sandbox, MCP client, and PyQt5 desktop overlays. | Python, FastAPI, Uvicorn, Ollama, SQLite, PyQt5 |
| **[`helios-character/`](./helios-character)** | **Airi** — 3D VRM & Live2D avatar presentation companion driven by HELIOS Core's Character Protocol (`/ws/character`) with procedural humanization, FBX animations, spatial navigation, and VoiceManager lip-sync. | FastAPI, WebSockets, Three.js / VRM, Live2D |
| **[`mobile_v2/`](./mobile_v2)** | Cross-platform mobile app featuring the interactive AI Core WebView HUD, real-time WebSocket streaming to HELIOS Core, and offline on-device GGUF model execution. | React Native 0.86, Expo 57, TypeScript, `llama.rn` |
| **Hikari** | **Hikari (`hikari.bat`)** — Autonomous multi-agent coding CLI (Claude Code & Codex style) featuring the HELIOS Black Hole visual representation, git worktree isolation, automated test verification, and rollback safety. | Python, Rich, Git Worktrees, Pytest, Multi-Agent Swarm |

---

## ✨ Key Features

### 💻 1. Hikari Autonomous Coding CLI (`hikari.bat`)
* **Event Horizon Visual HUD**: Styled after the HELIOS AI Core with a signature relativistic Black Hole ASCII representation and accretion disk telemetry badges.
* **Autonomous Coding Swarm**: Multi-agent software engineering terminal interface (Claude Code & Codex CLI style) driven by 8 specialized agents (`Planner`, `Architect`, `Repo Mapper`, `Coder`, `Tester`, `Repair`, `Reviewer`, `Security Reviewer`).
* **Git Worktree Isolation**: Safely develops code inside isolated `.helios_worktrees` so your working branch is never modified unless all verification tests pass.
* **Deterministic Automated Verification**: Executes real unit tests (`pytest`), detects failure root causes, and executes automated self-repair loops.
* **Interactive CLI Commands**: Inspect terminal diffs (`/diff`), run code review (`/review`), run tests (`/test`), check active VRAM model allocations (`/models`), or rollback changes (`/rollback`).

### 🧠 2. Core AI Router (`ai-router`)
* **Task-Based Model Routing**: Automatically classifies prompts (`coding`, `reasoning`, `vision`, `general`) and routes them to the optimal local or cloud model.
* **Hardware-Aware Auto-Provisioner & `llmfit`**: Scans CPU, RAM, VRAM, and Disk on startup to right-size and provision compatible local models automatically.
* **Zero-Trust Sandbox**: Restricts filesystem access to allowed directories, blocks system paths, and requires explicit human approval for high-risk shell or file modifications.
* **Vector Memory (RAG)**: Persists long-term facts, user preferences, and session context in local SQLite embeddings.
* **Desktop App & AI Core Overlay**: Includes both a full PyQt5 desktop client (`desktop_app.py`) and a frameless, click-through floating HUD overlay (`helios_desktop.py`, toggled via `Ctrl+Shift+Space`).
* **Rich Tool Ecosystem & MCP**: Built-in tools for Computer Vision (Set-of-Mark screen analysis), Stateful Shell, GitHub, Google Drive, CAD, 3D Printing (OctoPrint / BambuLabs), Self-Modification, and Model Context Protocol (MCP) servers.

### 🎭 2. Airi Avatar Companion (`helios-character`)
* **3D VRM Avatar Companion (Airi)**: Real-time 3D techwear VRM character body with full spatial movement, facial expressions, and body gesture controls.
* **Optional Presentation Layer**: Strictly separated from HELIOS Core intelligence (`CHARACTER_ENABLED=true/false`, `CHARACTER_RENDERER=vrm/live2d`, `CHARACTER_MODEL=helios-v1`). HELIOS continues functioning normally if the character is disabled, crashes, or disconnects.
* **Deterministic Emotion Engine & Safety Lock**: Translates EventBus lifecycle events (`tool_called`, `tool_completed`, `tool_failed`, `approval_required`) into renderer-independent `CharacterState` updates without extra LLM latency, and enforces `serious` mode during critical/destructive actions.
* **VoiceManager Lip-Sync**: Driven by `VoiceManager` (`speech_started`, `audio_chunk`, `speech_finished`, `speech_interrupted`) with 30-FPS RMS envelopes and viseme timelines.

### 📱 3. Mobile Companion (`mobile_v2`)
* **Hybrid Online / Offline Architecture**: Connects over WebSockets (`ws://<host>:8000/ws`) to the HELIOS desktop backend when on the same network, and seamlessly falls back to on-device inference via `llama.rn` (`.gguf` models) when offline.
* **AI Core HUD**: Embeds the interactive AI Core visualizer (`AICoreWebView.tsx`) alongside a native chat & model management view.

---

## 🚀 Quick Start (Two Versions Available)

HELIOS can be launched in **two distinct versions** depending on your needs (or via the interactive `start_helios.bat` menu):

| Version | Launcher Script | What It Runs |
| :--- | :--- | :--- |
| **⚡ Version 1: Full Spec** | **`start_helios_full_spec.bat`** *(or `start_helios.bat 1`)* | Full HELIOS stack: **`ai-router` (`:8000`)** (multi-model router, zero-trust sandbox, vector RAG memory, tools, MCP, desktop overlay) **+** **`helios-character` (`:8080`)** bridged via `/ws/character`. |
| **🎭 Version 2: Just the Character** | **`start_character_only.bat`** *(or `start_helios.bat 2`)* | Standalone 3D VRM Character (`:8080`) with its own lightweight local Ollama chat, neural TTS + 30-FPS lip-sync, 24 human reference poses, 6 posture styles, and RL pose trainer — **no `ai-router` (`:8000`) stack required**. |

### Prerequisites
1. **[Python 3.11+](https://www.python.org/downloads/)** (ensure **"Add python.exe to PATH"** is checked on Windows).
2. **[Ollama](https://ollama.com/download)** installed and running locally.
3. **[Node.js 18+](https://nodejs.org/)** *(optional, required only for `mobile_v2`)*.

---

### ⚡ Option A: Launch the Full Spec Version (`ai-router` + `helios-character`)
From the repository root on Windows, double-click **`start_helios_full_spec.bat`** (or run `start_helios.bat` and choose `[1]`):

```powershell
.\start_helios_full_spec.bat
```

* Launches **HELIOS Core (`ai-router`)** at **[http://localhost:8000](http://localhost:8000)** (plus the desktop AI Core overlay) AND **HELIOS Character (`helios-character`)** at **[http://localhost:8080?edition=full_spec](http://localhost:8080?edition=full_spec)**.
* To launch the full Desktop Window or floating AI Core overlay manually:
  ```powershell
  cd ai-router
  .\venv\Scripts\python.exe desktop_app.py      # Full Desktop UI
  .\venv\Scripts\python.exe helios_desktop.py   # Floating AI Core Overlay (Ctrl+Shift+Space)
  ```

---

### 🎭 Option B: Launch Just the Character (`helios-character` Standalone)
To run **only the 3D VRM character** with lightweight local chat, neural TTS lip-sync, 24 human poses, 6 posture styles, and the RL pose trainer—without starting `ai-router` (`:8000`):

```powershell
.\start_character_only.bat
# or inside helios-character/:
cd helios-character
.\start_character_only.bat
```

* Opens the standalone Character Viewer at **[http://localhost:8080?edition=character_only](http://localhost:8080?edition=character_only)**.
* You can also toggle between **⚡ Full Spec** and **🎭 Just the Character** live at any time using the Edition Switcher in the top-right corner of the viewer.

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
* **[Character Addon Guide](./helios-character/README.md)** — Character Protocol, modular VRM/Live2D renderers, and model manifest format.
* **[Mobile v2 Guide](./mobile_v2/README.md)** — Mobile app configuration, WebSocket bridge, and offline GGUF usage.
