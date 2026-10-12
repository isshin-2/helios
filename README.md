<div align="center">
  <img src="https://img.shields.io/badge/HELIOS-Ecosystem-00e5ff?style=for-the-badge&logo=openai" alt="HELIOS Ecosystem">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Ollama-Local_AI-orange?style=for-the-badge" alt="Ollama">
  <img src="https://img.shields.io/badge/Three.js-3D_VRM_Avatar-black?style=for-the-badge&logo=threedotjs" alt="3D VRM">
  <img src="https://img.shields.io/badge/Expo-React_Native-4630EB?style=for-the-badge&logo=expo" alt="Expo Mobile">
  <img src="https://img.shields.io/badge/Vite-Portfolio-646CFF?style=for-the-badge&logo=vite" alt="Vite Portfolio">
  <br><br>
  <strong>A high-performance, locally-hosted autonomous AI ecosystem uniting an intelligent multi-model router, an 8-agent coding swarm (Hikari), closed-loop computer control, an expressive neural TTS engine, an interactive 3D VRM cybernetic companion (Airi), an offline-capable mobile app, and a hardware-integrated engineering portfolio.</strong>
</div>

<br>

---

## 📂 Repository Structure

```text
HELIOS/
├── ai-router/               # Core AI Router, Hikari Swarm, Desktop UI & Computer Control (:8000)
│   ├── agents/              # 8-Agent Swarm (Planner, Architect, Coder, Tester, etc.) & ComputerAgent
│   ├── computer/            # Desktop automation primitives (actions, controller, safety, UI grounding)
│   ├── config/              # Voice profiles, pronunciation dictionaries, agent profiles
│   ├── core/                # Swarm state machine, model router, audio TTS engine, task contracts
│   ├── router/              # Fast prompt classification, SQLite vector memory (RAG)
│   ├── security/            # Zero-trust sandbox, permission governor, path firewall
│   ├── tests/               # Formal automated test suites (290+ tests)
│   │   └── manual/          # Ad-hoc integration & live scratch reproduction scripts
│   └── tools/               # Computer control, screen vision, shell, git, MCP client
├── helios-character/        # Airi — 3D VRM Cybernetic Avatar Presentation Companion (:8080)
│   ├── viewer/              # Three.js canvas, VRM expressions, animations, viseme lip-sync
│   └── ai_server.py         # WebSocket bridge & standalone character engine
├── helios-client/           # Client-Sided HELIOS: Desktop GUI, Hikari CLI & Device Sidecar
│   ├── cli.py               # Claude Code / Codex terminal console for remote server
│   ├── desktop.py           # Native PyQt5 WebEngine HUD with dynamic endpoint switcher
│   ├── sidecar.py           # Background agent bridging client shell, screen, & OS to server
│   └── api_client.py        # REST and WebSocket client library
├── mobile_v2/               # Expo / React Native Mobile Companion with Offline GGUF Fallback
├── portfolio/               # Cyberpunk Interactive Engineering Portfolio (Vite + React 19)
├── scripts/                 # Dedicated AI PC Workstation automation (WoL, server startup)
├── voices/                  # Neural voice reference audio & metadata (Airi, Helios)
├── .gitignore               # Unified repository ignore rules
├── hikari.bat               # 1-Click Launcher: Hikari Autonomous Coding Swarm CLI
├── setup.bat                # 1-Click Launcher: Unified Environment Setup
├── start_ai_pc.bat          # 1-Click Launcher: Dedicated AI PC Server (0.0.0.0:8000)
├── start_airi.bat           # 1-Click Launcher: Airi 3D Companion (connects to AI PC/localhost)
├── start_character_only.bat # 1-Click Launcher: Standalone 3D Character (No :8000 required)
├── start_helios.bat         # Interactive Master Launcher (Menu for Core, Hikari, Airi, Client, Full Spec)
├── start_helios_client.bat  # 1-Click Launcher: HELIOS Client (GUI, CLI, Sidecar for remote server)
└── start_helios_full_spec.bat # 1-Click Launcher: Full Spec (Core :8000 + Airi :8080)
```

