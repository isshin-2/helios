<div align="center">
  <img src="https://img.shields.io/badge/HELIOS-Ecosystem-00e5ff?style=for-the-badge&logo=openai" alt="HELIOS Ecosystem">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Ollama-Local_AI-orange?style=for-the-badge" alt="Ollama">
  <img src="https://img.shields.io/badge/Three.js-3D_VRM_Avatar-black?style=for-the-badge&logo=threedotjs" alt="3D VRM">
  <img src="https://img.shields.io/badge/FastAPI-REST_%26_WS-009688?style=for-the-badge&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Vite-Portfolio_%26_Site-646CFF?style=for-the-badge&logo=vite" alt="Vite">
  <br><br>
  <strong>A sovereign, locally-hosted autonomous AI ecosystem uniting an intelligent multi-model router, an isolated 8-agent coding swarm (Hikari), closed-loop computer vision & control (VLA), an expressive neural TTS engine, interactive dual 3D VRM presentation companions (Airi & Ren), zero-leak biometric security, and modular standalone addons.</strong>
</div>

<br>

---

## 🏛️ Ecosystem Overview & Sovereign Triad

HELIOS is architected around strict process and data isolation across three core pillars:

```text
                               ┌─────────────────────────────────────────┐
                               │           ANTIGRAVITY CLI /             │
                               │      UNIFIED SLASH DISPATCHER           │
                               └────────────────────┬────────────────────┘
                                                    │
                 ┌──────────────────────────────────┼──────────────────────────────────┐
                 │                                  │                                  │
                 ▼                                  ▼                                  ▼
      ┌──────────────────────┐           ┌──────────────────────┐           ┌──────────────────────┐
      │   HELIOS CORE AI     │           │    HIKARI CODING     │           │    SOLSTICE / AIRI   │
      │   ROUTER (:8000)     │           │    SWARM (:8001)     │           │    AVATARS (:8080/82)│
      ├──────────────────────┤           ├──────────────────────┤           ├──────────────────────┤
      │ • Multi-Model RAG    │           │ • 8-Agent Swarm      │           │ • Airi (Wolf-cut)    │
      │ • Zero-Trust Sandbox │           │ • Git Worktrees      │           │ • Ren (Brother)      │
      │ • VLA Computer Ctrl  │           │ • Pytest Verifier    │           │ • Dual Twin Synergy  │
      │ • Neural Audio / TTS │           │ • Isolated hikari.db │           │ • Isolated solstice.db│
      │ • SQLite helios.db   │           │ • Addon in /projects │           │ • Three.js + WebSockets│
      └──────────────────────┘           └──────────────────────┘           └──────────────────────┘
                 ▲                                                                     ▲
                 └─────────────────── HMAC-SHA256 BridgeGuard ─────────────────────────┘
                                       (Zero-Trust IPC Isolation)
```

1. **HELIOS Core Router (`:8000`)**: Core intelligence hub with prompt classification, model pooling, SQLite vector memory (RAG), zero-leak biometric auth, and Vision-Language-Action (VLA) desktop control.
2. **Hikari Coding Swarm (`:8001`)**: Autonomous multi-agent engineering terminal (Claude Code & Codex style) operating inside isolated git worktrees with strict regression verification.
3. **Solstice Companion Engine & 3D WebGL Studio (`:8082` / `:8080`)**: High-fidelity Three.js presentation avatars (Airi & Ren) with PBR rendering, 30-FPS viseme lip-sync, dynamic state colors, and the interactive Prop & Body Pose Studio.

---

## 📂 Repository Structure

