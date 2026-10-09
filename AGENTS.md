# HELIOS Agent Guidelines & Architecture Invariants

## 🏛️ Ecosystem Overview
HELIOS is an autonomous, locally-hosted AI ecosystem composed of:
1. **`ai-router/`**: Core AI Router, 8-agent Hikari Swarm, Zero-Trust Permissions, VLA Computer Control, and Neural TTS Engine (`:8000`).
2. **`helios-character/`**: Airi & Ren 3D VRM Cybernetic presentation companion driven by Character Protocol WebSocket (`:8080`).
3. **`mobile_v2/`**: React Native / Expo mobile companion with real-time Hikari terminal streaming and on-device offline GGUF fallback.
4. **`portfolio/`**: Cyberpunk interactive engineering portfolio (React 19 + Vite).

---

## 🤖 Antigravity Multi-Agent Collaboration Protocol

When working across multiple sessions or worktrees (e.g. Orchestrator vs. IDE Agent):
1. **Handover Board:** Always inspect and maintain `HANDOVER.md` at the repository root.
2. **Status Lifecycle:**
   - Use `@IDE-Agent READY` for tasks ready for direct editor implementation.
   - Use `@IDE-Agent COMPLETED` when editor changes are committed to the worktree branch (`agent-ide-tasks`).
   - Use `@Orchestrator VERIFIED` only after automated pytest/tsc validation passes 100%.
3. **Testing Standards:**
   - Never assert raw strings on serialized JSON tool outputs; parse with `json.loads()` and assert dictionary keys.
   - Screen capture tools must use `mss.MSS()` context manager.

---

## 🎭 Character & VRM Models
- **Airi (`models/Helios_Airi.vrm`)**: Cybernetic wolf-cut female companion (1.68m, `#00E5FF` cyan glowing eyes, silver-gray hair).
- **Helios Twin / Ren (`models/Helios_Twin.vrm`)**: Older brother tactical operative (1.82m tall, broadened shoulders/chest, tactical cargo techwear).
- Both models are dynamically registered in `viewer/models/manifest.json` and selectable via viewer UI buttons or URL query parameter (`?model=twin` / `?model=airi`).