| Module | Description | Primary Tech Stack |
| :--- | :--- | :--- |
| **[`ai-router/`](./ai-router)** | Core backend server, intelligent LLM router, vector memory (SQLite RAG), zero-trust sandbox, closed-loop computer control, neural TTS pipeline, and PyQt5 desktop overlays. | Python 3.11+, FastAPI, Uvicorn, Ollama, SQLite, PyQt5, Kokoro, GPT-SoVITS |
| **[`helios-client/`](./helios-client)** | Lightweight client subsystem running on user's laptop/workstation while HELIOS Core is hosted remotely. Includes Desktop GUI, Hikari CLI, and Sidecar device daemon. | Python 3.11+, PyQt5, WebSockets, HTTPX, Rich, PyAutoGUI, MSS |
| **[`helios-character/`](./helios-character)** | **Airi** — 3D VRM avatar presentation companion (`Helios_Airi.vrm`) driven by the Character Protocol (`/ws/character`) with procedural humanization, 30-FPS viseme lip-sync, and RL pose engine. | FastAPI, WebSockets, Three.js, VRM, Live2D |
| **[`mobile_v2/`](./mobile_v2)** | Cross-platform mobile app featuring the interactive AI Core HUD, real-time WebSocket streaming to HELIOS Core, and offline on-device GGUF execution. | React Native 0.86, Expo 57, TypeScript, `llama.rn` |
| **[`portfolio/`](./portfolio)** | Production-grade cyberpunk engineering portfolio showcasing hardware schematics, firmware architectures, and interactive digital twins. | React 19, Vite, Lucide Icons |
| **[`voices/`](./voices)** | Studio reference audio, phoneme mappings, and metadata for Airi and Helios neural voice synthesis. | YAML, WAV, OGG |
| **[`scripts/`](./scripts)** | Workstation scripts for headless UDP Wake-on-LAN (WoL), model verification, and high-throughput server hosting. | Windows Batch, PowerShell |
| **Hikari** | **Hikari (`hikari.bat`)** — Autonomous multi-agent coding CLI (Claude Code & Codex style) featuring the HELIOS Black Hole ASCII HUD, git worktree isolation, automated pytest verification, and rollback safety. | Python, Rich, Git Worktrees, Pytest |

---

## 🚀 Quick Launch (Universal Cross-Platform)

HELIOS runs seamlessly on **Windows, macOS, and Linux** across any hardware configuration (from 8 GB laptops to 64 GB RTX workstations and Apple Silicon Macs):

### 🌟 Universal Python CLI (Runs Everywhere)
```bash
python helios.py          # Interactive master launcher menu (Windows, macOS, Linux)
python helios.py core     # Start HELIOS Core AI Router (:8000)
python helios.py hikari   # Launch Hikari Autonomous Coding Swarm CLI
python helios.py full     # Launch Full Spec: Core (:8000) + Airi 3D Avatar (:8080)
python helios.py airi     # Launch Airi 3D Companion (:8080) standalone
python helios.py client   # Launch HELIOS Remote Client (GUI / CLI / Sidecar)
python helios.py status   # System diagnostics & hardware tier telemetry
python helios.py test     # Run verified core test suite
```

### ⚡ 1-Click Platform Launchers

| Command (Windows) | Command (macOS / Linux) | Mode | Description |
| :--- | :--- | :--- | :--- |
| **`start_helios.bat`** | **`./start_helios.sh`** | **Interactive Master Menu** | Choose between Core Server, Client Suite, Hikari CLI, Full Spec, or Airi Standalone. |
| **`start_helios_client.bat`** | **`./start_helios_client.sh`** | **Client Mode Suite** | Connects to remote HELIOS server: Desktop GUI, Hikari CLI, and Sidecar Daemon. |
| **`hikari.bat`** | **`./hikari.sh`** | **Hikari Coding CLI** | Multi-agent autonomous coding terminal (Claude Code style) with Black Hole HUD. |
| **`start_helios_full_spec.bat`** | **`./start_helios_full_spec.sh`** | **Full Spec Ecosystem** | Launches Core AI Router (`:8000`) and Airi 3D Companion (`:8080`) simultaneously. |
| **`start_airi.bat`** | **`./start_airi.sh`** | **Airi 3D Companion** | Launches the 3D VRM companion; automatically connects to AI PC or localhost. |
| **`start_character_only.bat`** | **`./start_airi.sh`** | **Standalone Character** | Lightweight 3D VRM companion with standalone local chat — no `:8000` stack needed. |
| **`setup.bat`** | **`./setup.sh`** | **Unified Setup** | Creates Python virtual environment and installs all backend dependencies. |
| **`portfolio/start_portfolio.bat`** | **`portfolio/start_portfolio.sh`** | **Engineering Portfolio** | Launches Vite dev server at `http://localhost:5174` and opens browser. |

