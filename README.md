<div align="center">
  <h1>HELIOS AI Router</h1>
  <p><strong>Locally-hosted, context-aware AI routing orchestrator for agentic workflows.</strong></p>
  
  [![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
  [![Ollama](https://img.shields.io/badge/Powered%20by-Ollama-orange.svg)](https://ollama.com/)
  [![Memory Optimization](https://img.shields.io/badge/Memory-Highly%20Optimized-success.svg)](#hardware-profiles--model-recommendations)
  [![Security](https://img.shields.io/badge/Security-Zero%20Trust-red.svg)](#security--sandbox)
</div>

<br>

HELIOS operates as a proxy between a user interface and local LLMs (via Ollama) and sandboxed system tools. It routes system calls to specific models based on task requirements while enforcing execution boundaries.

---

## Features

- **Task-Based Routing**: Directs queries to specific local LLMs based on required capability (e.g., `deepseek-r1:7b` for reasoning, `qwen2.5-coder:1.5b` for tool execution).
- **Memory Management**: Offloads inactive models from GPU/CPU VRAM to prevent Out-Of-Memory (OOM) exceptions.
- **Execution Sandbox**: Implements a Zero-Trust architecture via a `PermissionManager`. High-risk file operations and terminal commands require explicit API approval.
- **Pydantic Tooling**: Python-based tool definitions using Pydantic schemas, enabling LLMs to read files, run terminal commands, and automate OS tasks.
- **Vector Memory**: Uses local SQLite vector embeddings to persist session context.
- **Self-Modification**: Can propose codebase patches. Deployment requires explicit user approval.

---

## Hardware Profiles & Model Recommendations

HELIOS requires specific model configurations to prevent disk swapping or OOM crashes, particularly when running alongside the TTS engine (Kokoro TTS, ~1.5 GB). Configure `config.py` based on your available RAM.

| Component | 8GB RAM (Low-End Windows Laptop) | 16GB RAM (Standard Desktop) | 32GB+ RAM (Workstation) |
|-----------|----------------------------------|-----------------------------|-------------------------|
| **Tool Execution** | `qwen2.5-coder:1.5b` | `llama3.1:8b` | `deepseek-coder-v2:16b` |
| **General Chat** | `qwen2.5:7b` | `qwen2.5:7b` | `qwen2.5:14b` |
| **Reasoning** | *Not Recommended* | `deepseek-r1:7b` | `deepseek-r1:14b` |
| **Vision** | `moondream:latest` | `llava:latest` | `llava:13b` |
| **Memory Footprint**| **~3.2 GB** | **~8.5 GB** | **~18.0 GB** |

> **8GB System Constraints:**  
> Attempting to load 7B/8B models (4.5GB+) alongside Kokoro TTS (1.5GB) on an 8GB machine will trigger severe OS paging. Stick to the 8GB profile (`qwen2.5-coder:1.5b` + `moondream`) to maintain stable execution times.

---

## Installation

### 1. Requirements
- **Python 3.9+** (Must be in system PATH).
- **Ollama**: Must be running locally (default port: 11434).
- **Python Packages**: `pyautogui` and `Pillow` are required for UI automation tools.

### 2. Setup
Clone the repository and execute the startup script to build the environment and start the server:

* **Windows**: 
  ```bat
  start.bat
  ```
* **macOS**: 
  Run `./start.command` in terminal.
* **Linux**: 
  ```bash
  ./start.sh
  ```

### 3. Usage
Navigate to [http://localhost:8000](http://localhost:8000) in your browser.

---

## Security & Sandbox

HELIOS enforces execution boundaries by default:
- **File System**: Read/Write access is restricted to the HELIOS root directory. 
- **Permissions**: You can whitelist external directories and specific CLI commands via the **System Specs** panel in the Web UI.

Read the [ARCHITECTURE.md](ARCHITECTURE.md) for technical specifications on the routing and security implementations.
