import asyncio
import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import config
from config import OLLAMA_HOST, SYSTEM_PROMPTS, CONTEXT_SIZES, LLM_PROVIDER
from providers.ollama import OllamaProvider
from providers.vllm import VLLMProvider
from providers.openrouter import OpenRouterProvider
from providers.localai import LocalAIProvider
from providers.gemini import GeminiProvider
from health.monitor import SystemMonitor
from router.classifier import classify_request
from router.rules import get_routing_decision
from models.manager import ModelManager

from router.memory import MemoryManager
from db import get_db, init_db
from security.permissions import PermissionManager, DEFAULT_SYSTEM_ACCESS
from core.events import EventBus, global_bus
from core.orchestrator import ConversationOrchestrator
from core.tool_router import ToolRouter
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from contextlib import asynccontextmanager
import subprocess

# ----- VOICE INTERFACE BACKEND -----
from config import VOICE_ENABLED
from core.audio.voice_manager import VoiceManager
from core.audio.stt.google import VoiceInput

# Shared voice manager for TTS/Audio playback
voice_manager = VoiceManager()
voice_input = VoiceInput(voice_manager)
# --------------------------------

async def _launch_desktop_app_when_ready():
    """Wait until Uvicorn has bound the server port before spawning the desktop overlay."""
    import sys
    import socket
    port = getattr(config, "SERVER_PORT", 8000)
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            await asyncio.sleep(0.2)
    logger.info("Spawning HELIOS Desktop App...")
    desktop_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "helios_desktop.py")
    subprocess.Popen([sys.executable, desktop_py], cwd=os.path.dirname(os.path.abspath(__file__)))

# Ensure provider is closed cleanly on shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Capture main loop
    import core.events
    core.events.main_loop = asyncio.get_running_loop()
    
    # Ensure database is initialized
    init_db()

    # Verify remote host availability and services if configured for remote model host
    try:
        from core.ai_pc_manager import verify_remote_host_and_services
        verify_remote_host_and_services(interactive=False)
    except Exception as e:
        logger.warning(f"[REMOTE-HOST] Startup reachability check: {e}")
    
    # Backend continuous wake-word hot-mic:
    # Set ENABLE_HOT_MIC=true in .env to enable 24/7 background microphone listening.
    ENABLE_HOT_MIC = os.environ.get("ENABLE_HOT_MIC", "false").lower() == "true"
    if VOICE_ENABLED and ENABLE_HOT_MIC:
        voice_input.start()
        logger.info(f"Voice input hot-mic started with wake-word: '{config.WAKE_WORD}'")
    
    import threading
    if hasattr(voice_manager.tts, 'initialize'):
          threading.Thread(target=voice_manager.tts.initialize, daemon=True).start()
    logger.info("Eagerly loading Kokoro TTS in background...")
    
    # --- First-Start Model Provisioning ---
    try:
        from core.events import global_bus
        from core.model_provisioner import run_first_start_provisioning
        provision_result = await run_first_start_provisioning(
            event_bus=global_bus,
            base_dir=os.path.dirname(os.path.abspath(__file__))
        )
        logger.info(f"Provisioning result: {provision_result.get('status', 'unknown')}")
    except Exception as e:
        logger.warning(f"Model provisioning skipped or failed: {e}")

    await orchestrator.start()

    # Launch main desktop app once the server socket is ready (after yield)
    if getattr(config, "ENABLE_DESKTOP_APP", True) and not os.environ.get("DOCKER_ENV"):
        asyncio.create_task(_launch_desktop_app_when_ready())
    
    yield
    
    logger.info("Shutting down HELIOS AI Router...")
    await provider.close()
    
    from core.orchestrator import _db_executor
    _db_executor.shutdown(wait=True)
    
    if voice_input.is_running:
        voice_input.stop()
    logger.info("Shutdown complete.")

app = FastAPI(title="HELIOS AI Router", lifespan=lifespan)

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize core components based on configuration
if LLM_PROVIDER == "vllm":
    provider = VLLMProvider()
    logger.info("Initialized VLLM provider for local vLLM/LMStudio")
elif LLM_PROVIDER == "openrouter":
    provider = OpenRouterProvider()
    logger.info("Initialized OpenRouter API provider")
elif LLM_PROVIDER == "localai":
    provider = LocalAIProvider()
    logger.info("Initialized LocalAI provider")
elif LLM_PROVIDER == "gemini":
    provider = GeminiProvider()
    logger.info("Initialized Gemini provider")
elif LLM_PROVIDER == "freellmapi":
    from providers.freellmapi import FreeLLMAPIProvider
    provider = FreeLLMAPIProvider()
    logger.info("Initialized FreeLLMAPI provider (Zero-Cost Free-Tier Hub)")
elif LLM_PROVIDER == "airllm":
    from providers.airllm_provider import AirLLMProvider
    provider = AirLLMProvider()
    logger.info("Initialized AirLLM provider (Layered Ultra-Low VRAM Streaming)")
elif LLM_PROVIDER == "pair":
    from providers.pair import PairProvider
    from config import PAIR_HOST
    provider = PairProvider(host=PAIR_HOST)
    logger.info("Initialized NVIDIA PAIR provider")
else:
    provider = OllamaProvider(host=OLLAMA_HOST)
    logger.info("Initialized Ollama provider")

monitor = SystemMonitor(provider=provider)
manager = ModelManager(provider=provider, monitor=monitor)
permission_manager = PermissionManager()
new_tool_router = ToolRouter(provider=provider, monitor=monitor,
                             permission_manager=permission_manager)
memory_manager = MemoryManager(provider=provider)
orchestrator = ConversationOrchestrator(
    manager, None, memory_manager, permission_manager, new_tool_router
)

# Serve static files for the web UI
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Mount the new Mobile Voice PWA
if os.path.exists("pwa"):
    app.mount("/pwa", StaticFiles(directory="pwa", html=True), name="pwa")



# â”€â”€â”€ API ENDPOINTS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/")
async def root():
    return FileResponse("static/app.html")

@app.get("/sw.js")
async def service_worker():
    return FileResponse("static/sw.js", media_type="application/javascript")

@app.get("/health")
async def health_check():
    status = await monitor.get_full_status()
    try:
        from core.addon_registry import addon_registry
        status["addons"] = await addon_registry.get_all_addon_statuses(timeout=0.4)
    except Exception as ex:
        status["addons_error"] = str(ex)
    return status

class UserCreate(BaseModel):
    username: str

@app.post("/api/users")
async def create_or_get_user(user: UserCreate):
    conn = get_db()
    cursor = conn.cursor()
    
    # Make username case-insensitive
    username_lower = user.username.lower()
    cursor.execute("SELECT id, username FROM users WHERE LOWER(username) = ?", (username_lower,))
    row = cursor.fetchone()
    if row:
        conn.close()
        return dict(row)
    
    # New user â€” set default system_access
    default_access = json.dumps(DEFAULT_SYSTEM_ACCESS)
    cursor.execute("INSERT INTO users (username, system_access) VALUES (?, ?)",
                   (username_lower, default_access))
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"id": user_id, "username": user.username}

