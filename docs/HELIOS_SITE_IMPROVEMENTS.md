# HELIOS Official Site Analysis & Enhancement Factbook (Updated)

> **Scope**: Comprehensive architecture and static asset audit of `c:\projects\helios-site` mapped against the live HELIOS ecosystem codebase (`c:\projects\HELIOS`, addons, documentation, models, audio, and visual captures).  
> **Key User Clarification**: **NVIDIA PAIR GPU Node Cluster (`192.168.100.254:11434`) is developer-specific hardware infrastructure**, not part of standard end-user setups. User-facing content must stay focused on local self-hosted AI, while developer-specific cluster tooling belongs cleanly under internal/developer architecture documentation.

---

## 1. Static Asset Audit: Discrepancies & Dead Weight

Direct inspection of `c:\projects\helios-site\public\`, `src\`, `refrences\`, and `c:\projects\helios-visuals\` reveals several asset discrepancies and unreferenced storage bloat:

### 1.1 Unused & Orphaned Media in `public/`
| File Path | Size | Status in Code | Assessment & Action |
| :--- | :--- | :--- | :--- |
| `public/media/helios_animated_demo.mp4` | **2.68 MB** | **Zero references** in any `.jsx` or `.css` | A high-quality animated screen demo exists on disk but is never displayed to users. It can either be embedded in the Hero section or removed to cut bundle weight. |
| `public/image_68ad06.jpg` | **394 KB** | **Zero references** (duplicated in `refrences/`) | Legacy mock image left in `public/`. Remove to save space. |
| `public/models/actual_airi_vrm_thumb.png` | **801 KB** | **Zero references** | Duplicate thumbnail file unreferenced by `portraitAssets.js`. |
| `public/models/actual_ren_vrm_thumb.png` | **1.34 MB** | **Zero references** | 1.3 MB uncompressed PNG sitting unreferenced in the VRM directory. |
| `public/models/airi_thumb.png` & `airi_thumb.jpg` | **801 KB ea.** | **Zero references** | Legacy duplicate thumbs superseded by `/portraits/airi-*.png`. |

> **Savings Potential**: Deleting or archiving these unreferenced files removes **~6.0 MB** of dead weight from `public/`.

### 1.2 Model File Integrity vs. Stated Specs
- **`public/models/Helios_Airi.vrm`**: Actual size is **19.2 MB** (`19,219,876 bytes`). The site spec sheet in `SolAvatarVoice.jsx` claims it is `15.1 MB`.
- **`public/models/Helios_Twin.vrm`**: Actual size is **16.5 MB** (`16,549,504 bytes`). The site spec sheet claims it is `13.8 MB`.
- **Fix**: Update the UI text to state the true verified sizes (`19.2 MB` and `16.5 MB`).

### 1.3 Goldmine of Verified Visual Assets in `c:\projects\helios-visuals\`
Currently, the site only uses two 2D portrait cuts (`avatar-2026-10-20 (1).png` and `(2).png`). Meanwhile, `c:\projects\helios-visuals\` contains over **60 verified studio screenshots and render captures**:
- `screenshot_dual_synergy.png`: Dual Airi + Ren together in 3D WebGL (ideal for the Sol Twin Synergy banner).
- `screenshot_studio.png` & `screenshot_hand_foot_sliders.png`: The interactive 3D Prop & Pose Studio HUD (shows real 3D capability).
- `test_fullbody_listening.png`, `test_fullbody_speaking.png`, `test_fullbody_thinking.png`: Showing state changes.
- `test_pose_ren_monocle_face_perfect.png`: High-res close-up of Ren's cyber monocle HUD reticle and SD-04 drone.
- **Improvement**: Replace static 2D vector cards with a visual carousel or comparison gallery using these actual 3D engine captures.

---

## 2. Audio & Speech Synthesis Fact Check (GPT-SoVITS & Kokoro)

### 2.1 Where Voices Are Saved in HELIOS
Voice audio references, profile configs, and cloned voice metadata are stored in:
- **Reference Audio & Text**: `c:\projects\HELIOS\voices\`
  - `voices/airi/`:
    - `reference.wav` & `Miku-Nakano-2026-10-04-14-58-It's-nice-to-meet-you.-Well[short-pause]-technic.mp3` (457 KB)
    - `reference.txt`
    - `metadata.yaml` (Defines `model_type: gpt_sovits`, style, accent, prosody)
  - `voices/helios/`:
    - `reference.txt` & `metadata.yaml`
