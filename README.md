# HELIOS AI Router

HELIOS is a sophisticated, locally-hosted, context-aware AI routing orchestrator. It acts as an intelligent proxy between a dynamic user interface and various local LLMs (via Ollama) and sandboxed system tools.

## Key Features
- **Dynamic Model Routing**: Intelligently routes queries to the optimal local LLM based on task complexity (e.g., `deepseek-r1:7b` for reasoning, `qwen2.5-coder:7b` for coding).
- **Memory-Aware Offloading**: Actively manages your GPU/CPU VRAM by offloading inactive models to prevent Out-Of-Memory errors.
- **Robust Security Sandbox**: A Zero-Trust architecture where the LLM is tightly bounded by a `PermissionManager`. All file operations and terminal executions are strictly controlled and require human API approval for high-risk actions.
- **Pydantic Tool Chaining**: Extensible Python-based tools defined with rigid Pydantic schemas allow the LLM to read files, run terminal commands, and perform autonomous tasks reliably.
- **Persistent Vector Memory**: Utilizes local SQLite-based vector embeddings to remember facts across chat sessions automatically.
- **Self-Modification API**: HELIOS can autonomously propose and benchmark improvements to its own codebase, requiring explicit human approval before deploying changes.

## Prerequisites
- **Python 3.9+**
- **Ollama**: Must be running locally (default: `http://localhost:11434`).
- Ensure you have the recommended models pulled in Ollama (e.g., `ollama run qwen3:8b`). See `config.py` for the full fallback chains.

## Installation
1. Clone the repository.
2. Run the startup script to install dependencies and launch the server:
   - Windows: `start.bat`
   - macOS/Linux: `./start.sh`
3. Open your browser to [http://localhost:8000](http://localhost:8000).

## Security & Usage
- By default, HELIOS limits file access to its own directory. 
- You can manage allowed directories and approved terminal commands via the **System Specs** panel in the UI.

For a deeper dive into the system design, read [ARCHITECTURE.md](ARCHITECTURE.md).
