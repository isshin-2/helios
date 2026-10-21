# HELIOS — System Architecture & Topology Spec

## 1. System Overview

HELIOS is an autonomous, privacy-first, locally-hosted AI operating environment featuring an integrated 8-agent swarm, 3D companion holodeck, Vision-Language-Action (VLA) computer control, and real-time neural speech synthesis.

The system dynamically partitions work between the **local host** (lightweight execution, low-latency control, speech, and safety gating) and a dedicated **NVIDIA PAIR GPU Node** (heavy 32B+ reasoning and vision models).

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       PRESENTATION & COMPANION                                   │
│  HELIOS Code (CLI/TUI)        │ Solstice 3D Hologram (:8080)       │ Astraea Gaming Operative (:8085)│
│  Tensura Desktop Overlay HUD  │ HELIOS Official Showcase (:5175)   │ Mobile Companion (:8081)         │
└────────────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                                 │ HTTP / WebSocket (ws://127.0.0.1:8000/ws)
                                                 ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               ai-router/main.py  (FastAPI :8000)                                 │
│                                                                                                  │
│   ┌───────────────────────────────┐  ┌──────────────────────────────┐  ┌──────────────────────┐  │
│   │    Conversation & Swarm       │  │   Dynamic Tier Governor      │  │  Zero-Trust Security │  │
│   │ - ConversationOrchestrator    │  │ - HardwareProfiler           │  │ - PermissionManager  │  │
│   │ - 15-State TaskStateMachine   │  │ - HardwareGovernor (Tier 1-3)│  │ - SecretRedactor     │  │
│   │ - Supervisor & TaskContract   │  │ - LLMFit Model Right-Sizer   │  │ - Offline Ed25519    │  │
│   │ - EventBus & CancellationToken│  │ - Memory Staging Watchdog    │  │   License Validator  │  │
│   └───────────────┬───────────────┘  └──────────────┬───────────────┘  └──────────┬───────────┘  │
│                   │                                 │                             │              │
│                   ▼                                 ▼                             ▼              │
│   ┌───────────────────────────────┐  ┌──────────────────────────────┐  ┌──────────────────────┐  │
│   │    Autonomous 8-Agent Swarm   │  │    Vision-Language-Action    │  │ Dual Neural Audio    │  │
│   │ - Planner & Architect         │  │ - ComputerController (OS)    │  │ - Kokoro-ONNX (Local)│  │
│   │ - Coder & Tester              │  │ - ScreenVision (mss.MSS)     │  │ - GPT-SoVITS (Custom)│  │
│   │ - Repair & Reviewer           │  │ - Hands-Off Desktop HUD Pill │  │ - TextNormalizer     │  │
│   │ - Security Reviewer           │  │ - Rolling Screenshot Pruner  │  │   (Mute Metadata)    │  │
│   │ - Computer Agent              │  │   (5-10 Buffer)              │  │ - 30 FPS Lip-Sync    │  │
│   └───────────────┬───────────────┘  └──────────────────────────────┘  └──────────────────────┘  │
└───────────────────┼──────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                  INFERENCE PROVIDER LAYER                                        │
│   ┌─────────────────────────────────────────┐         Failover        ┌───────────────────────┐  │
│   │ Primary: NVIDIA PAIR GPU Cluster Node   │ ──────────────────────> │ Local Host Fallback   │  │
│   │ (192.168.100.254:11434)                 │                         │ (127.0.0.1:11434)     │  │
│   │ RTX 5060 Ti 16GB + 64GB RAM             │  Dynamic Escalation     │ Intel Iris Xe / CPU   │  │
│   │ qwen2.5-coder:32b, qwen3-vl:8b          │ ──────────────────────> │ vLLM, FreeLLMAPI,     │  │
│   │ Automatic Wake-on-LAN + Circuit Breaker │                         │ Gemini, OpenRouter    │  │
│   └─────────────────────────────────────────┘                         └───────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Subsystems

### 2.1 Router, Swarm & State Engine (`ai-router/`)
- **`core/orchestrator.py` (`ConversationOrchestrator`)**: Main conversation loop. Classifies requests, delegates to subagents or tool execution loops, injects episodic memories, and streams responses over WebSockets.
- **`core/state_machine.py` (`TaskStateMachine`)**: Formal 15-state Finite State Machine with an explicit transition matrix:
  `IDLE -> ANALYZE -> PLAN -> ARCHITECT -> EXECUTE -> VERIFY -> REPAIR -> REVIEW -> SECURITY_REVIEW -> WAITING_APPROVAL -> WAITING_USER -> PAUSED -> FAILED -> FINALIZE -> COMPLETED`.
- **`core/supervisor.py` (`Supervisor`)**: Drives a structured `TaskContract` through the state machine, enforcing step budgets, recursion limits, and automated recovery loops.
- **`core/task_contract.py` (`TaskContract`)**: Pydantic contract encapsulating the task objective, required tools/capabilities, execution history, risk rating, and rollback points.

### 2.2 Hardware Profiler & Tier Governor
- **`core/hardware_profiler.py` (`detect_hardware`)**: Detects system architecture, CPU topology, physical RAM, GPU vendor (NVIDIA, Intel, AMD, Apple Metal), and active VRAM across Windows, macOS, and Linux.
- **`core/hardware_governor.py` (`HardwareGovernor`)**: Categorizes host hardware into operational tiers:
  - **Tier 1 (High Performance, Dedicated GPU >= 8GB VRAM)**: Full 8-agent swarm concurrency, native 1080p screen analysis, 60 FPS 3D VRM rendering.
  - **Tier 2 (Balanced, Dedicated GPU 4-6GB / 32GB RAM)**: 4 concurrent agents, 720p Lanczos screen captures, Kokoro-ONNX TTS.
  - **Tier 3 (Budget / Integrated Graphics, e.g. Intel Iris Xe 2GB VRAM, <= 16GB RAM)**: Throttles to sequential single-agent execution, downscaled 540p fast capture, lightweight models (`moondream:latest`, `qwen2.5:1.5b`), and reduced 3D rendering overhead.
- **`tools/llmfit_tool.py` (`LLMFitTool`)**: Integrates the native `llmfit` binary (`llmfit.exe`) to evaluate model fit, memory footprints, and tokens/sec estimates across GGUF/AWQ quantizations.

### 2.3 Provider Cluster & High Availability
- **`providers/pair.py` (`PairProvider`)**: Connects to the dedicated AI-PC GPU node (`192.168.100.254:11434`). Features:
  - Resilient 10.0s connection timeouts for Wi-Fi/LAN stability.
  - Automatic Wake-on-LAN (UDP magic packet to port 9).
  - 15-second circuit breaker preventing latency cascading.
  - Zero-downtime transparent failover to local Ollama (`127.0.0.1:11434`), FreeLLMAPI proxy (`:3001`), or cloud APIs (Gemini, OpenRouter).

### 2.4 Vision-Language-Action (VLA) & Computer Control
- **`computer/controller.py` & `tools/computer.py`**: Cross-platform desktop actuation (`mouse_move`, `mouse_click`, `mouse_drag`, `type_text`, `hotkey`, `open_app`).
- **`tools/screen_vision.py` (`ScreenVisionTool`)**: High-speed desktop screen capture via `mss.MSS()`. Features an automated rolling screenshot retainer capping disk storage to the 7 most recent images (5–10 frame buffer).
- **`static/media/autonomous_overlay.html`**: A non-intrusive cybernetic HUD banner (`HANDS OFF KEYBOARD & MOUSE — AI Control Active`) that triggers when physical actuation is active and automatically dismisses on completion.

### 2.5 Dual Neural Speech Pipeline
- **`core/audio/tts/`**:
  - **Kokoro-ONNX**: Local, ultra-low latency CPU/iGPU speech synthesis.
  - **GPT-SoVITS**: High-fidelity custom voice cloning.
  - **`text_normalizer.py`**: Audio filtering engine that strips code blocks, bracket coordinate lists (`[120, 450, 200, 600]`), tool JSON outputs, and system metadata notes (`[System Note: ...]`) to ensure clean speech output.
  - **Viseme Extraction**: Delivers 30 FPS facial blendshape packets to the 3D VRM companion over WebSocket.

---

## 3. Decoupled Addon Topology

| Project Directory | Purpose & Tech Stack | Network Port |
| :--- | :--- | :--- |
| **`ai-router/`** | Core FastAPI backend, Swarm Orchestrator, VLA, SQLite DB | `:8000` |
| **`solstice-addon/`** / **`helios-character/`** | Airi & Ren 3D VRM companion holodeck, Posing Studio (Three.js) | `:8080` |
| **`astraea-addon/`** | Subfunction ASTRAEA Autonomous Gaming Operative (Chiaki / HSR) | `:8085` |
| **`mobile-addon/`** / **`mobile_v2/`** | React Native / Expo companion with Hikari terminal streaming | `:8081` |
| **`helios-site/`** | Official HELIOS showcase website (React 19 + Vite) | `:5175` |
| **`portfolio/`** | Interactive cyberpunk engineering portfolio | `:5174` |
| **`PAIR AI-PC`** | Remote NVIDIA workstation cluster daemon (Ollama/vLLM) | `:11434` / `:14321` |

---

## 4. Database & Persistence Layer (`ai-router/db.py`)

SQLite database (`ai-router/helios.db`) utilizing additive migrations:
- `users` & `sessions`: User identity and conversation sessions.
- `messages`: Structured message histories and role annotations.
- `memories` & `core_memory`: Dynamic long-term user facts and persistent system personas.
- `audit_log`: Zero-trust security logs for tool invocations, shell commands, and file edits.
- `task_checkpoints`: Serialized `TaskContract` states for crash recovery and checkpoint rollbacks.
- `episodic_memory`: Contextual summaries of historical task executions.
- `license_state`: Cryptographic record of offline Ed25519 license validation.