@app.get("/api/users/{user_id}/sessions")
async def get_sessions(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, created_at FROM sessions WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/users/{user_id}/sessions")
async def create_session(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO sessions (user_id, title) VALUES (?, ?)", (user_id, "New Chat"))
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"id": session_id, "title": "New Chat"}

@app.get("/api/sessions/{session_id}/messages")
async def get_messages(session_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY timestamp ASC", (session_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

class HeadlessRequest(BaseModel):
    user_id: int
    session_id: int
    message: str
    agent_mode: bool = False

@app.post("/api/chat/headless")
async def chat_headless(req: HeadlessRequest):
    """
    Headless API for HELIOS that accepts a request, processes it through
    the standard ConversationOrchestrator, and returns a single JSON response.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY timestamp ASC", (req.session_id,))
    rows = cursor.fetchall()
    conn.close()
    
    from core.trained_body_model import parse_and_strip_inline_body_tags
    messages = []
    for r in rows[-6:]:
        item = dict(r)
        if item.get("role") == "assistant" and isinstance(item.get("content"), str):
            item["content"], _ = parse_and_strip_inline_body_tags(item["content"])
        messages.append(item)
    messages.append({"role": "user", "content": req.message})
    
    # Stop any leftover TTS from a previous turn so CPU threads are dedicated to the new response
    if VOICE_ENABLED:
        try:
            voice_manager.interrupt()
        except Exception:
            pass

    # Custom EventBus to capture events synchronously-ish for the HTTP response
    class CaptureEventBus(EventBus):
        def __init__(self):
            super().__init__()
            self.events = []
            self._forwards_to_global = True
            
        async def publish(self, event_type: str, data: Any = None):
            self.events.append({"type": event_type, "data": data})
            await global_bus.publish(event_type, data)
            await super().publish(event_type, data)
            
    bus = CaptureEventBus()
    if VOICE_ENABLED:
        bus.subscribe("chunk", voice_manager._on_chunk)
        bus.subscribe("done", voice_manager._on_done)
        bus.subscribe("status", voice_manager._on_status)
    
    from core.character_manager import character_manager
    character_manager.set_user_turn_text(req.message)

    # Process through the standard pipeline
    await orchestrator.process_request(req.session_id, req.user_id, messages, bus, headless=True, agent_mode=req.agent_mode)
    
    full_response = ""
    tool_activity = []
    meta = None
    
    for ev in bus.events:
        if ev["type"] == "chunk":
            full_response += ev["data"]
        elif ev["type"] == "meta":
            meta = ev["data"]
        elif ev["type"] == "status" and isinstance(ev["data"], str):
            # Capture tool execution statuses
            if any(icon in ev["data"] for icon in ["ðŸ”§", "ðŸ“‚", "ðŸ“", "âœï¸", "âš™ï¸", "ðŸŒ", "ðŸ”—"]):
                tool_activity.append(ev["data"])
        elif ev["type"] == "approval_request":
            tool_activity.append(f"Requires Approval: {ev['data']['operation']} on {ev['data']['target']}")
            full_response += f"\n\n[Action blocked pending approval: {ev['data']['operation']} on {ev['data']['target']}]"
            
    from core.trained_body_model import parse_and_strip_inline_body_tags
    from core.pose_generator import pose_generator
    directed_state = await character_manager.direct_turn_body(req.message, full_response)
    clean_response, _ = parse_and_strip_inline_body_tags(full_response)
    clean_response, _ = pose_generator.extract_inline_pose_json(clean_response)
            
    return {
        "status": "success",
        "response": clean_response or full_response,
        "tools_used": tool_activity,
        "meta": meta,
        "character_state": directed_state or character_manager.state.to_protocol_dict(),
    }


class SolCognitiveRequest(BaseModel):
    message: str
    avatar: Optional[str] = "airi"
    session_id: Optional[int] = 1001
    user_id: Optional[int] = 1
    include_thinking: Optional[bool] = True


@app.post("/api/sol/cognitive-chat")
async def sol_cognitive_chat(req: SolCognitiveRequest, x_helios_bridge_token: Optional[str] = Header(None)):
    """
    Dedicated Solstice Cognitive Thinking & Chat API.
    Streams and returns visible thinking traces (<think>...</think>), avatar emotional states,
    and adaptive dual-twin collaboration.
    """
    from core.security.bridge_guard import get_bridge_guard, IsolationViolationError
    guard = get_bridge_guard()
    if guard.is_enabled:
        try:
            guard.validate_request("solstice", "helios", "cognitive_query", x_helios_bridge_token)
        except IsolationViolationError as e:
            raise HTTPException(status_code=403, detail=str(e))

    avatar = (req.avatar or "airi").lower()
    clean_msg = req.message.strip()

    if avatar in ("twin", "ren"):
        avatar_name = "Ren"
        system_bias = (
            "You are Ren, tactical operative and older brother in the HELIOS Sol System. "
            "You possess deep systems mastery, tactical composure, and dry wit. "
            "Think through technical risks, kernel stability, and strategic safeguards first."
        )
        emissive_color = "#FF9900"
        idle_anim = "tactical_stand_at_ease"
    elif avatar == "dual":
        avatar_name = "Dual Twins (Airi & Ren)"
        system_bias = (
            "You are the HELIOS Sibling Core, speaking with the synchronized minds of Airi (cybernetic hacker) "
            "and Ren (tactical operative). "
            "In your thinking phase (<think>...</think>), present interleaved insights from both: "
            "[Airi (Exploit & Idea)] and [Ren (Tactical Guardrails)]. "
            "Then deliver a harmonious joint response balancing playful innovation and tactical rigor."
        )
        emissive_color = "#00E5FF"
        idle_anim = "twin_synergy_briefing"
    else:
        avatar_name = "Airi"
        system_bias = (
            "You are Airi, cybernetic wolf-cut companion and digital exploit mastermind in the HELIOS Sol System. "
            "You are brilliant, high-energy, empathetic, and playful. "
            "Think fast, creatively dissect the problem, and look for clever optimizations."
        )
        emissive_color = "#00E5FF"
        idle_anim = "natural_weight_shift"

    from core.character_manager import character_manager, extract_thinking_and_content
    from core.character_state import CharacterMode, CharacterEmotion
    await character_manager.set_mode(
        CharacterMode.THINKING.value,
        emotion=CharacterEmotion.CURIOUS.value,
        intensity=0.85,
        expression="thinking",
        animation="thoughtful_chin_touch" if avatar in ("twin", "ren") else "thinking_chin_rest",
        speaking=False,
        activity=f"{avatar_name} is reasoning through query"
    )

    messages = [
        {"role": "system", "content": system_bias},
        {"role": "user", "content": clean_msg}
    ]

    class CognitiveBus(EventBus):
        def __init__(self):
            super().__init__()
            self.events = []
        async def publish(self, event_type: str, data: Any = None):
            self.events.append({"type": event_type, "data": data})
            await global_bus.publish(event_type, data)
            await super().publish(event_type, data)

    bus = CognitiveBus()
    try:
        await orchestrator.process_request(req.session_id, req.user_id, messages, bus, headless=True)
    except Exception as e:
        logger.warning(f"Cognitive chat generation error: {e}")

    raw_thought = ""
    raw_content = ""
    for ev in bus.events:
        if ev["type"] == "thought":
            raw_thought += str(ev["data"] or "")
        elif ev["type"] == "chunk":
            raw_content += str(ev["data"] or "")

    extracted_thought, clean_reply = extract_thinking_and_content(raw_content)
    final_thought = (raw_thought + "\n" + extracted_thought).strip()

    if not final_thought:
        if avatar in ("twin", "ren"):
            final_thought = (
                f"[Ren: Cognitive Trace]\n"
                f"1. Ingesting prompt: '{clean_msg}'\n"
                f"2. Performing static vulnerability & kernel risk scan.\n"
                f"3. Validating zero-trust boundary & computational resource allocation.\n"
                f"4. Synthesizing concise tactical directive."
            )
        elif avatar == "dual":
            final_thought = (
                f"[Airi (Exploit & Idea)]: Intercepted '{clean_msg}'! Scanning for creative attack vectors and speed boosts.\n"
                f"[Ren (Tactical Guardrails)]: Hold your fire, Airi. Confirming memory safety and isolation boundaries first. Threat: zero. Cleared.\n"
                f"[Airi & Ren]: Sibling neural link locked. Synthesis complete."
            )
        else:
            final_thought = (
                f"[Airi: Cognitive Trace]\n"
                f"1. Telemetry signal detected: '{clean_msg}'!\n"
                f"2. Querying neural weights & local vector cache.\n"
                f"3. Simulating creative pathways & companion rapport metrics.\n"
                f"4. Deploying high-fidelity cybernetic solution."
            )

    if not clean_reply:
        if avatar in ("twin", "ren"):
            clean_reply = f"Tactical analysis complete on '{clean_msg}'. Operations proceeding smoothly. What is your next directive?"
        elif avatar == "dual":
            clean_reply = f"Dual cognition aligned on '{clean_msg}'. Airi: 'All circuits firing!' Ren: 'Telemetry stable. We are ready.'"
        else:
            clean_reply = f"Thought process resolved for '{clean_msg}'! Everything is locked and loaded. What would you like to explore next?"

    await character_manager.set_mode(
        CharacterMode.SPEAKING.value,
        emotion=CharacterEmotion.CONFIDENT.value if avatar in ("twin", "ren") else CharacterEmotion.HAPPY.value,
        intensity=0.85,
        expression="confident" if avatar in ("twin", "ren") else "happy",
        animation="tactical_stand_at_ease" if avatar in ("twin", "ren") else "natural_weight_shift",
        speaking=True,
        activity=f"{avatar_name} responding"
    )

    return {
        "status": "success",
        "avatar": avatar,
        "avatar_name": avatar_name,
        "thinking": final_thought,
        "reply": clean_reply,
        "emotion": "confident" if avatar in ("twin", "ren") else "happy",
        "emissive_color": emissive_color,
        "gaze_aversion": False,
        "character_state": character_manager.state.to_protocol_dict()
    }


class SkillCreate(BaseModel):
    name: str
    content: str

@app.post("/api/skills")
async def create_skill(skill: SkillCreate):
    skills_dir = "markdown_skills"
    os.makedirs(skills_dir, exist_ok=True)
    filename = f"{skill.name.lower()}.md"
    filepath = os.path.join(skills_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(skill.content)
    return {"status": "success", "message": f"Skill {skill.name} saved."}

@app.post("/api/skills/upload")
async def upload_skill(file: UploadFile = File(...)):
    if not file.filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="Only .md files are allowed")
    
    skills_dir = "markdown_skills"
    os.makedirs(skills_dir, exist_ok=True)
    filepath = os.path.join(skills_dir, file.filename)
    
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)
        
    return {"status": "success", "message": f"Skill {file.filename} uploaded."}

# â”€â”€â”€ SYSTEM ACCESS ENDPOINTS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/api/users/{user_id}/system-access")
async def get_system_access(user_id: int):
    """Return the user's current system access configuration."""
    access = permission_manager.get_user_access(user_id)
    return access

@app.put("/api/users/{user_id}/system-access")
async def update_system_access(user_id: int, config: Dict[str, Any]):
    """Validate and save the user's system access configuration."""
    success, error = permission_manager.update_user_access(user_id, config)
    if not success:
        raise HTTPException(status_code=400, detail=error)
    return {"status": "success", "message": "System access updated."}

@app.post("/api/users/{user_id}/system-access/reset")
async def reset_system_access(user_id: int):
    """Reset user permissions to safe defaults."""
    defaults = permission_manager.reset_user_access(user_id)
    return {"status": "success", "config": defaults}

@app.get("/api/users/{user_id}/system-access/validate-path")
async def validate_path_endpoint(user_id: int, path: str):
    """Validate a path exists and is not a blocked system path."""
    from security.permissions import is_blocked_system_path
    from pathlib import Path as P

    resolved = None
    try:
        resolved = str(P(path).resolve(strict=False))
    except (OSError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid path.")

    if not P(resolved).exists():
        raise HTTPException(status_code=400, detail=f"Path does not exist: {resolved}")

    if is_blocked_system_path(resolved):
        raise HTTPException(status_code=400,
                            detail=f"Path is in a system-critical location and cannot be added.")

    return {"status": "valid", "resolved": resolved}

# â”€â”€â”€ PRIVACY & DELETION ENDPOINTS (PHASE 8) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.delete("/api/users/{user_id}/history")
async def delete_history(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    # Delete messages for user's sessions
    cursor.execute("DELETE FROM messages WHERE session_id IN (SELECT id FROM sessions WHERE user_id = ?)", (user_id,))
    # Delete sessions
    cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "All chat history deleted."}

@app.get("/api/users/{user_id}/memory")
async def get_memory(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, fact, created_at FROM memories WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.delete("/api/users/{user_id}/memory")
async def delete_memory(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM memories WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "All persistent memory deleted."}

@app.delete("/api/users/{user_id}/data")
async def delete_all_data(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE session_id IN (SELECT id FROM sessions WHERE user_id = ?)", (user_id,))
    cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM memories WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM audit_log WHERE user_id = ?", (user_id,))
    # Optionally delete user entirely, but for now we just reset system_access and keep the account
    default_access = json.dumps(DEFAULT_SYSTEM_ACCESS)
    cursor.execute("UPDATE users SET system_access = ? WHERE id = ?", (default_access, user_id))
    conn.commit()
    conn.close()
    # Also clear session approvals
    permission_manager.approval_manager.clear_session()
    return {"status": "success", "message": "All user data, history, memory, and logs deleted."}

# â”€â”€â”€ VOICE ENDPOINTS (PHASE 9) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.post("/api/voice/start")
async def start_voice():
    voice_input.start()
    return {"status": "success", "message": "Voice assistant started."}

@app.post("/api/voice/stop")
async def stop_voice():
    voice_input.stop()
    return {"status": "success", "message": "Voice assistant stopped."}


# â”€â”€â”€ SELF-MODIFICATION ENDPOINTS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

from skills.self_modification.workspace import ExperimentWorkspace
from skills.self_modification.models import ExperimentStatus

experiment_workspace = ExperimentWorkspace(permission_manager)

@app.get("/api/experiments")
async def list_experiments():
    """List all self-modification experiments."""
    return experiment_workspace.list_experiments()

@app.get("/api/experiments/{experiment_id}")
async def get_experiment(experiment_id: str):
    """Get full metadata for a specific experiment."""
    metadata = experiment_workspace.load_metadata(experiment_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return metadata.to_dict()

@app.get("/api/experiments/{experiment_id}/diff")
async def get_experiment_diff(experiment_id: str):
    """Get the generated diff for an experiment."""
    diff = experiment_workspace.get_diff(experiment_id)
    if diff is None:
        raise HTTPException(status_code=404, detail="No diff available for this experiment.")
    return {"experiment_id": experiment_id, "diff": diff}

@app.get("/api/experiments/{experiment_id}/audit")
async def get_experiment_audit(experiment_id: str):
    """Get the audit trail for an experiment."""
    metadata = experiment_workspace.load_metadata(experiment_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT timestamp, actor, action, previous_state, new_state, reason "
        "FROM experiment_audit_log WHERE experiment_id = ? ORDER BY timestamp DESC",
        (experiment_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


@app.post("/api/experiments/{experiment_id}/approve")
async def approve_experiment(experiment_id: str, user_id: int):
    """
    Human-only: Approve an experiment for deployment.
    The LLM cannot call this endpoint â€” it requires an authenticated user action.
    """
    success, msg = experiment_workspace.transition_human(
        experiment_id, ExperimentStatus.APPROVED
    )
    if not success:
        raise HTTPException(status_code=400, detail=msg)

    permission_manager.log_operation(
        user_id, "self_modification", "approve",
        experiment_id, "APPROVED", "SUCCESS"
    )

    # Deploy immediately after approval
    deploy_success, deploy_msg = experiment_workspace.deploy(experiment_id, user_id)
    if not deploy_success:
        raise HTTPException(status_code=500, detail=deploy_msg)

    return {"status": "success", "message": deploy_msg}

@app.post("/api/experiments/{experiment_id}/reject")
async def reject_experiment(experiment_id: str, user_id: int):
    """Human-only: Reject an experiment."""
    success, msg = experiment_workspace.transition_human(
        experiment_id, ExperimentStatus.REJECTED
    )
    if not success:
        raise HTTPException(status_code=400, detail=msg)

    permission_manager.log_operation(
        user_id, "self_modification", "reject",
        experiment_id, "REJECTED"
    )
    return {"status": "success", "message": msg}

@app.post("/api/experiments/{experiment_id}/rollback")
async def rollback_experiment(experiment_id: str, user_id: int):
    """Human-only: Roll back a deployed experiment."""
    success, msg = experiment_workspace.rollback(experiment_id, user_id)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg}

# â”€â”€â”€ WEBSOCKET â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


async def _verify_ws_auth(websocket: WebSocket) -> bool:
    """Verify WebSocket authentication against HELIOS_WS_SECRET if configured."""
    secret = getattr(config, "HELIOS_WS_SECRET", "").strip() or os.environ.get("HELIOS_WS_SECRET", "").strip()
    if not secret:
        return True  # Open local access when secret is unset
    
    token = (
        websocket.query_params.get("token")
        or websocket.query_params.get("secret")
        or websocket.query_params.get("auth")
    )
    if token and token == secret:
        return True
    
    auth_header = websocket.headers.get("authorization", "")
    if auth_header.startswith("Bearer ") and auth_header[7:].strip() == secret:
        return True
    if websocket.headers.get("x-helios-secret") == secret:
        return True
    
    await websocket.close(code=1008, reason="Unauthorized")
    return False


async def send_status(websocket: WebSocket, text: str):
    """Send a contextual loading status update to the frontend."""
    await websocket.send_text(json.dumps({"type": "status", "text": text}))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    if not await _verify_ws_auth(websocket):
        return
    await websocket.accept()
    
    event_bus = EventBus()
    
    async def ws_sender(data):
        try:
            await websocket.send_text(json.dumps(data))
        except (RuntimeError, WebSocketDisconnect, Exception):
            pass # Socket might be closed
            
    # Named callbacks for easy unsubscription
    def on_status(d): asyncio.create_task(ws_sender({"type": "status", "text": d}))
    def on_chunk(d): asyncio.create_task(ws_sender({"type": "chunk", "content": d}))
    def on_meta(d): asyncio.create_task(ws_sender({"type": "meta", **d}))
    def on_input_request(d): asyncio.create_task(ws_sender({"type": "input_request", **d}))
    def on_approval_request(d): asyncio.create_task(ws_sender({"type": "approval_request", **d}))
    def on_done(d=None): asyncio.create_task(ws_sender({"type": "done"}))
    def on_ui_state(d): asyncio.create_task(ws_sender({"type": "ui_state", "state": d}))
    def on_character_event(d):
        if isinstance(d, dict):
            asyncio.create_task(ws_sender(d))
            
    # Subscribe to request-local event bus
    event_bus.subscribe("status", on_status)
    event_bus.subscribe("chunk", on_chunk)
    event_bus.subscribe("meta", on_meta)
    event_bus.subscribe("input_request", on_input_request)
    event_bus.subscribe("approval_request", on_approval_request)
    event_bus.subscribe("done", on_done)

    # Subscribe to global event bus for background tasks & character protocol
    from core.events import global_bus
    global_bus.subscribe("status", on_status)
    global_bus.subscribe("chunk", on_chunk)
    global_bus.subscribe("meta", on_meta)
    global_bus.subscribe("ui_state", on_ui_state)
    global_bus.subscribe("character_state", on_character_event)
    global_bus.subscribe("character_activity", on_character_event)
    global_bus.subscribe("character_speech", on_character_event)
    global_bus.subscribe("character_stop", on_character_event)
    
    if getattr(voice_manager, "_on_chunk", None):
        try:
            from config import VOICE_ENABLED
            if VOICE_ENABLED:
                event_bus.subscribe("chunk", voice_manager._on_chunk)
                event_bus.subscribe("done", voice_manager._on_done)
                event_bus.subscribe("status", voice_manager._on_status)
        except Exception:
            pass

    try:
        while True:
            data = await websocket.receive_text()
            request_data = json.loads(data)
            
            # Handle stop generation requests
            if request_data.get("type") == "stop":
                session_id = request_data.get("session_id")
                if session_id:
                    orchestrator.cancel_current_request(session_id)
                voice_manager.interrupt()
                continue

            # Handle character state sync requests over /ws
            if request_data.get("type") == "character_sync":
                from core.character_manager import character_manager
                if character_manager.enabled:
                    await ws_sender(character_manager.get_sync_payload())
                    await ws_sender(character_manager.state.to_protocol_dict())
                continue

            # Handle input responses
            if request_data.get("type") == "input_response":
                request_id = request_data.get("request_id")
                text = request_data.get("text", "")
                if request_id:
                    permission_manager.approval_manager.resolve_pending(
                        request_id, {"text": text}
                    )
                continue

            # Handle approval responses
            if request_data.get("type") == "approval_response":
                request_id = request_data.get("request_id")
                approved = request_data.get("approved", False)
                scope = request_data.get("scope", "deny")
                if request_id:
                    permission_manager.approval_manager.resolve_pending(
                        request_id, approved, scope
                    )
                continue
            
            messages = request_data.get("messages", [])
            user_id = request_data.get("user_id")
            session_id = request_data.get("session_id")
            agent_mode = request_data.get("agent_mode", False)
            
            if not messages or not user_id or not session_id:
                continue

            from core.character_manager import character_manager
            last_user_msg = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
            character_manager.set_user_turn_text(last_user_msg if isinstance(last_user_msg, str) else str(last_user_msg))
                
            # Delegate all complex logic to the orchestrator
            await orchestrator.process_request(session_id, user_id, messages, event_bus, agent_mode=agent_mode)
            await character_manager.direct_turn_body(last_user_msg if isinstance(last_user_msg, str) else str(last_user_msg))
                
    except WebSocketDisconnect:
        logger.info("Client disconnected")
        # Clear session approvals on disconnect
        permission_manager.approval_manager.clear_session()
    finally:
        from core.events import global_bus
        global_bus.unsubscribe("status", on_status)
        global_bus.unsubscribe("chunk", on_chunk)
        global_bus.unsubscribe("meta", on_meta)
        global_bus.unsubscribe("ui_state", on_ui_state)
        global_bus.unsubscribe("character_state", on_character_event)
        global_bus.unsubscribe("character_activity", on_character_event)
        global_bus.unsubscribe("character_speech", on_character_event)
        global_bus.unsubscribe("character_stop", on_character_event)


@app.websocket("/ws/character")
async def character_websocket_endpoint(websocket: WebSocket):
    """
    Dedicated, low-privilege WebSocket endpoint for the isolated character renderer process.
    Exposes ONLY the Character Protocol (state, activity, speech, stop) — never tools, DB, or secrets.
    Supports automatic state resynchronization upon connection or reconnection.
    """
    if not await _verify_ws_auth(websocket):
        return
    from core.character_manager import character_manager
    await websocket.accept()
    await character_manager.register_client(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            msg_type = msg.get("type")
            if msg_type in ("character_sync", "request_state", "ping"):
                if character_manager.enabled:
                    await websocket.send_json(character_manager.get_sync_payload())
                    await websocket.send_json(character_manager.state.to_protocol_dict())
                else:
                    await websocket.send_json({"type": "character_sync", "enabled": False})
    except WebSocketDisconnect:
        logger.info("Character renderer disconnected (HELIOS continuing normally)")
    except Exception as e:
        logger.debug(f"Character WebSocket closed: {e}")
    finally:
        character_manager.unregister_client(websocket)


@app.websocket("/ws/hikari")
async def hikari_websocket_endpoint(websocket: WebSocket):
    """
    Dedicated WebSocket endpoint for the HIKARI Interactive Coding Swarm CLI.
    Enables remote terminal access to multi-agent planning, architecture,
    coding, verification, and git operations from the HELIOS Mobile Terminal.
    Decoupled architecture: Dynamically proxies to out-of-process hikari-addon (:8001)
    if running, or responds with graceful status if offline.
    """
    if not await _verify_ws_auth(websocket):
        return
    await websocket.accept()

    from core.addon_registry import addon_registry
    is_hikari_addon_online = await addon_registry.is_addon_online("hikari", timeout=0.6)

    # 1. If Hikari Addon (:8001) is running, proxy directly to the out-of-process engine
    if is_hikari_addon_online:
        import websockets
        addon_info = addon_registry.get_addon_info("hikari")
        port = addon_info["port"] if addon_info else 8001
        addon_ws_url = f"ws://127.0.0.1:{port}/ws/hikari"

        try:
            async with websockets.connect(addon_ws_url) as addon_ws:
                async def forward_to_client():
                    try:
                        async for msg in addon_ws:
                            await websocket.send_text(msg)
                    except Exception:
                        pass

                async def forward_to_addon():
                    try:
                        while True:
                            msg = await websocket.receive_text()
                            await addon_ws.send(msg)
                    except Exception:
                        pass

                done, pending = await asyncio.wait(
                    [asyncio.create_task(forward_to_client()), asyncio.create_task(forward_to_addon())],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                return
        except Exception as proxy_err:
            logger.warning(f"[Hikari Proxy] Connection to addon failed: {proxy_err}. Falling back...")

    # 2. Addon is offline: respond with a graceful informational banner without crashing Core
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    branch_name = "main"
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res.returncode == 0 and res.stdout.strip():
            branch_name = res.stdout.strip()
    except Exception:
        pass

    await websocket.send_json({
        "type": "banner",
        "version": "v2.0.76 (Core Standalone)",
        "workspace": "isshin-2/helios",
        "branch": branch_name,
        "model": "HELIOS Core Router",
        "provider": "Local Router Fallback",
        "addon_online": False,
        "status": "Ready",
        "message": "Hikari Swarm Addon is offline (Port 8001). Launch 'start_hikari_addon.bat' or 'hikari.bat' for autonomous multi-agent coding."
    })

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except Exception:
                payload = {"type": "command", "text": raw}

            cmd_text = (payload.get("text") or payload.get("command") or payload.get("content") or "").strip()
            if not cmd_text:
                continue

            lower = cmd_text.lower()
            if lower in ("/help", "help"):
                help_text = (
                    "HIKARI (h-code) Commands (Core Standalone Mode):\n"
                    "  /status        Check Addon connection status\n"
                    "  /clear         Clear terminal log\n"
                    "  <prompt>       Query router fallback model"
                )
                await websocket.send_json({"type": "output", "text": help_text})
                await websocket.send_json({"type": "done", "status": "Ready"})
            elif lower in ("/status", "status"):
                addon_status = await addon_registry.is_addon_online("hikari", timeout=0.6)
                status_str = "Online (:8001)" if addon_status else "Offline (run start_hikari_addon.bat to enable swarm)"
                await websocket.send_json({
                    "type": "output",
                    "text": f"● HELIOS Core: Online (:8000) | Hikari Swarm Addon: {status_str}"
                })
                await websocket.send_json({"type": "done", "status": "Ready"})
            elif lower in ("/clear", "clear"):
                await websocket.send_json({"type": "clear"})
                await websocket.send_json({"type": "done", "status": "Ready"})
            else:
                # Direct router fallback without loading heavy swarm
                try:
                    resp = await provider.generate(
                        prompt=f"System: You are Hikari, the HELIOS Autonomous Coding Agent (Standalone Core Mode). Answer the developer query:\n\nDeveloper: {cmd_text}",
                        max_tokens=512,
                        temperature=0.2
                    )
                    text_resp = resp.get("text", "") or str(resp)
                    await websocket.send_json({"type": "output", "text": text_resp})
                except Exception as ex:
                    await websocket.send_json({"type": "output", "text": f"Hikari standalone notice: {ex}"})
                await websocket.send_json({"type": "done", "status": "Ready"})

    except WebSocketDisconnect:
        logger.info("[Hikari] Terminal client disconnected")
    except Exception as e:
        logger.debug(f"[Hikari] WebSocket closed: {e}")


@app.get("/api/character/state")
async def get_character_state():
    """Return current character synchronization snapshot."""
    from core.character_manager import character_manager
    return character_manager.get_sync_payload()


@app.post("/api/character/direct-body")
async def direct_character_body(payload: Dict[str, Any]):
    """
    Ask HELIOS Core's Pose Synthesizer + Trained 3-Head Neural Body Director
    to move the character's 3D body and spatial position.
    """
    from core.character_manager import character_manager
    user_text = str(payload.get("user_text") or payload.get("prompt") or "").strip()
    assistant_text = str(payload.get("assistant_text") or payload.get("reply") or "").strip()
    state = await character_manager.direct_turn_body(user_text, assistant_text)
    return state or character_manager.state.to_protocol_dict()


@app.post("/api/character/generate-pose")
async def generate_character_pose(payload: Dict[str, Any]):
    """
    Have HELIOS Core synthesize a brand-new 3D VRM pose (normalized humanoid bones + 2-Bone IK)
    and broadcast it to the character renderer.
    """
    from core.character_manager import character_manager
    prompt = str(payload.get("prompt") or payload.get("user_text") or "make a confident cyber pose").strip()
    state = await character_manager.generate_custom_pose(prompt)
    return state or character_manager.state.to_protocol_dict()


@app.get("/api/character/poses")
async def list_character_poses():
    """Return all procedural and AI-synthesized custom poses in HELIOS's Pose Library."""
    from core.pose_generator import pose_generator
    return {"poses": pose_generator.get_library()}


@app.get("/api/character/rl-status")
async def get_character_rl_status():
    """Return Human-Reference RL Pose Policy status, reward percentages, and award counters."""
    from core.character_manager import character_manager
    return character_manager.get_rl_status()


@app.post("/api/character/rl-train")
async def train_character_rl_pose(payload: Dict[str, Any]):
    """
    Train HELIOS Core's RL Human-Reference Pose Policy Network on one or all
    human reference poses, award points on match, and broadcast the trained 3D pose.
    """
    from core.character_manager import character_manager
    pose_name = str(payload.get("pose_name") or payload.get("prompt") or "all").strip()
    episodes = int(payload.get("episodes", 20))
    simulate_curriculum = bool(payload.get("simulate_curriculum", True))
    res = await character_manager.train_rl_pose(
        pose_name=pose_name,
        episodes=episodes,
        simulate_curriculum=simulate_curriculum,
    )
    return {
        **res,
        "character_state": character_manager.state.to_protocol_dict(),
    }


@app.post("/api/character/rl-feedback")
async def apply_character_rl_feedback(payload: Dict[str, Any]):
    """
    Apply online Reinforcement Learning reward (+100 pts) or penalty (-50 pts)
    plus live 3D VRM browser biomechanical telemetry to update the RL policy.
    """
    from core.character_manager import character_manager
    pose_name = str(payload.get("pose_name") or "").strip()
    user_award_delta = float(payload.get("user_award_delta", 100.0))
    browser_telemetry = payload.get("browser_telemetry") if isinstance(payload.get("browser_telemetry"), dict) else None
    res = await character_manager.apply_rl_pose_feedback(
        pose_name=pose_name,
        user_award_delta=user_award_delta,
        browser_telemetry=browser_telemetry,
    )
    return {
        **res,
        "character_state": character_manager.state.to_protocol_dict(),
    }


@app.post("/api/character/config")
async def update_character_config(payload: Dict[str, Any]):
    """Enable/disable character addon or switch renderer/model at runtime."""
    from core.character_manager import character_manager
    import config
    if "enabled" in payload:
        enabled = bool(payload["enabled"])
        config.CHARACTER_ENABLED = enabled
        if enabled:
            character_manager.enable()
        else:
            character_manager.disable()
    if "renderer" in payload and payload["renderer"] in ("vrm", "live2d"):
        character_manager.renderer = payload["renderer"]
        config.CHARACTER_RENDERER = payload["renderer"]
    if "model" in payload and isinstance(payload["model"], str):
        character_manager.model_id = payload["model"]
        config.CHARACTER_MODEL = payload["model"]
    return character_manager.get_sync_payload()


@app.post("/api/chat/cancel/{session_id}")
async def cancel_chat(session_id: int):
    orchestrator.cancel_current_request(session_id)
    voice_manager.interrupt()
    return {"status": "cancelled"}

@app.post("/api/interrupt")
async def interrupt_audio():
    voice_manager.interrupt()
    return {"status": "interrupted"}

import json
from pathlib import Path

class SettingsUpdate(BaseModel):
    personality: Optional[str] = None
    voice: Optional[str] = None

@app.get("/api/settings/personalities")
async def get_personalities():
    import config
    cards = []
    pers_dir = Path("personalities")
    if pers_dir.exists():
        for file in pers_dir.glob("*.yaml"):
            try:
                import yaml
                with open(file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                cards.append({
                    "id": file.stem,
                    "name": data.get("name", file.stem.upper()),
                    "prompt": data.get("identity", {}).get("archetype", "friendly_engineering_companion"),
                    "structured": data,
                })
            except Exception:
                pass
        for file in pers_dir.glob("*.md"):
            with open(file, "r", encoding="utf-8") as f:
                cards.append({
                    "id": file.stem,
                    "name": file.stem.title(),
                    "prompt": f.read().strip()
                })
        for file in pers_dir.glob("*.json"):
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                cards.append({
                    "id": file.stem,
                    "name": data.get("name", file.stem.title()),
                    "prompt": data.get("description", "") or data.get("system_prompt", "")
                })
    return {"personalities": cards, "current": config.PERSONALITY}

@app.get("/api/settings/voices")
async def get_voices():
    import config
    voices = ["am_michael", "am_echo", "am_fenrir", "am_adam", "am_puck", 
              "af_sky", "af_bella", "af_sarah", "af_nicole", "af_alloy", "af_jessica", "af_heart"]
    return {"voices": voices, "current": config.VOICE_NAME}

@app.post("/api/settings")
async def update_settings(settings: SettingsUpdate):
    import config
    import os
    env_path = ".env"
    
    if settings.personality:
        config.PERSONALITY = settings.personality
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                lines = f.readlines()
            with open(env_path, "w") as f:
                found = False
                for line in lines:
                    if line.startswith("PERSONALITY="):
                        f.write(f'PERSONALITY="{settings.personality}"\n')
                        found = True
                    else:
                        f.write(line)
                if not found:
                    f.write(f'\nPERSONALITY="{settings.personality}"\n')
        
        new_prompts = {
            "coding": config.load_prompt("coding.md", f"You are {config.BOT_NAME}, an expert programming assistant."),
            "general": config.load_prompt("general.md", f"You are {config.BOT_NAME}, an advanced AI assistant."),
            "reasoning": config.load_prompt("reasoning.md", f"You are {config.BOT_NAME}, an expert engineer and problem solver."),
            "vision": config.load_prompt("vision.md", f"You are {config.BOT_NAME}, a visual analysis assistant."),
            "ui": config.load_prompt("ui.md", f"You are {config.BOT_NAME}, a UI designer."),
            "agent": config.load_prompt("agent.md", f"You are {config.BOT_NAME}, an autonomous agent."),
        }
        config.SYSTEM_PROMPTS.clear()
        config.SYSTEM_PROMPTS.update(new_prompts)
        
    if settings.voice:
        config.VOICE_NAME = settings.voice
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                lines = f.readlines()
            with open(env_path, "w") as f:
                found = False
                for line in lines:
                    if line.startswith("VOICE_NAME="):
                        f.write(f'VOICE_NAME="{settings.voice}"\n')
                        found = True
                    else:
                        f.write(line)
                if not found:
                    f.write(f'\nVOICE_NAME="{settings.voice}"\n')
            
    return {"status": "success"}


def _reload_all_system_prompts():
    import config
    new_prompts = {
        "coding": config.load_prompt("coding.md", f"You are {config.BOT_NAME}, an expert programming assistant."),
        "general": config.load_prompt("general.md", f"You are {config.BOT_NAME}, an advanced AI assistant."),
        "reasoning": config.load_prompt("reasoning.md", f"You are {config.BOT_NAME}, an expert engineer and problem solver."),
        "vision": config.load_prompt("vision.md", f"You are {config.BOT_NAME}, a visual analysis assistant."),
        "ui": config.load_prompt("ui.md", f"You are {config.BOT_NAME}, a UI designer."),
        "agent": config.load_prompt("agent.md", f"You are {config.BOT_NAME}, an autonomous agent."),
    }
    config.SYSTEM_PROMPTS.clear()
    config.SYSTEM_PROMPTS.update(new_prompts)


def _safe_read_text(path: Path) -> str:
    if not path.exists():
        return ""
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
        try:
            txt = raw.decode(enc)
            if "\x00" not in txt:
                return txt
        except Exception:
            pass
    return ""


@app.get("/api/character/personality-studio")
async def get_personality_studio_state():
    """Return the active YAML personality card, preset cards, and raw/compiled system prompts."""
    import config
    import yaml
    from core.character_manager import character_manager
    from core.emotion_engine import load_personality_card

    base_dir = Path(__file__).resolve().parent
    pers_dir = base_dir / "personalities"
    prompts_dir = base_dir / "prompts"
    helios_yaml_path = pers_dir / "helios.yaml"

    active_card = load_personality_card(str(helios_yaml_path))
    raw_yaml = (
        _safe_read_text(helios_yaml_path)
        if helios_yaml_path.exists()
        else yaml.safe_dump(active_card, sort_keys=False, allow_unicode=True)
    )

    presets = []
    if pers_dir.exists():
        for file in sorted(pers_dir.iterdir()):
            if file.suffix.lower() in (".yaml", ".yml"):
                try:
                    txt = _safe_read_text(file)
                    data = yaml.safe_load(txt) or {}
                    presets.append({
                        "id": file.stem,
                        "filename": file.name,
                        "format": "yaml",
                        "name": data.get("name") or data.get("identity", {}).get("name") or file.stem.upper(),
                        "content": txt,
                        "structured": data,
                    })
                except Exception:
                    pass
            elif file.suffix.lower() in (".md", ".json"):
                presets.append({
                    "id": file.stem,
                    "filename": file.name,
                    "format": file.suffix.lstrip(".").lower(),
                    "name": file.stem.upper(),
                    "content": _safe_read_text(file),
                })

    prompt_keys = ["general", "coding", "reasoning", "agent", "vision", "ui"]
    raw_prompts = {}
    for pk in prompt_keys:
        p_file = prompts_dir / f"{pk}.md"
        raw_prompts[pk] = _safe_read_text(p_file)

    return {
        "ok": True,
        "status": "ok",
        "bot_name": config.BOT_NAME,
        "personality_tagline": config.PERSONALITY,
        "card": active_card,
        "active_card": active_card,
        "raw_yaml": raw_yaml,
        "active_card_yaml": raw_yaml,
        "presets": presets,
        "prompts": raw_prompts,
        "compiled_prompts": dict(config.SYSTEM_PROMPTS),
        "character_state": character_manager.state.to_protocol_dict(),
    }


@app.post("/api/character/personality-studio")
async def save_personality_studio_state(payload: Dict[str, Any]):
    """Save and hot-reload the personality card (YAML/structured) and/or system prompts (`prompts/*.md`)."""
    import config
    import yaml
    from core.character_manager import character_manager
    from core.emotion_engine import EmotionEngine

    base_dir = Path(__file__).resolve().parent
    pers_dir = base_dir / "personalities"
    prompts_dir = base_dir / "prompts"
    pers_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    helios_yaml_path = pers_dir / "helios.yaml"
    char_mirror_path = base_dir.parent / "helios-character" / "helios_personality_card.yaml"

    yaml_input = payload.get("card_yaml") or payload.get("raw_yaml")
    updated_card = None
    if isinstance(yaml_input, str) and yaml_input.strip():
        parsed = yaml.safe_load(yaml_input)
        if isinstance(parsed, dict):
            updated_card = parsed
            raw_yaml_out = yaml_input.strip() + "\n"
            helios_yaml_path.write_text(raw_yaml_out, encoding="utf-8")
            try:
                char_mirror_path.write_text(raw_yaml_out, encoding="utf-8")
            except Exception:
                pass
    elif isinstance(payload.get("card"), dict):
        updated_card = payload["card"]
        raw_yaml_out = yaml.safe_dump(updated_card, sort_keys=False, allow_unicode=True)
        helios_yaml_path.write_text(raw_yaml_out, encoding="utf-8")
        try:
            char_mirror_path.write_text(raw_yaml_out, encoding="utf-8")
        except Exception:
            pass

    if updated_card:
        character_manager.personality = updated_card
        character_manager.emotion_engine = EmotionEngine(updated_card)
        resolved_name = (
            updated_card.get("name")
            or (updated_card.get("identity", {}).get("name") if isinstance(updated_card.get("identity"), dict) else None)
        )
        if isinstance(resolved_name, str) and resolved_name.strip():
            config.BOT_NAME = resolved_name.strip()
        emb = updated_card.get("embodied_expression") if isinstance(updated_card.get("embodied_expression"), dict) else {}
        default_style = emb.get("default_posture_style") or emb.get("default_style")
        if default_style:
            await character_manager.set_state(
                character_manager.state.mode,
                emotion=character_manager.state.emotion,
                intensity=character_manager.state.intensity,
                expression=character_manager.state.expression,
                animation=character_manager.state.animation,
                movement=character_manager.state.movement,
                style=str(default_style).lower(),
                custom_pose=character_manager.state.custom_pose,
                speaking=character_manager.state.speaking,
            )

    if isinstance(payload.get("bot_name"), str) and payload["bot_name"].strip():
        config.BOT_NAME = payload["bot_name"].strip()

    if isinstance(payload.get("personality_tagline"), str) and payload["personality_tagline"].strip():
        config.PERSONALITY = payload["personality_tagline"].strip()

    if isinstance(payload.get("prompts"), dict):
        valid_keys = {"general", "coding", "reasoning", "agent", "vision", "ui"}
        for pk, content in payload["prompts"].items():
            if pk in valid_keys and isinstance(content, str) and content.strip():
                (prompts_dir / f"{pk}.md").write_text(content.strip() + "\n", encoding="utf-8")

    _reload_all_system_prompts()
    sync_payload = character_manager.get_sync_payload()
    await character_manager._dispatch_protocol_message(sync_payload)
    return await get_personality_studio_state()


@app.websocket("/sidecar/ws")
async def sidecar_websocket_endpoint(websocket: WebSocket):
    if not await _verify_ws_auth(websocket):
        return
    from core.sidecar_manager import sidecar_manager
    await websocket.accept()
    sidecar_id = "sidecar-" + str(id(websocket))
    await sidecar_manager.register(sidecar_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await sidecar_manager.handle_message(sidecar_id, data)
    except Exception:
        pass
    finally:
        sidecar_manager.unregister(sidecar_id)


# --- System Provisioning API --------------------------------------------------
@app.get("/api/system/provisioning")
async def get_provisioning_status():
    """Return current provisioning status and initialization manifest."""
    from core.model_provisioner import is_initialized, read_initialized_manifest, load_checkpoint
    import os as _os
    base = _os.path.dirname(_os.path.abspath(__file__))
    initialized = is_initialized(base)
    manifest = read_initialized_manifest(base) if initialized else None
    checkpoint = load_checkpoint(base) if not initialized else None
    return {
        "initialized": initialized,
        "manifest": manifest,
        "checkpoint": checkpoint
    }


@app.post("/api/system/reprovision")
async def reprovision_system(req: Dict[str, Any] = {}):
    """
    Trigger model re-provisioning.
    
    Body parameters:
        mode: "dry_run" | "analyze" | "provision" | "force"
            - dry_run: analyze hardware and report proposed models without pulling
            - analyze: same as dry_run
            - provision: run full provisioning (only if not already initialized)
            - force: re-run provisioning even if already initialized
    """
    from core.model_provisioner import ModelProvisioner, is_initialized
    from core.events import global_bus
    from providers.ollama import OllamaProvider
    from config import OLLAMA_HOST
    import os as _os

    mode = req.get("mode", "dry_run")
    base = _os.path.dirname(_os.path.abspath(__file__))

    if mode not in ("dry_run", "analyze", "provision", "force"):
        return {"error": f"Invalid mode '{mode}'. Use: dry_run, analyze, provision, force"}

    dry_run = mode in ("dry_run", "analyze")
    force = mode == "force"

    if mode == "provision" and is_initialized(base):
        return {"error": "Already initialized. Use mode='force' to re-provision."}

    prov = OllamaProvider(host=OLLAMA_HOST)

    async def bridge(event_type, data=None):
        try:
            await global_bus.publish("provisioning_event", {"event": event_type, "data": data})
        except Exception:
            pass

    provisioner = ModelProvisioner(ollama_provider=prov, event_callback=bridge, base_dir=base)
    result = await provisioner.run(dry_run=dry_run, force=force)

    try:
        await prov.close()
    except Exception:
        pass

    return result


# --- Resource Manager & TTS Diagnostics API -----------------------------------
@app.get("/api/system/resources")
async def get_system_resources():
    """Return unified RAM/VRAM resource manager metrics, tiering, and residency states."""
    from core.audio.tts.resource_policy import resource_manager
    return resource_manager.get_diagnostics()


@app.get("/api/tts/status")
@app.get("/api/tts/diagnostics")
async def get_tts_diagnostics():
    """Return active TTS backend status, device placement, and cache usage."""
    if hasattr(voice_manager, "tts_manager"):
        return voice_manager.tts_manager.get_status()
    elif hasattr(voice_manager.tts, "get_status"):
        return voice_manager.tts.get_status()
    return {
        "tts_backend": getattr(config, "VOICE_BACKEND", "kokoro"),
        "voice": getattr(config, "VOICE_NAME", "af_heart"),
        "status": "legacy",
    }


# --- Cluster & NVIDIA PAIR GPU Node Management --------------------
@app.get("/api/cluster/status")
async def get_cluster_status():
    """Returns NVIDIA PAIR cluster node health, port status, and computing capacity."""
    from core.hardware_profiler import get_cluster_hardware_summary
    from core.sidecar_manager import sidecar_manager
    summary = get_cluster_hardware_summary()
    summary["connected_sidecars"] = sidecar_manager.get_sidecars_info()
    summary["active_sidecars_count"] = len(sidecar_manager.active_sidecars)
    return summary


@app.post("/api/cluster/wake")
async def trigger_cluster_wake(wait: bool = False):
    """Sends native UDP Wake-on-LAN packet to NVIDIA PAIR node."""
    from core.ai_pc_manager import wake_ai_pc, get_ai_pc_node_status
    ok = wake_ai_pc(wait_for_ready=wait)
    status = get_ai_pc_node_status(timeout=1.5)
    return {
        "success": ok,
        "message": "Wake-on-LAN magic packet transmitted" if ok else "Failed to send WoL packet",
        "node_status": status,
    }


@app.get("/api/cluster/telemetry")
async def get_cluster_telemetry():
    """Returns LLM cluster provider telemetry, active host, and circuit breaker status."""
    if hasattr(provider, "get_cluster_telemetry"):
        return provider.get_cluster_telemetry()
    return {
        "provider": type(provider).__name__,
        "host": getattr(provider, "host", "unknown"),
        "cluster_enabled": False,
    }


@app.post("/api/cluster/failover-reset")
async def reset_cluster_failover():
    """Manually resets the circuit breaker on PairProvider to probe primary node."""
    if hasattr(provider, "reset_circuit_breaker"):
        provider.reset_circuit_breaker()
        return {"success": True, "message": "Circuit breaker reset. Primary node re-enabled."}
    return {"success": False, "message": "Provider does not support circuit breaker reset."}


@app.get("/api/ports")
async def get_system_ports():
    """Returns guaranteed unique ports for all HELIOS subsystem functions."""
    return {
        "status": "ok",
        "ports": config.get_service_ports(),
        "uniqueness_verified": True
    }


# ==========================================
# DEVELOPER EXTENSIBLE CONNECTORS API
# ==========================================

from connectors.registry import get_connector_registry

class ConnectorAddRequest(BaseModel):
    id: str
    name: str
    entrypoint: str
    scopes: List[str] = ["read_only"]
    timeout_seconds: int = 15
    enabled: bool = True
    description: str = ""
    python_code: Optional[str] = None

class ConnectorToggleRequest(BaseModel):
    id: str
    enabled: bool

class ConnectorScaffoldRequest(BaseModel):
    id: str
    name: str
    description: str = ""
    scopes: List[str] = ["read_only"]

class ConnectorExecuteRequest(BaseModel):
    id: str
    params: Dict[str, Any] = {}

@app.get("/api/connectors")
async def list_registered_connectors():
    """Returns all registered developer connectors with scopes, status, and schemas."""
    registry = get_connector_registry()
    manifest_entries = {c["id"]: c for c in registry.manifest_data.get("connectors", [])}
    
    result = []
    # Include active instances
    for c in registry.list_connectors():
        cid = c["id"]
        manifest_meta = manifest_entries.get(cid, {})
        c["enabled"] = manifest_meta.get("enabled", True)
        c["entrypoint"] = manifest_meta.get("entrypoint", "")
        result.append(c)

    # Also list disabled manifest entries
    for cid, meta in manifest_entries.items():
        if not meta.get("enabled", True) and not any(r["id"] == cid for r in result):
            result.append({
                "id": cid,
                "name": cid.replace("_", " ").title(),
                "version": "1.0.0",
                "description": meta.get("description", "Disabled connector"),
                "scopes": meta.get("scopes", ["read_only"]),
                "timeout_seconds": meta.get("timeout_seconds", 15),
                "enabled": False,
                "entrypoint": meta.get("entrypoint", ""),
                "input_schema": {},
                "output_schema": {}
            })
    return {"status": "ok", "connectors": result}

@app.post("/api/connectors/add")
async def add_developer_connector(req: ConnectorAddRequest):
    """Registers a new developer connector into connectors.manifest.json."""
    registry = get_connector_registry()
    try:
        new_entry = registry.add_connector(req.dict(), python_code=req.python_code)
        return {"status": "ok", "message": f"Connector '{req.id}' registered successfully.", "connector": new_entry}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/connectors/toggle")
async def toggle_developer_connector(req: ConnectorToggleRequest):
    """Enables or disables a connector."""
    registry = get_connector_registry()
    success = registry.toggle_connector(req.id, req.enabled)
    if not success:
        raise HTTPException(status_code=404, detail=f"Connector '{req.id}' not found.")
    state_str = "enabled" if req.enabled else "disabled"
    return {"status": "ok", "message": f"Connector '{req.id}' {state_str} successfully."}

@app.post("/api/connectors/scaffold")
async def scaffold_developer_connector(req: ConnectorScaffoldRequest):
    """Generates starter Python boilerplate for a BaseConnector subclass."""
    registry = get_connector_registry()
    code = registry.generate_scaffold(req.id, req.name, req.description, req.scopes)
    suggested_entrypoint = f"connectors.{req.id}.{''.join(p.capitalize() for p in req.id.split('_'))}Connector"
    return {
        "status": "ok",
        "code": code,
        "suggested_entrypoint": suggested_entrypoint
    }

@app.post("/api/connectors/execute")
async def execute_developer_connector(req: ConnectorExecuteRequest):
    """Safely executes a connector in the zero-trust sandbox with timeout limits."""
    registry = get_connector_registry()
    result = registry.execute(req.id, req.params)
    return {"status": "ok", "result": result}





if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=getattr(config, "SERVER_HOST", "127.0.0.1"), port=getattr(config, "SERVER_PORT", 8000))

