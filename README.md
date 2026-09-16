<div align="center">
  <img src="https://img.shields.io/badge/HELIOS-AI_Router-00e5ff?style=for-the-badge&logo=openai" alt="HELIOS AI Router">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Ollama-Local_AI-orange?style=for-the-badge" alt="Ollama">
  <br><br>
  <strong>A magical, locally-hosted AI brain that routes tasks to different models, remembers your preferences, and controls your computer.</strong>
</div>

<br>

---

## ✨ Features

*   🧠 **Task-Based Routing**: Automatically directs queries to specific local LLMs based on the required capability (e.g., coding, reasoning, vision).
*   🚀 **First-Start Auto-Provisioner**: Zero manual model setup! HELIOS automatically scans your hardware (CPU, RAM, GPU, Disk) and dynamically downloads the optimal models for your system.
*   🔒 **Zero-Trust Sandbox**: High-risk file operations and terminal commands are sandboxed and require explicit API approval.
*   💾 **Vector Memory (RAG)**: Uses local SQLite vector embeddings to persist session context, automatically categorizing facts and tool discoveries into long-term memory.
*   🖥️ **Desktop App & Voice**: A beautiful, frameless desktop app with real-time state syncing, built-in Kokoro TTS voice generation, and intelligent UI overlays.
*   🐳 **Docker Support**: Run HELIOS headlessly in a Docker container for server deployments.

---

## 🚀 How to Setup HELIOS (The "Baby-Proof" Guide)

Don't worry if you aren't a programmer! Just follow these exact steps to get HELIOS running on your computer.

### Step 1: Install the Prerequisites
Before starting, you need two pieces of software installed on your computer:
1. **[Python (3.11 or newer)](https://www.python.org/downloads/)**: When installing, **make sure you check the box that says "Add Python.exe to PATH"** at the very bottom of the installer window!
2. **[Ollama](https://ollama.com/download)**: This is the engine that runs the AI models locally on your computer. Download and install it.

### Step 2: Start HELIOS!
Yes, that's it! HELIOS handles all the model downloading for you.

1. Download this entire folder to your computer.
2. Double-click the `start.bat` file (if you are on Windows). 
   * *(If you are on Mac, open a terminal, type `chmod +x start.command` and then run `./start.command`)*
   * *(If you are on Linux, run `./start.sh`)*
3. Wait for it to finish installing its requirements.
4. On first startup, HELIOS will analyze your hardware and securely provision the best AI models for your system.
5. **You're done!** Open your web browser and go to: **[http://localhost:8000](http://localhost:8000)**

---

## 🐳 Alternative: Running in Docker (For Servers)

If you prefer to run HELIOS in a Docker container (perfect for servers or if you want to skip installing Python locally), you can start it with one command!

Make sure you have [Docker Desktop](https://www.docker.com/products/docker-desktop) installed, then open your terminal in this folder and run:
```bash
docker-compose up --build -d
```
*Note: When running in Docker, HELIOS runs "headlessly", meaning the animated desktop popups and voice features are automatically disabled.*

---
---

## ⚙️ Advanced Technical Details (For Nerds)

HELIOS operates as a proxy between a user interface, local LLMs (via Ollama), and sandboxed system tools. It routes system calls to specific models based on task requirements while enforcing execution boundaries.

### 🤖 Intelligent Hardware Profiling & Provisioning

HELIOS includes a state-of-the-art **Auto-Provisioner**. On first boot, it scans system specs and categorizes your machine into deterministic hardware tiers:
*   `gpu_workstation_16gb_plus`
*   `gpu_entry_8gb_vram`
*   `balanced_cpu_16gb`
*   `budget_cpu_8gb`

It uses a localized mini-model (1B-3B) as an analyzer to select models from a secure catalog tailored to your available memory, VRAM, and disk space.

### 🖥️ Native GUI Overlays & State Sync

The Desktop UI (`helios_desktop.py`) leverages PyWebView to render a transparent, frameless window. It integrates deeply with the Python backend via WebSockets to synchronize UI states (`listening`, `thinking`, `speaking`, `idle`), ensuring seamless, non-intrusive voice assistant experiences without aggressive always-on-top behaviors.

> **Warning for 8GB Systems:** Attempting to load 7B/8B models (4.5GB+) alongside a TTS engine (1.5GB) on an 8GB machine will trigger severe OS paging. HELIOS's auto-provisioner will actively restrict your catalog to lightweight models (1.5B - 3B) to maintain stable execution times.