---

## ✨ Core Architecture & Features

### 💻 1. Hikari Autonomous Coding Swarm (`hikari.bat`)
* **Event Horizon Visual HUD**: Relativistic Black Hole ASCII display with real-time accretion disk telemetry badges and token throughput indicators.
* **8-Agent Software Engineering Swarm**:
  1. `Planner`: Task decomposition, dependency mapping, and milestone generation.
  2. `Architect`: System design, module boundaries, and interface contracts.
  3. `Repo Mapper`: AST code indexing, symbol references, and topological graph analysis.
  4. `Coder`: TDD code implementation with deterministic tool call constraints.
  5. `Tester`: Test suite execution (`pytest`), failure extraction, and regression checking.
  6. `Repair Agent`: Targeted patch generation with root-cause analysis loops.
  7. `Reviewer`: Clean-code quality audit and architectural compliance verification.
  8. `Security Reviewer`: Vulnerability scanning, AST sanitization, and path traversal auditing.
* **Git Worktree Isolation**: Safely develops code inside isolated `.helios_worktrees`—the main working branch remains pristine until tests pass 100%.
* **Interactive CLI Commands**: View diffs (`/diff`), trigger reviews (`/review`), run tests (`/test`), inspect VRAM allocations (`/models`), or rollback changes (`/rollback`).

### 🧠 2. AI Router & Dedicated AI PC Workstation (`ai-router`)
* **Dual Workstation Capability**:
  - **Localhost Mode**: Self-contained inference on laptop hardware.
  - **Dedicated AI PC Workstation**: Offloads inference to a dedicated node (**RTX 5060 Ti 16 GB VRAM + 64 GB DDR5 RAM**) on LAN (`192.168.100.254:8000`).
  - **Auto Wake-on-LAN**: Headless UDP magic packets automatically wake the AI PC when tasks arrive.
* **Concurrent Multi-Model Pool**: Concurrent execution across `qwen2.5-coder:32b`, `qwen2.5-coder:14b`, `qwen3.5:9b`, and `phi4:mini` without OOM faults.
* **Hardware Arbitrator & `llmfit`**: Dynamically profiles RAM/VRAM to right-size quantization levels and context windows.
* **Zero-Trust Security Sandbox**: File access confined to explicit workspaces; destructive shell commands require interactive human approval.
* **SQLite Vector Memory (RAG)**: Persistent semantic memory across sessions stored in `ai-router/helios.db`.

### 🖥️ 3. Closed-Loop Computer Control (`ai-router/computer`)
* **Desktop Automation**: Full keyboard, mouse, window, and process control through `ComputerAgent` and `ComputerControlTool`.
* **Multi-Layer UI Grounding**: Screen capture via MSS/ImageGrab, coordinate bounding, and UI Automation (UIA) tree inspection.
* **Safety & Emergency Controls**: Fail-safe mouse movements, bounding box enforcement, protected process isolation, and instant emergency stop triggers.

### 🎙️ 4. Expressive Neural TTS Engine (`ai-router/core/audio/tts`)
* **Dual-Backend Synthesis**: High-speed **Kokoro ONNX** for conversational responses + **GPT-SoVITS** for zero-shot voice cloning.
* **Text Normalizer**: Strips markdown, emojis, JSON artifacts, and converts technical units (e.g. `3.3V` → "three point three volts", `400kHz` → "four hundred kilohertz").
* **Engineering Pronunciation Dictionary**: Resolves technical acronyms and domain terms defined in `config/pronunciation.yaml`.
* **Prosody Engine & Speech Planner**: Dynamic speech pacing, emotion matching (`happy`, `serious`, `curious`, `neutral`), sentence-level streaming segmentation, and safety overrides.
* **Audio Processor**: DC offset removal, 70Hz high-pass filter, soft limiting, and real-time 30-FPS viseme envelope generation for lip-sync.

### 🎭 5. Airi 3D Cybernetic Companion (`helios-character`)
* **3D Techwear VRM Model (`Helios_Airi.vrm`)**: Real-time rendering via Three.js with full body kinematics, facial expressions, and spatial movement.
* **Decoupled Architecture**: Connects to HELIOS Core over `/ws/character` via the Character Protocol; HELIOS operates uninhibited even if the character UI is closed.
* **Procedural Humanization**: Micro-movements, eye blinks, breathing cycles, and emotion transitions driven directly by event stream telemetry.
* **Pose & Movement Engine**: 24 reference human poses, 6 posture styles, and reinforcement learning pose policy (`models/helios_rl_pose_policy.pkl`).

