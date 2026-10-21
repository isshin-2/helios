# HELIOS Installation & Deployment Guide

This guide covers setting up **HELIOS** for local execution, configuring BYOK/BYOHW inference, and managing Pro license entitlements.

---

## 🖥️ System Requirements

### Supported Operating Systems
- **Windows**: Windows 10 / 11 (64-bit)
- **Linux**: Ubuntu 22.04 LTS+, Debian 12+, Fedora, Arch Linux
- **macOS**: macOS 13+ (Ventura, Sonoma, Sequoia; Apple Silicon M1-M4 or Intel)

### Core Prerequisites
- **Python**: Version `3.11`, `3.12`, or `3.13`
- **Node.js**: Version `20.x` or `22.x LTS` (required for 3D VRM Avatar & Portfolio)
- **Git**: Version `2.40+`
- **Ollama** (Recommended for 100% offline local inference): [ollama.com](https://ollama.com)

---

## ⚡ Hardware Recommendations (BYOHW)

HELIOS automatically detects system RAM, CPU cores, GPU vendor, and VRAM to recommend optimal models.

| Hardware Tier | Memory / Compute | Recommended Provider & Models | Supported Capabilities |
| :--- | :--- | :--- | :--- |
| **Tier 1: Cloud BYOK / Low-Spec** | 8 GB RAM, Integrated GPU | BYOK: Gemini 1.5 Flash, OpenRouter, Groq | Full Code, Avatar, and Desk workflows with cloud API keys |
| **Tier 2: Mid-Range Local** | 16 GB RAM, 6–8 GB VRAM (RTX 3060/4060) | Ollama: `qwen2.5-coder:7b`, `llama3.2:3b` | 100% offline coding, basic tool calling, Kokoro TTS |
| **Tier 3: Pro Workstation** | 32–64 GB RAM, 16 GB+ VRAM (RTX 4080/5060 Ti) | Ollama / vLLM: `qwen2.5-coder:32b`, `deepseek-r1:14b` | Autonomous coding swarm, real-time vision, zero-latency desktop control |

---

## 🚀 Quickstart: Community Edition (MIT Open-Source)

HELIOS Community is fully functional, free, and open-source forever. It does not require online accounts, activation servers, or telemetry.

### 1. Clone the Repository
```bash
git clone https://github.com/krithik-helios/HELIOS.git
cd HELIOS
```

### 2. Configure Python Virtual Environment
On Windows (PowerShell):
```powershell
cd ai-router
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

On Linux / macOS (Bash / Zsh):
```bash
cd ai-router
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
cp .env.example .env
```

Key environment options in `.env`:
```ini
# Inference Provider: 'ollama', 'gemini', 'openrouter', 'vllm', or 'pair'
LLM_PROVIDER=ollama

# Network Security: Bind only to local loopback by default (Zero-Trust)
HELIOS_BIND_HOST=127.0.0.1
SERVER_PORT=8000

# Optional: Require a token for WebSocket connections (e.g. if accessing across LAN)
# HELIOS_WS_SECRET=your-secret-token-here

# BYOK Cloud Keys (Optional - only required if using cloud providers)
# GEMINI_API_KEY=AIzaSy...
# OPENROUTER_API_KEY=sk-or-v1-...
```

### 4. Launch the AI Router & Desktop Assistant
```powershell
python main.py
```
The FastAPI backend and WebSocket server will start on `http://127.0.0.1:8000`.

---

## 🎭 Launching the 3D VRM Cybernetic Avatar (Optional)

The avatar viewer provides a real-time, WebGL Three.js presentation companion synchronized with HELIOS speech and emotions.

```powershell
cd helios-character
npm install
npm run dev
```
Open `http://localhost:8080` in your web browser. You can select between:
- **Airi**: `http://localhost:8080/?model=airi`
- **Ren (Tactical Twin)**: `http://localhost:8080/?model=twin`

---

## 💎 Upgrading to HELIOS Pro (One-Time Purchase)

HELIOS Pro modules (`Code Pro`, `Avatar Pro`, `Desk Pro`) are unlocked via a cryptographic **Ed25519 offline license**. No internet connection or remote validation servers are used.

### License Installation Methods

#### Option A: User Configuration Directory (Recommended)
Place your purchased `license.json` file in:
- **Windows**: `%USERPROFILE%\.config\helios\license.json` (e.g., `C:\Users\<user>\.config\helios\license.json`)
- **Linux / macOS**: `~/.config/helios/license.json`

HELIOS automatically loads this file on startup.

#### Option B: Environment Variable
You can point to any location using `HELIOS_LICENSE_PATH`:
```bash
export HELIOS_LICENSE_PATH="/path/to/my_license.json"
```

#### Option C: REST API / Desktop HUD
You can import your license directly through the API:
```bash
curl -X POST http://127.0.0.1:8000/api/license/import \
  -H "Content-Type: application/json" \
  -d '{"license_text": "{ ... content of license.json ... }"}'
```

### Checking License Status
```bash
curl http://127.0.0.1:8000/api/license/status
```
Response:
```json
{
  "status": "ok",
  "edition": "pro",
  "is_active": true,
  "entitlements": {
    "code_core": true,
    "code_pro": true,
    "avatar_core": true,
    "avatar_pro": true,
    "desk_core": true,
    "desk_pro": true
  }
}
```

### Reverting to Community Edition
To remove Pro features and return to the Community baseline, either:
- Delete `~/.config/helios/license.json`, or
- Call `POST http://127.0.0.1:8000/api/license/remove`.

All your user data, memory databases, and local configurations are preserved 100%.

---

## 🔒 Security Best Practices

1. **Keep Default Loopback Binding**: Always keep `HELIOS_BIND_HOST=127.0.0.1` unless explicitly deploying on a secure, firewalled home LAN.
2. **Set a WebSocket Secret for LAN/Mobile Access**: If accessing HELIOS from the React Native mobile client over Wi-Fi, set `HELIOS_WS_SECRET` in `.env` and pass `?token=<secret>` in your connection URL.
3. **Never Commit Secrets**: HELIOS includes an automatic Secret Redactor that strips API keys from logs and telemetry, but never commit your `.env` or `license.json` to source control.
