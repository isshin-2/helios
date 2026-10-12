# HELIOS & Twin Ecosystem Living System Audit
> **Single Source of Truth (SSoT) for Component Topologies, Hardware Tiers, and Security Boundaries**  
> **Last Synchronized:** `2026-10-12T07:51:32.045795+05:30`  
> **Audit Status:** `HARDENED & ISOLATED`  
> **Governor Status:** `Tier 3: Budget / Integrated Graphics (iGPU or <= 16GB RAM)`  
> **Git Working State:** `155 modified/untracked files`

---

## 1. Process & Component Port Topology

| Subsystem | Process Identifier | Primary Port | Protocol | Memory Silo | Isolation Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **HELIOS Core Router** | `helios.core` | `8000` | HTTP / WebSocket | `data/helios.db` | Strict (HMAC Required) |
| **Hikari Coding Swarm** | `helios.hikari` | `8001` | WebSocket / CLI | `data/hikari.db` | Strict (Worktree Sandbox) |
| **Solstice (Sol) Avatar** | `helios.solstice` | `8082` | HTTP / WebSocket | `data/solstice.db` | Strict (Avatar Silo) |
| **3D WebGL Studio** | `helios.character` | `8080` | HTTP / Static WebGL | None (Stateless Client) | Read-Only Telemetry |
| **Ollama Local Daemon** | `ollama.service` | `11434` | HTTP / REST | `.ollama/models` | Localhost Only |

---

## 2. Hardware Probing Profile & Acceleration Tiers

| Hardware Metric | Inspected Value | System Allocation | Classification |
| :--- | :--- | :--- | :--- |
| **Primary GPU** | `Intel(R) Iris(R) Xe Graphics` | 2.0 GB Dedicated/Shared | **Tier 3: Budget / Integrated Graphics (iGPU or <= 16GB RAM)** |
| **Physical System RAM** | `15.68 GB Total` | Available: ~3.26 GB | Constraint |
| **CPU Architecture** | `Intel64 Family 6 Model 154 Stepping 4, GenuineIntel` | 10 Physical / 12 Logical Cores | Fast CPU Compute |
| **Acceleration Engine** | `DirectML / CPU Quantized` | Dynamic Fallback | Active |

### Active Capability Advisories & Warnings
- ⚠️ SYSTEM MEMORY / VRAM CONSTRAINT: Host is operating on integrated graphics or limited VRAM (~2.0GB VRAM, 15.7GB RAM).
- ⚠️ VLA VISION OVERLOAD: 8B+ vision models (e.g. qwen3-vl:8b, gemma4:12b) will cause high latency and memory swapping.
- ⚠️ SWARM CONCURRENCY HAZARD: Running 8 parallel coding agents simultaneously may exhaust RAM and trigger OS thrashing.
- ⚠️ 3D GRAPHICS LOAD: Dual PBR 3D VRM rendering with shadows and physics will reduce frame rates on integrated GPUs.

### Recommended Resource Allocations:
- **VISION**: Downgraded to moondream:latest (1B) or qwen2.5vl:3b with 540p downscaled capture.
- **CODING_SWARM**: Throttled to sequential single-agent execution using qwen2.5-coder:1.5b / 3b.
- **3D_VIEWER**: Capped to 30 FPS, shadow maps disabled, MSAA reduced.
- **TTS**: Defaulting to low-overhead Kokoro-ONNX / Edge-TTS fallback.

---

## 3. Data Boundary & IPC Isolation Status

- **Bridge Enabled:** `False`
- **Cross-Engine Isolation:** `STRICT ENFORCEMENT (Zero-Trust)`
- **SQLite Database Stores:**
  - `HELIOS`: `data/helios.db` (Isolated)
  - `Hikari`: `data/hikari.db` (Isolated)
  - `Solstice`: `data/solstice.db` (Isolated)
- **Token Max Age:** `5s (Anti-Replay Window)`

---

## 4. Registered Connector Catalog & Scopes

| Connector ID | Version | Scopes | Timeout | Zero-Trust Sandbox |
| :--- | :--- | :--- | :--- | :--- |
| `system_diagnostics` | `1.0.0` | `read_only` | 10s | Enforced |

---

## 5. Antigravity Slash Command Entry Points

| Slash Command | Dispatch Target | Mode | Verification |
| :--- | :--- | :--- | :--- |
| `/audit` | `scripts/run_audit.py` | Full workspace re-scan & SSoT sync | Automated |
| `/setup` | `scripts/bootstrap.py` | Idempotent environment & hardware check | Automated |
| `/test-isolation` | `tests/test_isolation.py` | Data & memory segregation suite | Automated |
| `/verify-voice` | `scripts/verify_voice.py` | Speaker calibration & PIN verification | Interactive / Automated |
| `/3d-web-experience` | `scripts/launch_3d_experience.py` | Launches dual-avatar WebGL on :8080 | Automated |