```text
HELIOS/
├── ai-router/               # Core AI Router, VLA Computer Control, Neural TTS (:8000)
│   ├── agents/              # Core Agent Swarm & ComputerAgent (Desktop vision/actions)
│   ├── computer/            # Automation primitives, safety governor, coordinate grounding
│   ├── config/              # Voice profiles, pronunciation dictionaries, agent configs
│   ├── core/                # State machine, hardware governor, audio engine, task contracts
│   ├── router/              # Fast prompt classification, SQLite vector memory (RAG)
│   ├── security/            # Zero-trust sandbox, permission governor, path firewall
│   ├── static/              # Web UI HUD & Developer Connectors Studio Playground
│   └── tests/               # Formal test suites (Core, VLA, Computer Control, TTS)
├── helios-character/        # Airi & Ren 3D VRM WebGL Experience & Pose Studio (:8080)
│   ├── viewer/              # Three.js canvas, PBR 3D props, dual-twin kinematics, Sol Studio
│   ├── training/            # 4-Head Neural MLP & RL human pose policy trainers
│   └── ai_server.py         # Standalone character protocol engine & WebSocket bridge
├── helios-client/           # Client Subsystem (Laptop/Workstation to Remote AI Router)
│   ├── cli.py               # Remote CLI client
│   ├── desktop.py           # Native PyQt5 WebEngine HUD
│   └── sidecar.py           # Background agent bridging local OS, screen, and shell
├── config/                  # Declarative connector manifests, bridge rules, and custom profile
│   ├── connectors.manifest.json  # Registered external tool connectors
│   └── custom_profile.json       # Interactive setup preferences & port configuration
├── data/                    # Physically segregated SQLite databases (helios.db, hikari.db, solstice.db)
├── docs/                    # Architecture documentation & Living System Audit (SSoT)
│   ├── CORE_TWIN_ARCHITECTURE.md # Sovereign Triad specification & IPC boundaries
│   └── SYSTEM_AUDIT.md           # Real-time hardware tiers, port topology, and advisories
├── portfolio/               # Cyberpunk Interactive Engineering Portfolio (React 19 + Vite)
├── scripts/                 # Bootstrap, hardware scan, voice biometrics, audit & launchers
│   ├── bootstrap.py         # Zero-friction installer & interactive configuration wizard
│   ├── launch_3d_experience.py # 3D Avatar & Sol Studio launcher
│   ├── run_audit.py         # Living System Audit scanner
│   └── verify_voice.py      # Speaker verification & fallback PIN calibration
├── voices/                  # Neural voice reference audio & metadata (Airi, Helios)
├── helios.bat               # Antigravity Slash Command CLI dispatcher
├── helios_cmd.py            # Unified CLI implementation (/setup, /audit, /custom, etc.)
├── hikari.bat               # Direct launcher: Hikari Autonomous Coding Swarm
├── setup.bat                # 1-Click Zero-Friction Bootstrap & Hardware Provisioner
├── start_helios_dev.bat     # 1-Click Developer Edition: Core Router (:8000) + Hikari (:8001)
├── start_site.bat           # 1-Click Official Project Website Launcher (:5175)
└── start_solstice.bat       # 1-Click User Edition: Solstice Companion (:8082) + 3D Avatar (:8080)
```

### 🧩 Decoupled Modular Addons in `C:\projects\`
To keep HELIOS Core lightweight and maintain independent data stores, supplementary engines are cleanly decoupled:
* **`C:\projects\hikari-addon`**: Standalone Hikari coding swarm engine (`:8001`, `data/hikari.db`, `start_hikari_addon.bat`).
* **`C:\projects\solstice-addon`**: Standalone Solstice companion avatar engine (`:8082`, `data/solstice.db`, `start_solstice_addon.bat`).
* **`C:\projects\mobile-addon`**: React Native / Expo mobile companion with offline GGUF fallback (`start_mobile_addon.bat`).
* **`C:\projects\helios-site`**: Official React 19 + Vite project landing website (`:5175`, `start_site.bat`).

---

## ⚡ Quick Launch & Operational Slash Commands

Launch any mode directly using **`helios <command>`** or double-clicking the one-click launchers:

