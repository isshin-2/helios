# HELIOS — Security Documentation

## Overview

HELIOS can access files, microphones, screens, applications, credentials, and command execution. **The LLM model is never the security authority.** All capability decisions flow through the centralized `PermissionManager`.

```
LLM → Router → Skill → PermissionManager → ApprovalManager → OS/FS
```

---

## 1. Permission Broker

**File:** `ai-router/security/permissions.py`

Every tool call (filesystem, terminal, computer control, browser) must pass through `PermissionManager` before execution. The manager:

- Checks the calling user's configured `system_access` policy
- Validates filesystem paths against an explicit allow-list
- Blocks unconditionally dangerous commands (`BLOCKED_COMMANDS` set)
- Requires approval for privileged operations (`PRIVILEGED_COMMANDS` set)
- Logs all decisions to `audit_log` in SQLite

**Blocked commands (never allowed):**  
`powershell`, `cmd`, `bash`, `rm`, `del`, `format`, `diskpart`, `reg`, `regedit`, `shutdown`, `net`, `netsh`, `schtasks`, `taskkill`, `kill`, `sudo`, `curl`, `wget`, and others.

**Privileged commands (require explicit user approval):**  
`npm`, `pip`, `git`, `node`, `python`, `cargo`, `gcc`, `make`, and others.

---

## 2. Path Firewall

Filesystem operations (read, write, list) are validated against configured allowed paths. By default, only the HELIOS directory is accessible. Users must explicitly grant additional paths.

- **Symlink traversal** is blocked (resolved path must be within the allow-list)
- **Parent directory traversal** (`../`) is rejected
- **System directories** (`C:\Windows`, `/etc`, `/proc`) are never in the default allow-list

---

## 3. WebSocket Authentication

WebSocket endpoints (`/chat`, `/ws/voice`, `/ws/computer`) are bound to `127.0.0.1` by default. Remote access requires explicit configuration with authentication.

To configure LAN access:
1. Set `HELIOS_BIND_HOST=0.0.0.0` in `.env` (not recommended without a reverse proxy)
2. Set `HELIOS_WS_SECRET=<strong-random-token>` — clients must supply this in the Authorization header
3. Use a TLS-terminating reverse proxy (nginx, Caddy) for external access
4. Never expose port 8000 directly to the public internet

---

## 4. Secret Management

### API Keys
- Cloud API keys (Gemini, Groq, OpenRouter, NVIDIA) are stored in `.env` files only
- Keys are never logged, never included in prompts, never exported in config backups
- The secret redactor (`core/secret_redactor.py`) scrubs known key patterns from all log and telemetry output
- OS credential store integration (via `keyring`) is planned for a future release

### Environment Files
- `.env` files are in `.gitignore` — never commit them
- Use `.env.example` as the template (no real keys in the example)
- `VLLM_API_KEY` defaults to `"sk-helios"` (local dummy) and can be overridden via env-var

### License Files
- License files contain only license metadata (ID, products, expiry, signature)
- No payment data or personal information is stored in the license file
- The private signing key is never bundled in the application

---

## 5. Prompt Injection Defence

HELIOS processes untrusted content from files, web pages, screenshots, and tool outputs. Potential injection points:

| Source | Mitigation |
|--------|-----------|
| File contents | Content passed as tool results, not as system prompt |
| Web page text | Browser agent marks content as `[EXTERNAL CONTENT]` |
| Screenshots | OCR output is tagged; not used to override tool calls |
| LLM tool calls | All calls validated by PermissionManager before execution |

> **Note:** The previous `[SYSTEM OVERRIDE]` prompt injection in `config.py` has been removed (commit: Phase A security fixes). It is no longer present in the codebase.

---

## 6. Sandbox and Workspace Isolation

Coding agents operate within workspace boundaries:
- File writes are restricted to the configured workspace directory
- Docker sandbox (when enabled) provides additional CPU, memory, and filesystem limits
- `DOCKER_SANDBOX_ENABLED=true` in `.env` activates sandboxed execution for code tests

---

## 7. Telemetry and Privacy

- All telemetry is written to local `logs/telemetry.jsonl` only
- No data is sent to any external server by HELIOS itself
- Telemetry records are redacted by `secret_redactor.redact_dict()` before writing
- Users can disable telemetry logging by deleting or not creating the `logs/` directory
- HELIOS never prompts users to send telemetry to developers

---

## 8. Desktop Control Safety

Computer / VLA control (`ai-router/tools/computer.py`, `agents/computer_agent.py`):

- Every action (click, type, screenshot) is logged to the audit log
- **Global stop** is available via the UI or by sending `SIGTERM` to the process
- Microphone recording status is logged on start/stop
- Screen capture is performed locally — frames are never transmitted to external services unless the user explicitly sends them to a cloud vision model

---

## 9. Network Binding

| Default | Setting |
|---------|---------|
| Bind to `127.0.0.1` only | Configurable via `HELIOS_BIND_HOST` |
| No LAN exposure without opt-in | `HELIOS_BIND_HOST=0.0.0.0` enables LAN (requires auth) |
| No public internet exposure | Route through authenticated reverse proxy only |

---

## 10. Known Remaining Risks

| Risk | Status | Mitigation |
|------|--------|-----------|
| WebSocket auth enforcement on all endpoints | Planned (Phase F) | Currently loopback-only by default |
| OS credential store for API keys | Planned | `.env` only for now |
| Prompt injection from file contents | Partial | Tool-result tagging; full scanner planned |
| PyQt5 GPL copyleft on desktop binary | Open | Consider PySide6 migration |
| VRM model redistribution rights | Unverified | Must audit before commercial distribution |
| Reference voice audio rights | Unverified | Must audit before commercial distribution |

---

## Reporting Security Issues

Do not file public issues for security vulnerabilities. Contact the project owner privately with a description of the issue and reproduction steps.
