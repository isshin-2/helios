# HELIOS Core & Twin Ecosystem Architecture Specification
> **Document Revision:** 1.0.0 (Unified Triad & Hard Isolation)  
> **Status:** RATIFIED & ACTIVE  
> **Author:** Antigravity Autonomous Systems Engineering Team

---

## 1. System Overview

HELIOS is a hardened, local-first autonomous AI operating ecosystem consisting of three partitioned runtime engines:

1. **HELIOS Core Router (Port `8000`)**:
   - Central model routing engine, Zero-Trust permission evaluator, Zero-Leak outbound privacy scrubber, and extensible connector registry.
   - Dedicated memory: `data/helios.db` and `data/helios_vectors/`.

2. **Hikari Coding Swarm (Port `8001`)**:
   - Autonomous 8-agent software engineering engine, interactive terminal CLI (`hikari.bat`), git worktree isolation, automated code generation, and test-repair loops.
   - Dedicated memory: `data/hikari.db` and `data/hikari_vectors/`.

3. **Solstice / "Sol" Avatar & Companion Engine (Port `8082` & WebGL `8080`)**:
   - Avatar presentation and companion telemetry engine for **both Airi and Ren (Helios Twin)**.
   - Real-time Three.js WebGL co-presence rendering, facial emotion mapping, viseme speech lip-sync, affective telemetry, and local voice biometric authentication.
   - Dedicated memory: `data/solstice.db` and `data/solstice_vectors/`.

---

## 2. Hard Isolation & HMAC Bridge Security Gate

```
┌─────────────────────────────────────────────────────────────┐
│                       DATA BOUNDARIES                       │
├──────────────────────────────┬──────────────────────────────┤
│ HELIOS Memory Namespace      │ data/helios.db               │
│ Hikari Memory Namespace      │ data/hikari.db               │
│ Solstice Memory Namespace    │ data/solstice.db             │
└──────────────────────────────┴──────────────────────────────┘
```

- **Strict Isolation Policy:** No engine is permitted to read, write, or cross-query another engine's database or vector store directly.
- **BridgeGuard:** All cross-engine communication requires:
  1. `BRIDGE_ENABLED=true` in `.env`.
  2. An authorized HMAC-SHA256 signature in the request headers (`X-Helios-Bridge-Token`) computed using `BRIDGE_SECRET` from `config/bridge.json`.
  3. Replay attack prevention with timestamp validation ($\le 5\text{ seconds}$ drift).

---

## 3. Hardware Governor & Capability Advisory Matrix

The Hardware Governor automatically detects host capabilities via DXGI, WMI, and `nvidia-smi`, assigning the system to one of three tiers:

| Metric | Tier 1 (High Performance) | Tier 2 (Balanced / Mid) | Tier 3 (Budget / iGPU) |
| :--- | :--- | :--- | :--- |
| **GPU Hardware** | Dedicated NVIDIA RTX $\ge 8\text{ GB}$ | Dedicated GPU $4\text{–}6\text{ GB}$ / $\ge 32\text{ GB}$ RAM | Intel Iris Xe / AMD Vega / $\le 16\text{ GB}$ RAM |
| **VLA Vision Model** | `qwen3-vl:8b` (Full Res) | `qwen2.5vl:3b` (720p) | `moondream:latest` (540p) or Disabled |
| **Hikari Swarm** | 8 Agents Concurrent | 4 Agents Concurrent | 1–2 Sequential Agents |
| **3D Avatar Mode** | 60 FPS PBR, Shadows, Physics | 60 FPS Optimized | 30 FPS Low-Overhead (No MSAA/Shadows) |
| **TTS Engine** | Dual Neural / GPT-SoVITS | Quantized Neural / Kokoro | ONNX / Edge-TTS / Kokoro Quantized |

### Budget Hardware Advisory Banner
When Tier 3 is detected, the system issues an explicit diagnostic advisory:
> **[WARNING - BUDGET HARDWARE DETECTED]**  
> Running on integrated graphics / low memory budget. To prevent system freezing:
> - Heavy Vision models ($\ge 8\text{B}$) are advised against; downgraded to `moondream` (1B).
> - Hikari Swarm concurrency throttled to sequential execution.
> - WebGL 3D scenes capped to 30 FPS without high-sample MSAA.

---

## 4. Zero-Leak Privacy & Local Voice Biometrics

- **Zero-Leak Filter:** Intercepts and scrubs outbound prompts for file paths, environment variables, API secrets (`sk-***`, `HELIOS_SECRET_***`), IP addresses, and PII.
- **Local Voice Biometrics:**
  - Lightweight ONNX ECAPA-TDNN speaker encoder (~20MB in `.models/biometrics/`).
  - Interactive 3-sample voice calibration deriving a local voiceprint centroid.
  - Cosine similarity matching (threshold $\ge 0.78$) with zero cloud transmission.
  - Argon2 / PBKDF2 hashed PIN fallback for noisy environments or microphone absence.

---

## 5. Extensibility & Connector Registry

- **`BaseConnector` Class:** Abstract interface defining `execute()`, parameter schemas, output schemas, and execution timeouts.
- **`config/connectors.manifest.json`:** Declarative registry defining all active connectors, permission scopes, and rate limits.
- **Zero-Trust Sandboxing:** All connector invocations are executed within timeout wrappers with structured error containment.

---

## 6. Antigravity Slash Commands Workflow

All operational commands can be triggered via `helios <command>` or inside the Hikari interactive shell:

- `/audit`: Scans files, checks IPC boundaries, validates hardware profile, and updates `docs/SYSTEM_AUDIT.md`.
- `/setup`: Performs a health check of `.venv`, Ollama status, hardware profile, and environment variables.
- `/test-isolation`: Executes an automated test suite verifying cross-namespace data isolation.
- `/verify-voice`: Runs speaker calibration, calculates similarity scores, and tests PIN fallback.
- `/3d-web-experience`: Launches the Three.js dual-avatar scene with real-time telemetry from Solstice and Hikari.

---

## 7. Dual Edition Distribution

1. **HELIOS Developer Edition (`start_helios_dev.bat`):** Launches HELIOS (:8000) and Hikari (:8001) with full terminal streaming, git worktree isolation, and debugging tools.
2. **HELIOS User / Companion Edition (`start_solstice.bat`):** Launches Solstice (:8082) with the 3D twin avatar interface (:8080) and voice biometrics, providing an ambient conversational companion without developer clutter.
