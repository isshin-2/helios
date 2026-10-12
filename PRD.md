# Product Requirements Document (PRD): HELIOS Autonomous Evolution & Ralph Loop

## 🎯 Objective
Establish an iterative Ralph Loop execution workflow for HELIOS. Complete, validate with automated tests, and create atomic git commits for each architectural milestone to ensure instant rollback capability.

---

## Task 1: HELIOS Character Tuner Studio Modal & Isolated Twin Pose Calibration
- **Component:** `helios-character/`
- **Scope:**
  - Standalone slide-over studio modal (`#adjust-studio-modal`) for prop and biomechanical body pose adjustments.
  - Isolated twin adjustments (`twinBodyPoseAdjustments.airi` vs `twinBodyPoseAdjustments.ren`) ensuring zero interference between siblings.
  - 3D prop rotation controls (pitch, yaw, roll) and clean holographic optic (removal of dark boom mic lines and boxes).
- **Validation Criteria:**
  - `python -m py_compile helios-character/test_adjuster_menu.py` passes without syntax error.
  - Node.js syntax validation on `helios-character/viewer/app.js`.
- **Commit Target:**
  - Stage: `helios-character/viewer/index.html`, `helios-character/viewer/app.js`, `helios-character/test_adjuster_menu.py`, `helios-character/`
  - Message: `feat(helios-character): standalone tuner studio modal and isolated twin pose calibration`

---

## Task 2: Ecosystem Triad Partitioning & Zero-Friction Bootstrap
- **Component:** `core/`, `engines/`, `docs/`, `setup.bat`
- **Scope:**
  - Architectural triad partitioning (`HELIOS` :8000, `Hikari` :8001, `Solstice` :8082, `Viewer` :8080).
  - Physical database segregation (`data/helios.db`, `data/hikari.db`, `data/solstice.db`).
  - Zero-Trust BridgeGuard HMAC-SHA256 signatures, zero-leak credential scrubber, and local voice biometrics gate.
  - Zero-friction bootstrap runner (`setup.bat` and `scripts/bootstrap.py`) with hardware profiling and budget governor.
  - Antigravity CLI slash command dispatcher (`helios.bat` and `helios_cmd.py`).
- **Validation Criteria:**
  - `.\helios.bat /test-isolation` passes 7/7 tests (100%).
  - `.\setup.bat --dry-run` executes with 0 errors.
- **Commit Target:**
  - Stage: `setup.bat`, `helios.bat`, `helios_cmd.py`, `scripts/`, `docs/`, `core/`, `engines/`, `tests/test_isolation.py`
  - Message: `feat(core): triad process partitioning, zero-friction bootstrap, and hardware governor`

---

## Task 3: Interactive Ecosystem Customizations & Developer Connectors Studio
- **Component:** `connectors/`, `ai-router/static/app.html`, `tests/test_connectors.py`
- **Scope:**
  - Interactive Ecosystem Customization Wizard via `setup.bat -c` and `/custom`.
  - Developer Connectors Studio Modal in HELIOS Web UI (`ai-router/static/app.html`) with Installed Connectors, Scaffolding Code Generator, and Live Sandbox Playground.
  - Extensible `BaseConnector` registry with schema validation and error containment.
- **Validation Criteria:**
  - `.\ai-router\venv\Scripts\python.exe -m pytest tests/test_connectors.py -v` passes 4/4 tests (100%).
  - `.\helios.bat /custom --dry-run` executes without error.
- **Commit Target:**
  - Stage: `connectors/`, `ai-router/static/app.html`, `tests/test_connectors.py`, `config/custom_profile.json`
  - Message: `feat(connectors): developer connectors studio and ecosystem customization wizard`

---

## Task 4: Autonomous Ralph Loop CLI Integration & Test Runner
- **Component:** `scripts/ralph_runner.py`, `helios_cmd.py`, `prompt.md`
- **Scope:**
  - Implement native Ralph Loop execution harness in `scripts/ralph_runner.py`.
  - Register `/ralph` command in `helios_cmd.py` with flags `--task-file`, `--progress-file`, `--max-iterations`, and `--run-once`.
  - Validate tests at every step and automatically append commit hashes and rollback recipes to `progress.txt`.
- **Validation Criteria:**
  - `.\helios.bat /ralph --help` or `--status` executes cleanly.
  - All tests in `tests/` pass 100%.
- **Commit Target:**
  - Stage: `scripts/ralph_runner.py`, `helios_cmd.py`, `prompt.md`, `PRD.md`, `progress.txt`
  - Message: `feat(ralph): autonomous ralph loop cli integration with per-step testing and rollback tracking`