### 🌟 Antigravity Operational Slash Commands
| Command | Action | Description |
| :--- | :--- | :--- |
| **`helios /dev`** | `start_helios_dev.bat` | Launches **Developer Edition**: Core Router (`:8000`) + Hikari Coding Swarm (`:8001`). |
| **`helios /user`** | `start_solstice.bat` | Launches **User Edition**: Solstice Companion Engine (`:8082`) + 3D Avatars (`:8080`). |
| **`helios /studio`** | `launch_3d_experience.py --studio` | Opens **Sol Studio** (3D Prop & Biomechanical Body Pose Tuner) at `http://localhost:8080/?studio=true`. |
| **`helios /custom`** | `bootstrap.py --custom` | Launches interactive **Customization Wizard** (profiles, models, ports, biometrics). |
| **`helios /audit`** | `run_audit.py` | Scans workspace, checks IPC boundaries, and refreshes [`docs/SYSTEM_AUDIT.md`](./docs/SYSTEM_AUDIT.md). |
| **`helios /setup`** | `bootstrap.py` | Runs idempotent hardware probe, Ollama provisioning, and model download check. |
| **`helios /test-isolation`** | `pytest test_isolation.py` | Validates strict physical memory and database separation across engines. |
| **`helios /verify-voice`** | `verify_voice.py` | Calibrates speaker verification centroid embeddings and fallback PIN security. |
| **`helios /site`** | `start_site.bat` | Boots the official project website at `http://localhost:5175`. |
| **`helios /mobile`** | `start_phone.bat` | Launches the React Native / Expo mobile companion. |
| **`helios /hikari`** | `start_hikari_addon.bat` | Boots the standalone Hikari Coding Swarm engine (`:8001`). |
| **`helios /solstice`**| `start_solstice_addon.bat`| Boots the standalone Solstice companion engine (`:8082`). |
| **`helios /character-only`**| `start_character_only.bat`| Boots standalone 3D VRM presentation companion (`:8080`) without AI router. |
| **`helios /astraea`** | `start_astraea.bat` | Boots Astraea gaming operative daemon (`:8085`). |

> [!TIP]
> **Running from any Terminal / Command Prompt:**
> Typing `helios` in your command prompt displays the unified Antigravity command dispatcher. Any operational mode or addon can be triggered directly with `helios /<command>` (e.g., `helios /dev`, `helios /user`, `helios /hikari`, `helios /audit`).
> If an addon is not installed or missing from `C:\projects\<addon>`, `helios` will exit cleanly with an informative error displaying the expected path.

### 🧩 Modular Addon Launch & Control Commands
Run standalone microservices and peripheral addons directly from their project directories, via one-click batch scripts, or via `helios /<addon>`:

| Addon | Directory | Unified CLI / Script | Port | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Hikari Swarm Engine** | `C:\projects\hikari-addon` | `helios /hikari`<br>*(or `start_hikari_addon.bat`)* | `:8001` | Standalone 8-agent autonomous software engineering swarm & WebSocket backend. |
| **Hikari Swarm CLI** | `C:\projects\hikari-addon` | `hikari.bat` | — | Interactive terminal console (Claude Code & Codex style) operating in isolated worktrees. |
| **Solstice Avatar Engine** | `C:\projects\solstice-addon` | `helios /solstice`<br>*(or `start_solstice_addon.bat`)* | `:8082` | Standalone presentation companion engine, state synchronization, and avatar telemetry. |
| **Solstice 3D Companion** | `C:\projects\solstice-addon` | `helios /character-only`<br>*(or `start_character_only.bat`)* | `:8080` | Lightweight standalone 3D WebGL presentation companion (Airi & Ren) without `:8000`. |
| **Mobile Companion (Expo)**| `C:\projects\mobile-addon` | `helios /mobile`<br>*(or `start_mobile_addon.bat`)* | `:8081` | Cross-platform React Native / Expo companion with real-time Hikari stream and GGUF fallback. |
| **Official Project Website** | `C:\projects\helios-site` | `helios /site`<br>*(or `start_site.bat`)* | `:5175` | Official React 19 + Vite cyberpunk documentation and interactive landing portal. |
| **Astraea Gaming Operative** | `C:\projects\astraea-addon` | `helios /astraea`<br>*(or `start_astraea.bat`)* | `:8085` | Autonomous gaming operative with low-latency controller emulation & visual state analysis. |