- **Voice Configurations & Prosody**: `c:\projects\HELIOS\ai-router\config\voice_profiles.yaml`
  - Defines exact backend (`backend: gpt_sovits`), reference paths, pitch, speed, and emotion prosody matrices (natural, happy, curious, excited, serious, concerned, amused, relaxed, confused).
- **Core Engine Implementation**: `c:\projects\HELIOS\ai-router\core\audio\tts\gpt_sovits.py` and `manager.py`
  - Arbitrates GPU VRAM (requires ~2.4GB VRAM, 1.8GB RAM) with fallback to Kokoro-ONNX when VRAM is constrained.

### 2.2 Site Improvement for Voice
- **Current Site State**: The site only states "Kokoro 24kHz", omitting the custom GPT-SoVITS cloning engine, and clicking voice sample lines in `SolAvatarVoice.jsx` only plays a synthetic beep from Web Audio API.
- **Improvement**: 
  1. Highlight **GPT-SoVITS** as the high-fidelity neural cloning voice engine for Airi on the Sol System page (with Kokoro as the ultra-low latency fallback).
  2. Copy sample voice clips synthesized from `voices/airi/reference.wav` into `c:\projects\helios-site\public\media\voices\` so clicking the speech lines plays real neural voice audio.

---

## 3. Clear Separation: User-Facing Product vs. Developer Infrastructure

Per user directive, **developer-specific cluster infrastructure must not be conflated with the standard user-facing product**.

### 3.1 What End-Users Experience (Community / Standard User)
- **Local-First & Private**: 100% runs on the user's workstation via local Ollama, vLLM, or LM Studio.
- **Zero-Cloud Leakage**: `LOCAL_ONLY=true` prevents any audio, screen capture, or prompt text from leaving localhost.
- **Hardware-Aware Tiering**: Automatically adapts to whether the user has a gaming GPU or an integrated CPU/iGPU (Intel Iris Xe / Apple Silicon) using `docs/SYSTEM_AUDIT.md` recommendations.
- **Optional BYOK (Bring Your Own Key)**: Seamlessly enter a personal Gemini, Groq, or OpenRouter API key for heavier tasks without cloud phone-home.
- **Dual Avatars**: Airi (companion interface) and Ren (tactical older brother twin) in 3D WebGL with local Kokoro-ONNX voice synthesis.
- **Hikari Coding Terminal**: Single or parallel autonomous agents working on local codebases inside isolated Git worktrees.

### 3.2 What Belongs Only in Developer / Architecture Tabs
- **NVIDIA PAIR GPU Cluster Node** (`192.168.100.254:11434` with Wake-on-LAN magic packet and 15s circuit breaker): This is dedicated author/internal test infrastructure for running heavy 32B+ reasoning models. It should **not** appear on the user download page as a requirement or core feature.
- **Offline Ed25519 Cryptographic Licensing**: Keep in the "Licensing / Enterprise" sub-page; don't clutter the quickstart with "unverified checklist" warnings.

---

## 4. Specific Site Improvements by View

### 4.1 Global Header & Navigation (`SiteHeader.jsx` & `App.jsx`)
1. **Eliminate Double-Header Clutter**: Remove lines 235–346 in `App.jsx`. Having two stacked navigation menus (`Home/Ecosystem/Sol/Downloads` on top and `MODULES_REGISTRY/SOL_AVATAR_VOICE/DOWNLOAD_CENTER` below) creates visual confusion and eats 50px of vertical space.
2. **Promote Audio Toggle**: Keep the SFX toggle in the top navbar, but label it clearly as `UI Sounds` vs `Voice Audio`.

### 4.2 Home Experience (`HomeExperience.jsx`)
1. **Embed the Animated Demo**: Integrate `public/media/helios_animated_demo.mp4` into a sleek Mac/Linux terminal mockup below the Hero section. Seeing autonomous agent terminal diffs in motion instantly explains what HELIOS does.
2. **Character Aesthetic Accuracy**: Correct the description of Airi to match `AGENTS.md` (cybernetic wolf-cut, `#00E5FF` cyan glowing eyes, silver-gray hair) to align with canonical VRM assets.
3. **Interactive Hardware Calculator**: Add a simple 3-button selector:
   - *“Budget / iGPU (Intel Iris Xe or ≤ 16GB RAM)”* -> Shows Tier 3 config: `qwen2.5:1.5b`, 540p VLA vision, 30 FPS avatar.
   - *“Mid-Range (6-8GB VRAM)”* -> Shows Tier 2 config: `qwen2.5-coder:7b`, 720p vision, Kokoro TTS.
   - *“Workstation (16GB+ VRAM)”* -> Shows Tier 1 config: `qwen2.5-coder:32b`, full 8-agent swarm, 1080p VLA.

