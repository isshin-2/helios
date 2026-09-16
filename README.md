<div align="center">
  <img src="https://img.shields.io/badge/HELIOS-AI_Router-00e5ff?style=for-the-badge" alt="HELIOS AI Router">
  <br><br>
  <strong>A magical, locally-hosted AI brain that routes tasks to different models, remembers your preferences, and controls your computer.</strong>
</div>

<br>

---

# 🚀 How to Setup HELIOS (The "Baby-Proof" Guide)

Don't worry if you aren't a programmer! Just follow these exact steps to get HELIOS running on your computer.

### Step 1: Install the Prerequisites
Before starting, you need two pieces of software installed on your computer:
1. **[Python (3.11 or newer)](https://www.python.org/downloads/)**: When installing, **make sure you check the box that says "Add Python.exe to PATH"** at the very bottom of the installer window!
2. **[Ollama](https://ollama.com/download)**: This is the engine that runs the AI models locally on your computer. Download and install it.

### Step 2: Download the AI Models
HELIOS needs "brains" to work. Open your computer's **Terminal** (or Command Prompt) and copy-paste these commands one by one, hitting Enter after each:
`ash
ollama pull qwen2.5-coder:1.5b
ollama pull qwen2.5:7b
ollama pull moondream
`
*(Note: These downloads might take a few minutes depending on your internet speed).*

### Step 3: Start HELIOS!
Now that everything is installed, it's time to turn HELIOS on.

1. Download this entire folder to your computer.
2. Double-click the start.bat file (if you are on Windows). 
   * *(If you are on Mac, open a terminal, type chmod +x start.command and then run ./start.command)*
   * *(If you are on Linux, run ./start.sh)*
3. Wait for it to finish installing its requirements.
4. **You're done!** Open your web browser and go to: **[http://localhost:8000](http://localhost:8000)**

---

## 🐳 Alternative: Running in Docker (For Servers)
If you prefer to run HELIOS in a Docker container (perfect for servers or if you want to skip installing Python locally), you can start it with one command!

Make sure you have [Docker Desktop](https://www.docker.com/products/docker-desktop) installed, then open your terminal in this folder and run:
`ash
docker-compose up --build -d
`
*Note: When running in Docker, HELIOS runs "headlessly", meaning the animated desktop popups are automatically disabled.*

---
---

# ⚙️ Advanced Technical Details (For Nerds)

HELIOS operates as a proxy between a user interface and local LLMs (via Ollama) and sandboxed system tools. It routes system calls to specific models based on task requirements while enforcing execution boundaries.

### Core Features
- **Task-Based Routing**: Directs queries to specific local LLMs based on required capability (e.g., deepseek-r1:7b for reasoning, qwen2.5-coder:1.5b for tool execution).
- **Zero-Trust Sandbox**: Implements an execution sandbox via a PermissionManager. High-risk file operations and terminal commands require explicit API approval.
- **Vector Memory (RAG)**: Uses local SQLite vector embeddings to persist session context, automatically categorizing facts and tool discoveries into long-term memory.
- **Native GUI Overlays**: Features a dynamic, animated desktop UI overlay ("Tensura Style") for interactive mid-task multiple-choice questions from the AI.

### Hardware Profiles & Model Recommendations

Configure config.py based on your available RAM.

| Component | 8GB RAM (Low-End Windows Laptop) | 16GB RAM (Standard Desktop) | 32GB+ RAM (Workstation) |
|-----------|----------------------------------|-----------------------------|-------------------------|
| **Tool Execution** | qwen2.5-coder:1.5b | llama3.1:8b | deepseek-coder-v2:16b |
| **General Chat** | qwen2.5:7b | qwen2.5:7b | qwen2.5:14b |
| **Reasoning** | *Not Recommended* | deepseek-r1:7b | deepseek-r1:14b |
| **Vision** | moondream:latest | llava:latest | llava:13b |
| **Memory**| **~3.2 GB** | **~8.5 GB** | **~18.0 GB** |

> **Warning for 8GB Systems:** Attempting to load 7B/8B models (4.5GB+) alongside a TTS engine (1.5GB) on an 8GB machine will trigger severe OS paging. Stick to the 8GB profile to maintain stable execution times.