---

## ✨ Core Features & Architectural Invariants

### 🧠 1. Intelligent AI Router & Hardware Governor (`ai-router`)
* **Dynamic Hardware Profiling**: Classifies host system into **Tier 1** (High-Performance NVIDIA GPU Workstation / RTX GPU), **Tier 2** (Balanced Mid-Range), or **Tier 3** (Budget Integrated Graphics $\le 16\text{ GB}$ RAM).
* **Automatic Budget Downgrades**: On constrained hardware (e.g. Intel Iris Xe), the Governor automatically:
  - Caps 3D WebGL rendering to 30 FPS with reduced shadow passes.
  - Limits vision models to lightweight options (`moondream:1b` / `qwen2.5vl:3b`) with 540p capture downscaling.
  - Restricts swarm execution to sequential runs to prevent OS memory thrashing.
  - Routes TTS to low-overhead Kokoro ONNX.
* **SQLite Vector Memory (RAG)**: Persistent semantic memory across sessions stored in `data/helios.db`.
* **Zero-Leak Security & Biometric Gate**: Local regex and token scrubbers filter API keys, secrets, and PII. Local 192-dim speaker verification verifies authorized voice commands with Argon2-hashed fallback PIN protection.

### 💻 2. Hikari Autonomous Coding Swarm (`hikari.bat`)
* **Event Horizon Visual HUD**: Relativistic Black Hole terminal display with real-time throughput metrics.
* **8-Agent Software Swarm**:
  `Planner` → `Architect` → `Repo Mapper` → `Coder` → `Tester` → `Repair Agent` → `Reviewer` → `Security Reviewer`.
* **Git Worktree Isolation**: Executes code changes in isolated `.helios_worktrees`—the main working tree remains untouched until tests pass 100%.

### 🖥️ 3. Vision-Language-Action (VLA) Closed-Loop Computer Control (`ai-router/computer`)
* **Desktop Automation**: Direct keyboard, mouse, window, and process orchestration via `ComputerAgent`.
* **Grounding & Safety**: Coordinate bounding enforcement, safe failsafe margins, protected process isolation, and instantaneous emergency stop abort triggers.

### 🎙️ 4. Expressive Neural TTS Engine (`ai-router/core/audio/tts`)
* **Dual-Backend Synthesis**: High-speed **Kokoro ONNX** for instant responses + **GPT-SoVITS** for voice cloning.
* **Text Normalizer & Pronunciation Dictionary**: Strips markdown artifacts, expands technical engineering units (`3.3V` → "three point three volts", `400kHz` → "four hundred kilohertz"), and applies phonetic corrections from `config/pronunciation.yaml`.
* **Prosody & Real-Time Lip Sync**: Dynamic pacing, emotion matching (`happy`, `serious`, `curious`, `neutral`), and 30-FPS viseme envelope calculation.

### 🎭 5. Dual 3D VRM Presentation Companions & Sol Studio (`helios-character`)
* **Airi (`Helios_Airi.vrm`)**: Cybernetic wolf-cut female companion (1.68m, cyan `#00E5FF` eyes, cyber-butterfly companion prop).
* **Ren / Helios Twin (`Helios_Twin.vrm`)**: Tactical older brother operative (1.82m tall, tactical cargo techwear, SD-04 Ghosteye recon drone, MN-01 Cyber-Sight monocle HUD).
* **Dual Twin Synergy Mode**: Displays both Airi and Ren simultaneously on-screen with synchronized twin combat and briefing stances.
* **Dynamic State Material Transitions**: Outfits and irises dynamically modulate colors across AI Core states:
  - ⚫ **Idle** (`#2C3038` Charcoal / Calm Cyan-Slate)
  - 🔵 **Listening** (`#00E5FF` Bright Neon Cyan Pulse)
  - 🟡 **Thinking** (`#FFCC00` Radiant Gold / Amber Pulse)
  - 🔷 **Speaking** (`#3296FA` Electric Blue with audio amplitude modulation)
  - 🔴 **Error** (`#FF3B30` Alert Crimson)
