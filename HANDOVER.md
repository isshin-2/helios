# HELIOS Handover & Orchestration Spec

## 🎯 Primary Goal
**Finalize & stabilize the uncommitted Vision-Language-Action (VLA) computer control, GPT-SoVITS TTS, and Mobile V2 streaming integration, and configure the Airi / Helios Twin older brother model selection.**

---

## 🚦 Agent Collaboration Protocol

1. **Lead Orchestrator**: Maintains this specification, coordinates micro-tasks, runs regressions, monitors the worktree, and merges/pushes branches.
2. **IDE Agent**: Focuses on direct editor work, targeted code edits, and refactorings on the designated worktree branch (`agent-ide-tasks`).
3. **Status Tags**:
   - `@IDE-Agent READY` : Task is fully specified, unblocked, and ready for editor implementation.
   - `@IDE-Agent IN-PROGRESS` : IDE agent has begun editing code for this task.
   - `@IDE-Agent COMPLETED` : IDE agent has completed the changes, verified syntax, and committed to the branch.
   - `@Orchestrator VERIFIED` : Orchestrator has pulled, run automated tests, and verified the task.

---

## 📋 Task Index & Status Board

| Task ID | Component | Description | Status | Assignee |
| :--- | :--- | :--- | :--- | :--- |
| **TASK-01** | `ai-router/tests` | Fix `test_computer_control_move` assertion for structured JSON | `@Orchestrator VERIFIED` | Orchestrator |
| **TASK-02** | `ai-router/tools` | Update `mss.mss()` to `mss.MSS()` deprecation warning | `@Orchestrator VERIFIED` | Orchestrator |
| **TASK-03** | `ai-router/vla` | Ensure root `vla_engine.py` and `SYSTEM_AUDIT.md` path alignment | `@Orchestrator VERIFIED` | Orchestrator |
| **TASK-04** | `ai-router/tts` | Stabilize GPT-SoVITS audio normalizer & resource policy contracts | `@Orchestrator VERIFIED` | Orchestrator |
| **TASK-05** | `mobile_v2` | Type check and verify `/ws/hikari` terminal streaming client | `@Orchestrator VERIFIED` | Orchestrator |
| **TASK-06** | `ai-router/core` | Run unified regression suite (Core Suite + VLA + TTS + Computer) | `@Orchestrator VERIFIED` | Orchestrator |
| **TASK-07** | `helios-character` | Airi & Twin older brother VRM generation & model selection | `@Orchestrator VERIFIED` | Orchestrator |
| **TASK-08** | `ai-router/core` | Meta Seamless Interaction dyadic engine & sibling profiles | `@Orchestrator VERIFIED` | Orchestrator |
| **TASK-09** | `ai-router/models` | Retrain 4-Head Neural MLP & RL Policy with dyadic priors | `@Orchestrator VERIFIED` | Orchestrator |
| **TASK-10** | `helios-character` | Procedural dyadic poses & sibling gaze/humanizer in Three.js | `@Orchestrator VERIFIED` | Orchestrator |
| **TASK-11** | `helios-character` | Authentic male Ren VRM synthesis with male techwear & Airi cybernetic palette | `@Orchestrator VERIFIED` | Orchestrator |
| **TASK-12** | `helios-character` | Applied HELIOS cybernetic palette directly to user's ren.vrm (`Pictures\ren.vrm`) | `@Orchestrator VERIFIED` | Orchestrator |
| **TASK-13** | `helios-character` | Dynamic cybernetic color changing across states (Idle, Listening, Thinking, Speaking, Error) | `@Orchestrator VERIFIED` | Orchestrator |
| **TASK-14** | `helios-character` | Automated browser verification & visual calibration matching Ren to Airi's color transitions | `@Orchestrator VERIFIED` | Orchestrator |

---

## 🛠️ Detailed Engineering Task Specifications & Outcomes

### [TASK-01] Fix `test_computer_control_move` assertion for structured JSON
- **Status:** `@Orchestrator VERIFIED`
- **File:** `ai-router/tests/test_computer_control.py`
- **Resolution:** Updated assertion to parse JSON and validate `data["success"] is True`, `data["action"] == "move"`, and `data["target"] == {"x": 500, "y": 400}`.
- **Verification:** `pytest ai-router/tests/test_computer_control.py` passed 6/6.

---

### [TASK-02] Update `mss.mss()` to `mss.MSS()` deprecation warning
- **Status:** `@Orchestrator VERIFIED`
- **Files:**
  - `ai-router/tools/screen_vision.py`
  - `ai-router/tests/test_computer_control.py`
- **Resolution:** Replaced all `mss.mss()` context manager calls with `mss.MSS()`.
- **Verification:** Zero deprecation warnings in test suite.

---

### [TASK-03] Ensure root `vla_engine.py` and `SYSTEM_AUDIT.md` path alignment
- **Status:** `@Orchestrator VERIFIED`
- **Files:**
  - `ai-router/system_audit.py`
  - `vla_engine.py`
  - `SYSTEM_AUDIT.md`
