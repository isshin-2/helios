# HELIOS Handover & Orchestration Spec

## 🎯 Primary Goal
**Finalize & stabilize the uncommitted Vision-Language-Action (VLA) computer control, GPT-SoVITS TTS, and Mobile V2 streaming integration.**

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
| **TASK-01** | `ai-router/tests` | Fix `test_computer_control_move` assertion for structured JSON | `@IDE-Agent READY` | IDE Agent |
| **TASK-02** | `ai-router/tools` | Update `mss.mss()` to `mss.MSS()` deprecation warning | `@IDE-Agent READY` | IDE Agent |
| **TASK-03** | `ai-router/vla` | Ensure root `vla_engine.py` and `SYSTEM_AUDIT.md` path alignment | `@IDE-Agent READY` | IDE Agent |
| **TASK-04** | `ai-router/tts` | Stabilize GPT-SoVITS audio normalizer & resource policy contracts | `@Orchestrator VERIFIED` | Orchestrator |
| **TASK-05** | `mobile_v2` | Type check and verify `/ws/hikari` terminal streaming client | `@Orchestrator VERIFIED` | Orchestrator |
| **TASK-06** | `ai-router/core` | Run unified regression suite (Core Suite + VLA + TTS + Computer) | `BLOCKED` on TASK-01 | Orchestrator |

---

## 🛠️ Detailed Engineering Task Specifications

### [TASK-01] Fix `test_computer_control_move` assertion for structured JSON
- **Status:** `@IDE-Agent READY`
- **File:** `ai-router/tests/test_computer_control.py` (Line 20-30)
- **Problem Statement:**
  `ComputerControlTool.execute` was upgraded to return a JSON-serialized `ActionResult` model (`model_dump_json()`). The test `test_computer_control_move()` fails with:
  ```text
  assert 'Moved mouse to (500, 400)' in '{"success": true, "action": "move", "target": {"x": 500, "y": 400}, ...}'
  ```
- **Required Action:**
  1. Open `ai-router/tests/test_computer_control.py`.
  2. Parse the return value `res` using `json.loads(res)` (or verify with `ActionResult.model_validate_json(res)`).
  3. Assert `data["success"] is True`.
  4. Assert `data["action"] == "move"`.
  5. Assert `data["target"] == {"x": 500, "y": 400}`.
- **Verification Command:**
  ```powershell
  .\ai-router\venv\Scripts\python.exe -m pytest ai-router/tests/test_computer_control.py -k test_computer_control_move
  ```
- **Tag on Completion:** Change status to `@IDE-Agent COMPLETED`.

---

### [TASK-02] Update `mss.mss()` to `mss.MSS()` deprecation warning
- **Status:** `@IDE-Agent READY`
- **Files:**
  - `ai-router/tools/screen_vision.py` (Line ~45)
  - `ai-router/tests/test_computer_control.py` (Line ~52)
- **Problem Statement:**
  The `mss` library outputs:
  ```text
  DeprecationWarning: mss.mss is deprecated and will be removed in a future release; use mss.MSS instead
  ```
- **Required Action:**
  1. In `ai-router/tools/screen_vision.py`, change `with mss.mss() as sct:` to `with mss.MSS() as sct:`.
  2. In `ai-router/tests/test_computer_control.py`, change `with mss.mss() as sct:` to `with mss.MSS() as sct:`.
- **Verification Command:**
  ```powershell
  .\ai-router\venv\Scripts\python.exe -m pytest ai-router/tests/test_computer_control.py
  ```
- **Tag on Completion:** Change status to `@IDE-Agent COMPLETED`.

---

### [TASK-03] Ensure root `vla_engine.py` and `SYSTEM_AUDIT.md` path alignment
- **Status:** `@IDE-Agent READY`
- **Files:**
  - `vla_engine.py` (root)
  - `ai-router/vla_engine.py`
  - `SYSTEM_AUDIT.md` (root)
- **Problem Statement:**
  Verify that the root wrapper `vla_engine.py` correctly bootstraps `ai-router/vla_engine.py` and points to the root `SYSTEM_AUDIT.md` hash cache without duplicate drift.
- **Required Action:**
  1. Inspect `vla_engine.py` at root and in `ai-router/vla_engine.py`.
  2. Ensure default path to `SYSTEM_AUDIT.md` gracefully checks both `SYSTEM_AUDIT.md` (root) and `ai-router/SYSTEM_AUDIT.md`.
- **Verification Command:**
  ```powershell
  .\ai-router\venv\Scripts\python.exe -m pytest ai-router/tests/test_vla_framework.py
  ```
- **Tag on Completion:** Change status to `@IDE-Agent COMPLETED`.

---

### [TASK-04] Stabilize GPT-SoVITS audio normalizer & resource policy contracts
- **Status:** `@Orchestrator VERIFIED`
- **Summary:** Verified 38/38 unit and integration tests passing in `test_tts_pipeline.py` and `test_gpt_sovits_resource_manager.py`.

---

### [TASK-05] Type check and verify `/ws/hikari` terminal streaming client
- **Status:** `@Orchestrator VERIFIED`
- **Summary:** Verified `mobile_v2` compiles with 0 errors via local TypeScript compiler (`tsc.cmd --project mobile_v2/tsconfig.json --noEmit`).

---

### [TASK-06] Unified Ecosystem Regression Run
- **Status:** `BLOCKED` (Waiting for TASK-01 and TASK-02)
- **Goal:** Execute all unit, contract, and subsystem test suites in one master run.
- **Target Suites:**
  - `test_helios_core_suite.py` (6 tests)
  - `test_computer_control.py` + `test_computer_system.py` (28 tests)
  - `test_tts_pipeline.py` + `test_gpt_sovits_resource_manager.py` (26 tests)
  - `test_vla_framework.py` (12 tests)
