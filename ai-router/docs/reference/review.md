# HELIOS AI Project Review and Analysis

## Overview
HELIOS is an advanced, locally-hosted AI routing orchestrator and personal assistant system. It acts as an intelligent proxy connecting dynamic user interfaces (Desktop Web UI, Mobile Voice PWA, and a Desktop Siri-like Overlay) to a suite of local Large Language Models (managed by Ollama) and sandboxed system tools. Its core design emphasizes strict security (Zero-Trust sandbox), intelligent model routing based on task complexity, persistent vector memory, active memory management to operate efficiently on limited hardware, and a highly responsive local voice pipeline.

## Scripts to Main Architecture

HELIOS uses several entry points and utility scripts that tie into the core orchestration:

*   **`start.bat` / `start.sh`**: The primary bootstrap scripts. They automatically generate the isolated Python Virtual Environment (`venv`), install dependencies from `requirements.txt`, and launch `main.py`. This ensures HELIOS runs predictably regardless of the host machine's global Python state.
*   **`main.py`**: The central FastAPI application server. It serves the REST endpoints and WebSockets, initializes the core `Orchestrator`, and spins up background daemons for the STT (Speech-To-Text) microphone loops and TTS (Text-To-Speech) engines.
*   **`cli.py`**: A command-line interface alternative to the web server, allowing developers to interact with the HELIOS routing and memory engine directly through terminal inputs for rapid testing and debugging.
*   **`patch_google_overlay.py` / `scripts/ui_overlay.py`**: Scripts responsible for rendering the "Siri-like" transparent desktop widget. The STT microphone loop in `core/audio/stt/google.py` spawns `ui_overlay.py` as a detached subprocess the moment it detects a wake word, providing instant visual feedback to the user without blocking the main event loop.

## Hardware Constraints & Performance (Budget Mode)

HELIOS was specifically architected to run on tightly constrained, consumer-grade hardware (targeting 8GB shared RAM, no dedicated VRAM). To achieve this, it employs extreme memory management strategies:

### 1. VRAM/RAM Eviction & Timeout Management
*   **Aggressive Offloading**: The system constantly polls `127.0.0.1:11434/api/ps` to monitor Ollama's memory footprint. If the system is constrained, `models/manager.py` proactively unloads inactive models before initializing a new one. 
*   **Budget Mode `keep_alive`**: Large models (like `qwen2.5:7b` - ~5GB) consume too much memory to stay resident indefinitely. Budget Mode sets `keep_alive` to `"2m"`—a careful compromise that keeps the model warm for immediate follow-up questions during a conversation, but forcibly evicts it to free up RAM if the user walks away.
*   **Extended Connection Timeouts**: Loading a massive 5GB LLM from an HDD or slow SSD into system RAM can take upwards of 160 seconds. The internal `httpx` HTTP clients and testing scripts are configured with massive timeouts (300-500 seconds) to prevent TCP connection drops and `asyncio.CancelledError` chain collapses during these long cold-boots.

### 2. Audio Pipeline Optimization
*   **Wake-Word Efficiency**: Instead of streaming continuous audio to a cloud provider or a heavy local transformer, HELIOS uses an ultra-lightweight `Vosk` acoustic model. It runs endlessly in the background on the CPU with near-zero performance penalty.
*   **TTS Latency**: Heavy diffusion-based text-to-speech models (like VibeVoice or StyleTTS2) require >3GB of RAM, which would crash the system if run alongside a 5GB LLM on an 8GB machine. HELIOS utilizes `Kokoro-ONNX` (~80MB footprint) natively on the CPU. It dynamically chunks sentences by punctuation (commas, periods) and streams the audio instantly, aggressively minimizing "Time-To-First-Speech" (TTFS) latency without starving Ollama of memory.

## Hardware Benchmarking & Testing

To properly test HELIOS on constrained hardware, developers should monitor the following telemetry and endpoints:

*   **Time-To-First-Token (TTFT)**: The internal `stream_generator` explicitly logs TTFT in milliseconds. On budget hardware (HDD/slow SSD), TTFT on a cold boot of a 5GB model will often exceed 100,000ms. Subsequent "warm" queries within the `2m` keep-alive window should drop to <800ms.
*   **Ollama `/api/ps` Telemetry**: Use this endpoint to observe active memory mapping. `models/manager.py` relies on this to determine if the host RAM is saturated before dispatching new model loads.
*   **Audio Pipeline Latency**: When testing the Voice PWA or Desktop overlay, hardware testers should measure the gap between the Wake Word trigger ("Helios") and the UI overlay instantiation. Because `Vosk` runs locally on the CPU, this gap should remain <200ms regardless of GPU load.

## Key Components

### 1. The Request Pipeline & Orchestration (`core/orchestrator.py`)
- **Event Bus (`core/events.py`)**: An internal publish-subscribe mechanism handles decoupled communication between components.
- **Request Cancellation**: Fully implemented LLM request abortion mechanisms via HTTP endpoints to allow instant voice barge-ins without orphaned GPU processing.

