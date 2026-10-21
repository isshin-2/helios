# HELIOS Client — Remote Client Suite

<div align="center">
  <img src="https://img.shields.io/badge/HELIOS-Client-00e5ff?style=for-the-badge&logo=electron" alt="HELIOS Client">
  <img src="https://img.shields.io/badge/Architecture-Client--Server-blue?style=for-the-badge" alt="Client-Server">
  <img src="https://img.shields.io/badge/GUI-PyQt5_WebEngine-orange?style=for-the-badge" alt="PyQt5">
  <img src="https://img.shields.io/badge/CLI-Rich_Terminal-green?style=for-the-badge" alt="Rich Terminal">
</div>

<br>

**HELIOS Client** enables you to use your laptop or desktop workstation as a lightweight, fully-featured client while HELIOS Core, the 8-agent swarm, neural TTS, and heavy LLMs run remotely on a dedicated server (e.g. Dedicated AI PC Workstation with RTX 5060 Ti).

---

## 🌟 Key Capabilities

1. **Cyberpunk Desktop GUI (`--gui`)**:
   - Native dark-mode application window embedding the remote HELIOS Web HUD.
   - Dynamic server endpoint switcher (`AI PC (192.168.100.254:8000)`, `Localhost (127.0.0.1:8000)`, or Custom IP).
   - Real-time server connectivity & latency ping indicator badge (`● ONLINE (2.4ms)`).
   - One-click Wake-on-LAN trigger for sleeping GPU nodes.
   - Integrated toggle to run the Client Sidecar daemon in a background thread.

2. **Hikari Interactive Terminal CLI (`--cli`)**:
   - Claude Code and Codex-style terminal interface.
   - Connects to the remote server over WebSocket (`/ws/hikari`) with real-time agent step streaming (`ANALYZE`, `PLAN`, `ARCHITECT`, `EXECUTE`, `TEST`, `VERIFY`).
   - Built-in slash commands: `/status`, `/models`, `/diff`, `/test`, `/server`, `/wake`, `/clear`, `/exit`.

3. **Client Sidecar Daemon (`--sidecar`)**:
   - Links the physical client device to the remote HELIOS server via `/sidecar/ws`.
   - **Local Shell Execution**: Runs terminal commands (builds, tests, linters) directly in your client machine's local workspace.
   - **Remote Screen Capture**: Captures screenshots from your client display and feeds them to server-side vision models (`qwen3-vl:8b`, `moondream`).
   - **Desktop Automation**: Performs mouse clicks, keyboard typing, hotkeys, and app launching on your client desktop.
   - **Security Sandbox**: Blacklists destructive system commands (`rm -rf /`, `format`, `diskpart`, etc.).

---

## 🚀 Quick Launch (Root Launchers)

From the repository root on your client machine:

```powershell
# Interactive Master Launcher (GUI, CLI, Sidecar, Status, WoL)
.\start_helios_client.bat

# Direct Launches:
.\start_helios_client.bat gui       # Launch Desktop GUI Client
.\start_helios_client.bat cli       # Launch Terminal CLI (Hikari Remote)
.\start_helios_client.bat sidecar   # Launch Client Sidecar Daemon
.\start_helios_client.bat all       # Launch GUI + Sidecar simultaneously
.\start_helios_client.bat status    # Test server reachability & ping
.\start_helios_client.bat wake      # Send Wake-on-LAN to server
```

You can also use the master ecosystem launcher `start_helios.bat` and select `[6] HELIOS Client Mode`.

---

## ⚙️ Configuration & Discovery

Server addresses are automatically resolved in this priority:

1. CLI flag: `--server http://<ip>:<port>`
2. Environment variable: `HELIOS_SERVER_URL`
3. Client configuration file: `helios-client/client_config.json`
4. Workstation configuration: `AI_PC_IP` in `ai-router/.env`
5. Default fallback: `http://192.168.100.254:8000`

### Updating Default Server URL:

```powershell
# From command-line
python -m helios-client.main --set-server http://192.168.100.254:8000

# Or test current server status
python -m helios-client.main --status
```

---

## 📂 Architecture Overview

```text
┌─────────────────────────────────┐               ┌─────────────────────────────────────────┐
│     CLIENT MACHINE (Laptop)     │               │        SERVER NODE (Dedicated AI PC)    │
│                                 │               │                                         │
│  ┌───────────────────────────┐  │  HTTP / WS    │  ┌───────────────────────────────────┐  │
│  │ HELIOS Desktop GUI Client │──┼───────────────┼─>│ HELIOS Core Server (:8000)        │  │
│  │ (Embedded Web HUD + Ping) │  │               │  │ - Intelligent Multi-Model Router  │  │
│  └───────────────────────────┘  │               │  │ - 8-Agent Hikari Swarm            │  │
│                                 │  /ws/hikari   │  │ - SQLite Vector Memory (RAG)      │  │
│  ┌───────────────────────────┐  │               │  │ - Hardware Arbitrator & llmfit    │  │
│  │ HELIOS Hikari Terminal    │──┼───────────────┼─>│ - Kokoro / GPT-SoVITS Neural TTS  │  │
│  │ (Claude-Code CLI Console) │  │               │  └───────────────────────────────────┘  │
│  └───────────────────────────┘  │               │                                         │
│                                 │  /sidecar/ws  │                                         │
│  ┌───────────────────────────┐  │ (Bidirection) │                                         │
│  │ Client Sidecar Daemon     │<─┼───────────────┼─> Remote Desktop Controller & Screen    │
│  │ - Local Shell Commands    │  │               │   Vision Dispatches to Client           │
│  │ - Mouse & Keyboard Actions│  │               │                                         │
│  │ - Screen Capture (MSS/PIL)│  │               │                                         │
│  │ - File Read/Write in CWD  │  │               │                                         │
│  └───────────────────────────┘  │               │                                         │
└─────────────────────────────────┘               └─────────────────────────────────────────┘
```

---

## 🧪 Testing

Run client verification tests:

```powershell
..\ai-router\venv\Scripts\python.exe -m pytest helios-client/tests/test_client.py
```