* **Sol Studio (Prop & Body Pose Adjustment Suite)**:
  - Interactive slide-over modal for live 3D prop adjustment (X/Y/Z position, pitch/yaw/roll rotations, orbit paths, speed).
  - Biomechanical joint tuner for head, spine, arms, hands/wrists, and stance with twin isolation (zero overlap between Airi and Ren).
  - Persistent JSON calibration export and local storage caching.

### 🔌 6. Developer Connectors Studio (`ai-router/static/app.html`)
* **Declarative Manifest (`config/connectors.manifest.json`)**: Registered external connectors with structured input/output JSON schemas, timeout safeguards, and zero-trust sandboxing.
* **Web UI Connectors Studio**:
  - Live inventory of installed connectors with status badges.
  - Interactive boilerplate generator for scaffolding new Python `BaseConnector` tools.
  - Live Playground to test connector execution, inspect JSON payloads, and monitor latency in real time.

---

## 🧪 Testing & Verification

HELIOS includes comprehensive automated test suites verifying architectural isolation, connectors, TTS, and computer control:

```powershell
# 1. Run Architectural Memory & Database Isolation Suite (100% Passed)
.\ai-router\venv\Scripts\python.exe -m pytest tests/test_isolation.py -v

# 2. Run Developer Connectors Sandbox Suite
.\ai-router\venv\Scripts\python.exe -m pytest tests/test_connectors.py -v

# 3. Run Core AI Router Verification Suite
.\ai-router\venv\Scripts\python.exe -m pytest ai-router/tests/test_helios_core_suite.py

# 4. Run Neural TTS & Audio Pipeline Tests
.\ai-router\venv\Scripts\python.exe -m pytest ai-router/tests/test_tts_pipeline.py

# 5. Run Living System Audit & Governance Check
helios /audit
```

---

## 🛠️ Prerequisites & Zero-Friction Setup

1. **[Python 3.11+](https://www.python.org/downloads/)** (Ensure **"Add python.exe to PATH"** is checked on Windows).
2. **[Ollama](https://ollama.com/download)** installed and running locally on `:11434`.
3. **[Node.js 18+](https://nodejs.org/)** *(required for `portfolio` and `helios-site`)*.

### One-Click Setup:
```cmd
setup.bat
```
- **Automated Mode**: Detects GPU/VRAM/RAM tier, checks Ollama, downloads matched models, configures `.env`, builds the virtual environment, and installs dependencies.
- **Interactive Customization**: Run `setup.bat -c` or `helios /custom` to configure editions, ports, and models via an interactive wizard.

---

## 📖 Deep-Dive Documentation

* **[Living System Audit (SSoT)](./docs/SYSTEM_AUDIT.md)** — Hardware tiers, port topology, and advisories.
* **[Sovereign Triad Architecture](./docs/CORE_TWIN_ARCHITECTURE.md)** — Process isolation, HMAC-SHA256 BridgeGuard, and data boundaries.
* **[AI Router Architecture](./ai-router/ARCHITECTURE.md)** — Router internals, sandbox security, and model routing.
* **[Character Engine & Sol Studio](./helios-character/README.md)** — VRM models, Three.js shaders, props calibration, and WebSocket protocol.
* **[Engineering Portfolio](./portfolio/README.md)** — Hardware schematics, digital twins, and project showcase.
