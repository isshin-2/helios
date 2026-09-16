# Final Verification Report: HELIOS Skillspector Security & Dockerization

## 1. Architecture Decisions

### Why Subprocess for Skillspector?
Calling Skillspector via the Python API (`graph.invoke`) can conflict with HELIOS's dependencies (e.g., Pydantic or LangChain versions) and limits our ability to strictly enforce OS-level isolation and timeouts. By wrapping the Skillspector CLI in a `subprocess.run(["skillspector", "scan", "-f", "json", "--no-llm"])` call, we isolate the HELIOS core from the scanning environment, ensure strict timeout enforcement, and cleanly parse structured JSON results regardless of internal scanner warnings.

### Why a Read-Only Mount for Skills?
Mounting the skills directory as read-only (`./skills:/app/skills:ro`) adheres to the Principle of Least Privilege. Skills should not be able to dynamically modify their own source code or drop executable payloads into their module directory at runtime. This forces any runtime artifacts to be written to ephemeral container storage or properly designated temp directories, preventing persistence of malicious modifications. Quarantine metadata is written to a designated `/app/quarantine` directory outside the read-only mount.

## 2. Security Proofs

We implemented a fail-closed policy where any scan timeout, error, or `DO_NOT_INSTALL` recommendation immediately results in quarantine.

**How the malicious test proved the policy:**
We created a `malicious_skill_test.py` fixture that contains a module-level side effect (writing a file `malicious_marker.txt`) and a dangerous payload (`subprocess.run("curl ... | bash")`).
During dynamic skill discovery (`manifest.py`), the file is scanned by Skillspector *before* it is imported. Skillspector detects the "Dangerous Code Execution" signature and returns a `DO_NOT_INSTALL` (or `ERROR`) recommendation. 
Because the policy is fail-closed, HELIOS immediately quarantines the file and completely skips the Python import. As proven by the `test_skillspector_security.py` suite, `malicious_marker.txt` is never created, confirming that the malicious module's code—even at the top level—is never executed.

## 3. Docker Setup Instructions

HELIOS can now be run securely via Docker Compose.

**To build and start:**
```bash
docker compose up -d --build
```

**Key Container Features:**
* Runs on a minimal `python:3.12-slim` base image (bumped from 3.11 because Skillspector requires Python 3.12+).
* Executes as a non-root `helios` user.
* Skills directory is mounted read-only.
* API is exposed on port `8000`.
* Quarantine metadata is safely persisted in the container at `/app/quarantine`.

**To view logs:**
```bash
docker compose logs -f helios-core
```

## 4. Future Recommendations for LLM-Based Scanning

Currently, LLM-based scanning is disabled (`SKILLSPECTOR_LLM_ANALYSIS=false` and `--no-llm` flag) to ensure fast, deterministic booting.

If LLM-based analysis is enabled in the future:
1. **Asynchronous Scanning:** LLM analysis can take significantly longer (15-60+ seconds per skill). Dynamic loading at boot time would become unacceptably slow. Consider moving LLM scanning to an out-of-band asynchronous worker (e.g., Celery) or an explicit "Install Skill" API endpoint rather than scanning at boot time.
2. **LLM Timeouts:** Ensure API timeouts for the LLM are strict, as a slow LLM provider could hang the entire router boot sequence.
3. **Caching:** Implement a hash-based cache (e.g., SHA256 of the skill file) so that unchanged skills do not require re-evaluation by the LLM on every boot. This is highly recommended even for heuristic scanning to optimize startup speed.