### 4.3 Sol Avatar & Voice Engine (`SolAvatarVoice.jsx`)
1. **Actual Audio Playback**: Hook the dialogue buttons to real pre-rendered `.mp3` clips of Kokoro TTS.
2. **True VRM File Sizes**: Display **19.2 MB** for Airi and **16.5 MB** for Ren.
3. **Gallery of Real 3D Studio Poses**: Embed screenshots from `c:\projects\helios-visuals\` showing the twins with their props (SD-04 Ghosteye Recon Drone, Cyber Monocle HUD, Cyber-Butterfly) and in Synergy mode.
4. **Offline 3D Viewer Graceful Fallback**: If `:8080` is not actively running on the user's machine, provide a modal explaining: *"Run `helios /studio` or `start_solstice.bat` to launch the live 3D holodeck locally, or inspect the 3D screenshot gallery below."*

### 4.4 Ecosystem Registry (`App.jsx` Packages View)
1. **Add ASTRAEA Operative**: Include `astraea-addon` (`:8085`, Autonomous Gaming & Vision Operative) in the package directory alongside Core, Hikari, Sol, and Mobile.
2. **Replace Placeholder Warnings**: Remove `"RELEASE DETAILS UNVERIFIED"` and `"RELEASE CHECKLIST INCOMPLETE"`. Display clear badges such as `MIT Community Core` and `v3.0.0 Stable`.
3. **Computer Control / VLA Card**: Add Desktop Automation (`ScreenVisionTool`, `ComputerAgent`, 34 OS tools) to the Core breakdown.

### 4.5 Download Hub (`DownloadCenter.jsx`)
1. **Clear BYOK & Local-Only Highlights**: Emphasize that HELIOS never sends telemetry to any third party and that cloud API keys are purely optional.
2. **Direct Script Inspection**: Add a 1-click modal or collapsible view to inspect `setup.bat` and `setup.sh` directly on the page before downloading.

### 4.6 Skills, IoT & Open-Source Connectors (`SkillsPage.jsx`) [Implemented]
Added a dedicated page and header navigation link (`#skills`) detailing open-source ecosystem tools commonly orchestrated with local LLMs:
- **Home Assistant OS & Core**: Autonomous local smart home telemetry, entity control, lights/climate switching, and YAML automations over local REST/WebSocket (`:8123`) without cloud voice assistants.
- **Model Context Protocol (MCP)**: Anthropic MCP standard integration connecting HELIOS Core and Hikari to external MCP servers (filesystem sandboxes, GitHub, Brave Search, Postgres).
- **SearXNG Private Metasearch**: Zero-tracking self-hosted metasearch (`:8888`) for real-time web grounding and documentation indexing without ad-tracking.
- **OctoPrint & Bambu Lab 3D Printing**: Hardware fabrication monitoring, temperature sensing, and VLA camera vision inspection for 3D print failures.
- **ChromaDB & Qdrant**: High-density local vector memory stores for codebase RAG and episodic memory graphs.
- **Desktop VLA Actuation**: Native Win32/X11 screen vision (MSS), coordinate clicking, keyboard typing, and safety HUD overlay.
- Features category filtering pills, technical spec breakdowns, example autonomous prompts, copyable `connectors.manifest.json` entries, and zero-trust security callouts.

---

## 5. Prioritized Action Checklist

- [ ] **Asset Cleanup**: Delete or move unreferenced `public/media/` and duplicate `.png`/`.jpg` files (~6 MB saved).
- [ ] **Model Specs**: Correct file sizes to `19.2 MB` and `16.5 MB` in `SolAvatarVoice.jsx`.
- [ ] **Header Unification**: Remove duplicate sub-header in `App.jsx`.
- [ ] **Character Canon Alignment**: Reconcile Airi's visual styling across the site with `AGENTS.md`.
- [ ] **Real Voice Samples**: Add pre-synthesized Kokoro audio clips to dialogue lines.
- [ ] **Visual Showcase**: Incorporate 3D render screenshots from `helios-visuals/` to prove 3D fidelity.
- [ ] **Developer Separation**: Keep cluster/PAIR node specs strictly in internal architecture docs, keeping the public site 100% focused on local workstation users and privacy.
