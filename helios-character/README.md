# HELIOS Character (`helios-character`) — Full Spec & Character-Only Editions

`helios-character` is the 3D VRM and Live2D character system for **HELIOS**. It supports **two operating versions**:

1. **⚡ Full Spec Version (`full_spec`)**:
   * Bridges live to **HELIOS Core (`ai-router` on `:8000`)** via `/ws/character`.
   * Combines the full HELIOS ecosystem (multi-model routing, zero-trust sandbox, vector RAG memory, tools, MCP, desktop overlay) with the 3D VRM character.
2. **🎭 Just the Character (`character_only`)**:
   * Runs as a **standalone, lightweight 3D VRM character companion on `:8080`** without starting `ai-router` (`:8000`).
   * Includes its own lightweight local Ollama conversational brain (powered by `helios_personality_card.yaml` with instant expressive fallback), neural TTS (`edge-tts` + 30-FPS RMS/viseme lip-sync), 4-head neural body movement director, 24 human reference poses, 6 human posture styles, and the DeepMimic-style RL Pose Trainer.

---

## 📁 Directory Structure

```text
solstice-addon/
├── ai_server.py                  # Dual-version Character Server (Full Spec Bridge + Standalone Character Brain)
├── server.py                     # Lightweight HTTP/Live2D server (:8085 / :8082)
├── helios_personality_card.yaml  # Active Character Personality Card (Live Studio)
├── start_character_only.bat      # Launcher for Just the Character (Standalone :8080)
├── start_solstice_addon.bat      # Launcher for Solstice Addon Avatar Engine (:8082)
├── start_vrm_addon.bat           # Launcher for Character Addon server (:8080)
├── PLAN.md                       # Character architecture & integration notes
├── docs/                         # Project documentation, lore, prompts & screenshots
│   ├── TWINS_LORE_AND_PROMPTS.md # Twin character lore & prompts
│   └── screenshots/              # Verification screenshots
├── scripts/                      # Utility scripts
│   └── model_generation/         # 3D VRM crafting, texture generation & palette tooling
├── assets/                       # Asset caches & raw extractions
│   └── extracted/                # Extracted inspection textures and VRoid item data
├── tests/                        # Automated & manual playwright test suites
├── training/                     # Neural body director dataset and RL model weights
├── data/                         # Local database storage (solstice.db)
└── viewer/                       # Frontend 3D VRM & Live2D WebGL viewer
    ├── index.html                # Viewer UI, canvas & Edition Switcher
    ├── personality.html          # Live Personality Card & System Prompts Studio
    ├── app.js                    # Character Protocol consumer, 2-bone IK pose engine & RL telemetry
    ├── style.css                 # Viewer styling
    ├── vrm/                      # Modular VRM renderer, animation, expressions, humanizer, lip_sync
    ├── live2d/                   # Live2D renderer adapter
    └── models/                   # Model manifest (manifest.json), VRM assets (Helios_Airi.vrm, twin.vrm), animations & voices
```

---

## 🚀 Launching

### 🎭 Launch Just the Character (Standalone — No `:8000` Required)
```powershell
.\start_character_only.bat
```
Opens **[http://localhost:8080?edition=character_only](http://localhost:8080?edition=character_only)**.

### ⚡ Launch the Full Spec Version (`ai-router :8000` + `helios-character :8080`)
From the repository root:
```powershell
..\start_helios_full_spec.bat
```
Opens **[http://localhost:8080?edition=full_spec](http://localhost:8080?edition=full_spec)** connected to `ws://localhost:8000/ws/character`.
