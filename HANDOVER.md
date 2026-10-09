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
