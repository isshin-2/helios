# HELIOS — BYOK and BYOHW Guide

## Bring Your Own Key (BYOK)

HELIOS supports multiple cloud and local inference providers. You supply the keys — HELIOS never stores or transmits them beyond the provider you configure.

### Supported Providers

| Provider | Env Var | Notes |
|----------|---------|-------|
| Ollama (local) | `OLLAMA_HOST` | Default `http://127.0.0.1:11434` |
| vLLM / LM Studio / SGLang | `VLLM_API_BASE` | OpenAI-compatible endpoint |
| PAIR (AI PC cluster) | `PAIR_HOST` | Your own remote Ollama node |
| FreeLLMAPI | `FREELLMAPI_URL` | Free-tier proxy — no key required |
| Google Gemini | `GEMINI_API_KEY` | Cloud |
| Groq | `GROQ_API_KEY` | Cloud |
| NVIDIA NIM | `NVIDIA_API_KEY` | Cloud |
| OpenRouter | `OPENROUTER_API_KEY` | Cloud (routes to many models) |

### Configuring Keys

1. Copy `.env.example` to `ai-router/.env`
2. Fill in only the providers you want to use — leave others blank
3. Keys are read at startup and never logged or exported

```bash
# Example: use Gemini + local Ollama
LLM_PROVIDER=ollama
OLLAMA_HOST=http://127.0.0.1:11434
GEMINI_API_KEY=AIza...your_key_here...
```

### Revoking Keys

1. Remove or blank the relevant env-var in `ai-router/.env`
2. Restart HELIOS

### Key Security Guarantees

- Keys are **never** included in prompts, log files, telemetry, or exported configs
- The secret redactor (`core/secret_redactor.py`) scrubs known key patterns from all output
- Keys are not committed to git (`.env` is in `.gitignore`)
- OS credential store (`keyring`) integration is planned for a future release

### Local-Only Privacy Mode

Set `LOCAL_ONLY=true` in `.env` to prevent HELIOS from routing any request to a cloud provider:

```
LOCAL_ONLY=true
```

In local-only mode:
- All requests are routed to Ollama, vLLM, or PAIR only
- If local inference is unavailable, HELIOS explains why and stops — it does not fall back to cloud
- Screenshots, audio, and code are never transmitted externally

### Provider Transparency

Before sending a request, the model router reports which provider and model will receive it. This is shown in:
- API response headers (`X-HELIOS-Provider`)
- The web HUD status bar
- The audit log

---

## Bring Your Own Hardware (BYOHW)

HELIOS runs entirely on your hardware. There is no required cloud compute.

### Local Hardware Options

| Setup | Description |
|-------|-------------|
| **Solo workstation** | Single machine running both HELIOS and Ollama |
| **AI PC cluster** | Powerful GPU workstation running Ollama; HELIOS on a laptop |
| **vLLM / LM Studio** | Self-hosted OpenAI-compatible inference server |
| **SGLang** | High-performance inference for large models |

### Hardware Profiling

On first run, HELIOS profiles your hardware:

```
scripts/run_audit.py   # Manual hardware audit
```

The profiler detects:
- Available RAM (physical and available)
- GPU presence and VRAM (via NVIDIA-SMI or ROCm-SMI)
- CPU model and core count

### Model Recommendations

Based on detected hardware, HELIOS recommends models from the agent profiles in `config/agent_profiles.yaml`. The VRAM-aware model router:

1. Selects the best model for available VRAM
2. Falls back to smaller models if the primary cannot fit
3. Enables RAM offload when VRAM is insufficient
4. Respects configured `max_concurrent_large_models` limit

### Model Downloads

HELIOS **does not download models automatically without consent.** The first-run provisioner checks for Whisper models and prompts before downloading.

To pull models manually:
```bash
ollama pull qwen2.5-coder:14b    # Coding agent
ollama pull nomic-embed-text     # Memory embeddings
```

### AI PC (Remote GPU) Setup

If you have a dedicated GPU workstation:

1. Install and run Ollama on the GPU machine
2. Set in `ai-router/.env`:
   ```
   LLM_PROVIDER=pair
   PAIR_HOST=http://192.168.x.x:11434
   AI_PC_IP=192.168.x.x
   ```
3. Optionally enable Wake-on-LAN:
   ```
   AUTO_WAKE_AI_PC=true
   AI_PC_MAC=AA:BB:CC:DD:EE:FF
   ```

### Resource Controls

Control resource usage via `.env`:

| Setting | Default | Description |
|---------|---------|-------------|
| `GPU_RESERVE_MB` | `2048` | GPU memory reserved for OS/display |
| `RAM_RESERVE_GB` | `8` | RAM reserved for OS |
| `RAM_CACHE_LIMIT_GB` | `32` | Max RAM for model cache |
| `TTS_IDLE_UNLOAD_SECONDS` | `300` | Unload TTS after idle period |

### Context Size

Adjust per agent in `config/agent_profiles.yaml` or globally:

```yaml
# config/agent_profiles.yaml
coder:
  model: qwen2.5-coder:14b
  options:
    num_ctx: 16384   # tokens
```