- **Resolution:** Updated `AuditSyncManager` to automatically resolve both root and subproject `SYSTEM_AUDIT.md` paths.

---

### [TASK-04] Stabilize GPT-SoVITS audio normalizer & resource policy contracts
- **Status:** `@Orchestrator VERIFIED`
- **Files:** `ai-router/tests/test_tts_pipeline.py`, `ai-router/tests/test_gpt_sovits_resource_manager.py`
- **Verification:** 38/38 unit and integration tests passing.

---

### [TASK-05] Type check and verify `/ws/hikari` terminal streaming client
- **Status:** `@Orchestrator VERIFIED`
- **Files:** `mobile_v2/`
- **Verification:** `tsc.cmd --project mobile_v2/tsconfig.json --noEmit` passed with 0 errors.

---

### [TASK-06] Unified Ecosystem Master Regression Run
- **Status:** `@Orchestrator VERIFIED`
- **Result:** **72 / 72 tests passed (100%) in 39.99s**.

---

### [TASK-07] Airi & Twin Older Brother VRM Generation & Model Selection
- **Status:** `@Orchestrator VERIFIED`
- **Files:**
  - `helios-character/viewer/models/Helios_Twin.vrm`
  - `helios-character/viewer/vrm/twin.vrm`
  - `helios-character/viewer/models/manifest.json`
  - `helios-character/viewer/index.html`
  - `helios-character/viewer/app.js`
- **Changes Implemented:**
  1. **Physique / Bone Hierarchy:** Transformed VRM skeleton for tall (1.82m), broad-shouldered athletic build.
  2. **Sibling Aesthetic DNA:** Inherited Airi's cyan cybernetic eyes (`#00E5FF`) and silver hair.
  3. **Stealth Techwear:** Re-textured into dark slate (`#0B0D11`) and carbon armor with glowing cyan power conduits.
  4. **Viewer Model Selector:** Dedicated selector buttons for `⚡ HELIOS Airi` and `🔷 HELIOS Twin (Brother)`.
  5. **Startup & Query URL:** Added `?model=twin` URL parameter support.

---

### [TASK-08] Meta Seamless Interaction Dyadic Engine & Sibling Profiles
- **Status:** `@Orchestrator VERIFIED`
- **Files:**
  - `ai-router/core/seamless_interaction.py`
  - `ai-router/core/character_state.py`
  - `ai-router/tests/test_seamless_interaction.py`
- **Changes Implemented:**
  1. Distilled dyadic interaction priors from `facebook/seamless-interaction`: mean 230ms turn-transition gap, 180ms barge-in threshold, thinking gaze aversion, and active backchannel nods.
  2. Created differentiated sibling behavior profiles:
     - **Airi:** Expressive head tilt (12.5°), lively backchannel nodding (`active_listening_nod`), high gaze aversion rate (0.72).
     - **Ren:** Tactical composure (0.95), micro-nods (`nod`), steady authoritative eye contact with minimal saccade drift.
  3. Added tests validating turn-taking, backchanneling, barge-in recoil, and gaze aversion (`6/6 passed`).

---

### [TASK-09] Retrain 4-Head Neural MLP & RL Policy with Dyadic Priors
- **Status:** `@Orchestrator VERIFIED`
- **Files:**
  - `helios-character/training/train_and_eval_body_director.py`
  - `ai-router/models/helios_body_movement_model.pkl`
  - `ai-router/models/helios_rl_pose_policy.pkl`
  - `helios-character/training/helios_body_movement_model.pkl`
- **Changes Implemented:**
  1. Added 5 dyadic scenario tuples to training corpus covering backchanneling, gaze aversion, turn-yielding inquiry, and tactical posture.
  2. Re-trained 4-Head Neural MLP (100% accuracy) and RL policy (99.9% reward), persisting production weights.

---

### [TASK-10] Procedural Dyadic Poses & Sibling Gaze/Humanizer in Three.js
- **Status:** `@Orchestrator VERIFIED`
- **Files:**
  - `helios-character/viewer/vrm/animation.js`
  - `helios-character/viewer/app.js`
  - `helios-character/viewer/vrm/humanizer.js`
- **Changes Implemented:**
  1. Mapped `active_listening_nod`, `thoughtful_gaze_aversion`, `turn_yield_inquiry`, `barge_in_alert`, and `tactical_composure` in `PROTOCOL_ANIMATION_MAP`.
  2. Implemented 2-Bone IK + thoracic keyframe curves for all 5 dyadic animations in `applyProceduralPose()`.
  3. Added `tactical` posture style bias and integrated saccade suppression and thinking gaze aversion drift into `humanizer.js`.

---

### [TASK-11] Authentic Male Ren VRM Synthesis with Male Techwear & Airi Cybernetic Palette
- **Status:** `@Orchestrator VERIFIED`
- **Files:**
  - `helios-character/viewer/models/Helios_Twin.vrm`
  - `helios-character/viewer/vrm/twin.vrm`
  - `helios-character/craft_male_ren_vrm.py`
  - `helios-character/viewer/models/manifest.json`