### 📱 6. Mobile Companion (`mobile_v2`)
* **Tensura Cyberpunk HUD**: Redesigned dark-mode interface (`#090a10` abyss, `#00e5ff` cyan, `#ffb700` amber) with live connection badge and real-time latency ping indicator.
* **Interactive AI Core Black Hole HUD**: Visualizes system states (`idle`, `listening`, `thinking`, `speaking`, `amber`) synchronized live with the core server via bidirectional JS bridge.
* **4-Tab Command Deck**:
  1. `AI Core HUD`: Real-time state visualizer and operational telemetry pills.
  2. `Terminal`: Streaming chat with LLM metadata tags, quick command chips (`/status`, `/models`, `/test`), and execution cancellation.
  3. `Swarm & Nodes`: Live cards for the 8-agent swarm, dedicated AI PC Workstation stats, and Airi 3D companion audio telemetry.
  4. `Nodes & Settings`: Dynamic endpoint configuration, live Ping tester, autonomous mode switch, and on-device GGUF model selector.
* **Human-in-the-Loop Security Approvals**: Interactive modal intercepts high-impact tool execution requests with immediate Approve/Deny buttons over WebSockets.
* **Offline Fallback**: Runs on-device local `.gguf` models with `llama.rn` when offline or out of LAN range.

### ⚡ 7. Cyberpunk Engineering Portfolio (`portfolio`)
* **Interactive Project Deck**: Showcases all embedded systems, robotics, and AI projects by Krithik Mahesh (@isshin-2).
* **Live Simulators**: AgriTech Rover telemetry deck, AquaPulse tank twin, and TEMPSENSE pharmaceutical monitor.

---

## 🧪 Testing & Validation

HELIOS includes a comprehensive automated test suite with over **290 unit and integration tests**:

```powershell
cd ai-router

# 1. Run the core architectural verification suite (Hardware, Sandbox, RAG, Swarm)
.\venv\Scripts\python.exe -m pytest tests/test_helios_core_suite.py

# 2. Run the neural TTS and audio processing test suite (17 tests)
.\venv\Scripts\python.exe -m pytest tests/test_tts_pipeline.py

# 3. Run the closed-loop computer control system tests
.\venv\Scripts\python.exe -m pytest tests/test_computer_system.py

# 4. Verify test discovery across the entire repository
.\venv\Scripts\python.exe -m pytest --collect-only
```

*All ad-hoc scratch scripts and live test fixtures are safely isolated in `ai-router/tests/manual/` to ensure zero noise during CI/CD execution.*

---

## 🛠️ Prerequisites & Installation

1. **[Python 3.11+](https://www.python.org/downloads/)** (Ensure **"Add python.exe to PATH"** is checked on Windows).
2. **[Ollama](https://ollama.com/download)** installed and running locally or on the AI PC.
3. **[Node.js 18+](https://nodejs.org/)** *(required for `mobile_v2` and `portfolio`)*.

### Setup in 1 Step:

- **Any OS (Universal):**
  ```bash
  python helios.py setup          # Interactive configuration wizard
  python helios.py setup --quick  # 1-second auto-detected setup
  ```
- **Windows:** Double-click **`setup.bat`**, or run `.\setup.bat`
- **macOS / Linux:** Run `chmod +x *.sh && ./setup.sh`

HELIOS automatically detects your hardware (RAM, VRAM, Apple Silicon, CPU), probes local and cluster nodes, configures sensible defaults into `.env`, creates the virtual environment, and installs dependencies.

---

## 📖 Deep-Dive Documentation

* **[AI Router Architecture](./ai-router/ARCHITECTURE.md)** — Hardware tiers, zero-trust sandbox, and self-modification pipeline.
* **[AI Router Guide](./ai-router/README.md)** — Backend configuration, API routes, and PyQt5 overlay controls.
* **[Character Addon Guide](./helios-character/README.md)** — Airi 3D VRM model setup, manifest format, and WebSocket protocol.
* **[Mobile v2 Guide](./mobile_v2/README.md)** — React Native mobile setup, Expo configuration, and offline GGUF inference.
* **[Portfolio Guide](./portfolio/README.md)** — Engineering portfolio architecture, hardware pinouts, and simulators.