### 2. Intelligent Routing & Classification (`outer/classifier.py`)
- The router maps queries to predefined roles defined in `config.py` (e.g., reasoning, coding, general, vision), utilizing fallback chains if a specific model isn't available.

### 3. Zero-Trust Sandbox & Security (`security/permissions.py`)
- **Path Resolution**: Enforces strict access boundaries against user-approved allowed_directories.
- **Human-in-the-Loop**: High-risk actions halt the pipeline and dispatch an approval_request to the frontend.

### 4. Persistent Vector Memory & Context (`outer/memory.py`, `db.py`)
- Extracts and persists factual information into a local SQLite database (`helios.db`) utilizing vector embeddings (nomic-embed-text).

## Future Optimizations & Improvements

While HELIOS is heavily optimized for an 8GB RAM ceiling, there are several architectural paths to further enhance performance and capability:

### 1. Performance Optimizations
*   **Aggressive Quantization**: Defaulting to lower precision (Q3_K_M or Q4_K_M) GGUF models. A Q4 `qwen2.5:7b` requires significantly less RAM than a Q8 or FP16, heavily reducing cold-boot times and memory swapping on standard HDDs/SSDs.
*   **Semantic Request Caching**: Implementing a lightweight semantic cache (e.g., using `nomic-embed-text` + SQLite) to intercept repeated or highly similar queries. If a user asks a similar question, HELIOS can bypass the LLM inference entirely and instantly return the cached answer.
*   **Asynchronous Memory Consolidation**: Moving vector DB summarization and memory embedding entirely to background idle periods (when the user is asleep or away) rather than doing it immediately after a conversation, freeing up CPU cycles during active use.

### 2. System Improvements
*   **Multi-Agent Coordination**: Upgrading the router to allow parallel execution. Instead of passing a query to a single model, HELIOS could spawn a "Coder" model and a "Reviewer" model concurrently, having them synthesize a final answer before pushing it to the TTS pipeline.
*   **Native UI Overlays**: Migrating the current Python `win32gui` / `ctypes` desktop overlay to a compiled, native language (like Rust or C++) to further shave off Python runtime overhead and achieve sub-10ms UI render times.
*   **Advanced Noise Filtering (VAD)**: Upgrading the STT loop to use advanced noise-canceling Voice Activity Detection (like WebRTC VAD or RNNoise) to aggressively filter out background television or music, reducing false-positive Wake Word triggers.

## Required Technical Specifications Checklist

*   [x] **Host Environment**
    *   OS: Windows 10/11 (Primary), macOS/Linux (Secondary support via `start.sh`)
    *   Hardware Minimums: 8GB RAM shared, Quad-Core CPU
    *   Runtime: Python 3.10+, isolated Virtual Environment (`venv`)
*   [x] **Local LLM Engine**
    *   Provider: Ollama (REST API via `127.0.0.1:11434`)
    *   Routing: Dynamic fallback chains (e.g., `qwen2.5:7b` -> `phi3:mini`)
    *   Memory Strategy: Aggressive TTFT timeout (`500s`), Budget `keep_alive` eviction (`2m`)
*   [ ] **Cloud LLM Engine**
    *   *Not Currently Implemented* (Strict local-only zero-trust architecture enforced)
*   [x] **Audio Subsystem**
    *   Wake Word: Local `Vosk` (Kaldi offline acoustic models)
    *   STT: `SpeechRecognition` (Google STT fallback for high-fidelity transcription)
    *   TTS: `Kokoro-ONNX` (CPU-optimized, ~80MB footprint, punctuation-chunked streaming)
    *   I/O: `PyAudio` / `sounddevice` (Multi-threaded buffer management for instant barge-in)
*   [x] **Vector DB & Caching**
    *   Database: `SQLite` (`helios.db`)
    *   Embeddings: `nomic-embed-text` (Local generation)
    *   Operations: Automated conversation summarization, semantic similarity search
*   [x] **Security & Sandbox**
    *   Access Control: Zero-Trust directory boundary enforcement (`security/permissions.py`)
    *   Execution: Human-in-the-loop requirement for terminal commands/file writes
*   [x] **UI & Inter-process**
    *   Core Transport: `FastAPI` (REST + WebSockets on port 8000)
    *   Event Bus: Internal Pub/Sub for decoupled component communication
    *   Desktop GUI: Transparent frameless webview overlay (`win32gui`, `ctypes`)
    *   Mobile: Voice PWA architecture

## Conclusion
HELIOS represents a highly sophisticated, pragmatic approach to local AI agents. By strictly separating reasoning (LLMs) from execution (Orchestrator), building out advanced local streaming voice pipelines, and heavily prioritizing strict hardware budget limits (8GB RAM) and security, it provides a powerful and interactive assistant environment that won't overwhelm budget PCs.