- **Changes Implemented:**
  1. **Base Rig:** Built directly upon `Yu1_1.vrm` (100% authentic male humanoid skeleton, 120 joints, 14 blendshapes, male hair and physics).
  2. **Masculine Techwear Outfit:** Injected male high-collar tactical techwear jacket (`vroid_extracted_22.png`), tactical utility cargo trousers (`vroid_extracted_21.png`), and combat runner shoes (`vroid_extracted_20.png`) from reference `model.vroid`.
  3. **Airi Cybernetic Color Scheme Integration:**
     - **Hair:** Silver-slate (#C0D0D8) with cyan underlayer tone and subtle rim glow.
     - **Eyes:** Piercing cybernetic cyan iris (`#00E5FF`) with glowing MToon emission.
     - **Clothing:** Stealth dark slate (#0B0D11) & reinforced charcoal (#1B1E26) techwear fabric with glowing `#00E5FF` cyan circuit lines, zippers, and buckle piping.
  4. Synced cleanly across root and IDE worktree (`project-ide-branch`).

---

### [TASK-12] Applied HELIOS Cybernetic Palette directly to User's `ren.vrm`
- **Status:** `@Orchestrator VERIFIED`
- **Files:**
  - `C:\Users\krithik\Pictures\ren_helios.vrm`
  - `helios-character/viewer/models/Helios_Twin.vrm`
  - `helios-character/viewer/vrm/twin.vrm`
  - `helios-character/apply_helios_palette_to_ren.py`
- **Changes Implemented:**
  1. Loaded the user's VRM from `C:\Users\krithik\Pictures\ren.vrm` (VRMC 1.0 male model with 118 joints, 14 expressions, rigged techwear jacket, cargo bottoms, runners, and belt accessories).
  2. Injected HELIOS aesthetic palette:
     - **Cybernetic Eyes:** Piercing cyan iris (`#00E5FF`) with glowing emissive factors.
     - **Hair:** Silver-slate (`#C0D0D8`) gradient with subtle cyan highlights.
     - **Eyebrows & Lashes:** Cool graphite slate.
     - **Techwear Clothing:** Dark stealth slate (`#11141A`) & charcoal base fabric with glowing `#00E5FF` cyan circuit lines, zippers, cargo straps, and shoe sole conduit lines.
  3. Re-serialized GLB container and preserved all bufferViews with exact byte alignment.
  4. Saved output to `C:\Users\krithik\Pictures\ren_helios.vrm` as well as live companion viewer locations.

---

### [TASK-13] Dynamic Cybernetic Color Changing Across AI Core States
- **Status:** `@Orchestrator VERIFIED`
- **Files:**
  - `helios-character/viewer/app.js`
  - `helios-character/viewer/style.css`
- **Changes Implemented:**
  1. **Dynamic State-Driven Material Modulation:**
     - **⚫ Idle (`#2C3038` Charcoal / Calm Cyan-Slate):** Gentle 1.6 Hz cybernetic breathing rhythm across techwear conduit lines and calm cyan-slate iris.
     - **🔵 Listening (`#00E5FF` Piercing Cyan):** Bright neon cyan 3.2 Hz pulse across iris, jacket zippers, cargo straps, runner soles, and spatial polar grid.
     - **🟡 Thinking / Working (`#FFCC00` Amber / Gold):** Rapid 7.8 Hz thinking pulse (matching Tensura popup) across iris, techwear power conduits, and hair sheen.
     - **🔷 Speaking (`#3296FA` Electric Blue):** 5.5 Hz electric blue pulse with real-time audio amplitude / lip-sync energy modulation from vowel openness (`aa`, `oh`).
     - **🔴 Error (`#FF3B30` Alert Crimson):** Fast 8.5 Hz warning pulse across iris, outfit piping, and spatial lighting.
  2. **Multi-Layer VRM Material Coverage & Dedicated Emissive Maps:**
     - Updated `collectEmissiveMaterials(vrm)` to track all cybernetic elements: eye irises, techwear piping/seams, hair strands, and accessories.
     - **Root Cause & Fix for Ren:** Previously, VRoid set `_EmissionMap` to `Shader_NoneBlack` (all 0,0,0 black pixels), which multiplied `mat.emissive` by 0 in the MToon fragment shader. Synthesized dedicated 2048x2048 and 1024x512 emissive circuit maps matching Airi:
       - Texture 25: Iris emissive map (glowing iris conduits)
       - Texture 26: Tops emissive map (zippers, shoulder piping, collar conduits)
       - Texture 27: Bottoms cargo emissive map (pocket straps, buckle conduits)
       - Texture 28: Shoes runner emissive map (soles, laces conduits)
       - Texture 29: Hair sheen emissive map
     - Material shader now dynamically lights up and changes color in real time across all states.
  3. **Synced & Verified:** Changes live in `viewer/app.js` and synced to the IDE branch worktree.




