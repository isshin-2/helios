# HELIOS Architecture Deep-Dive

HELIOS operates on a strict, component-based pipeline where the LLM acts purely as a reasoning engine, while all side-effects and context management are tightly controlled by the backend orchestration layer.

## The Request Lifecycle (`ConversationOrchestrator`)
1. **Intake**: A user sends a message via the UI over a WebSocket connection (or via the Headless API).
2. **Memory Extraction**: The `MemoryManager` evaluates if the user's prompt contains personal facts to save, or if past facts should be injected into the system prompt.
3. **Routing**: `router/classifier.py` analyzes the prompt (Intent, Detail, Complexity, Tools Needed). `router/rules.py` then determines the exact routing strategy (e.g., 'coding', 'reasoning', 'general').
4. **Tool Loop**: If the route allows tools, the `ToolRouter` prepares the available Pydantic schemas. The LLM can call tools iteratively.
5. **Model Loading & Offloading**: The `ModelManager` prepares the optimal model for the route, proactively offloading inactive models if VRAM is constrained.
6. **Streaming Response**: The final generation is streamed back to the frontend.

## The Zero-Trust Sandbox (`PermissionManager`)
HELIOS trusts the LLM to generate text, but *never* trusts it to execute code blindly.
- **Path Resolution**: All filesystem tools resolve relative paths to absolute paths and verify they lie within the user's explicit `allowed_directories`.
- **Blocked System Paths**: Hardcoded filters prevent access to sensitive OS directories (e.g., `C:\Windows`, `/etc`).
- **Human Approval Workflow**: Destructive operations (like `file_writer` or `terminal`) halt the pipeline and send an `approval_request` to the frontend. Execution resumes only when the user clicks "Approve".

## Memory-Aware Model Management
- **Status Polling**: The `SystemMonitor` continuously polls Ollama's `ps` endpoint to determine active VRAM usage.
- **Dynamic Offloading**: When a new model is requested, `ModelManager.ensure_model_loaded` compares the system's available RAM against the model's footprint + a context buffer. If insufficient, it iteratively unloads the largest non-target models via the Ollama API (`keep_alive=0`) until memory is freed.
- **Fallback Chains**: If a model fails to load or crashes, HELIOS automatically falls back to smaller, more resilient models (defined in `config.py`).

## The Self-Modification Framework
- The `SelfModificationTool` allows HELIOS to propose edits to its own source code.
- Instead of writing directly, it creates isolated `ExperimentWorkspace` branches.
- It applies diffs, runs safety checks, and benchmarks the new code in an ephemeral state.
- If successful, the experiment enters an `AWAITING_APPROVAL` status via the API, awaiting human deployment.
