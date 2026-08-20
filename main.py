import asyncio
import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os

from config import OLLAMA_HOST, SYSTEM_PROMPTS, CONTEXT_SIZES
from providers.ollama import OllamaProvider
from health.monitor import SystemMonitor
from router.classifier import classify_request
from router.rules import get_routing_decision
from models.manager import ModelManager
from tools.executor import ToolExecutor
from router.memory import MemoryManager
from db import get_db
from security.permissions import PermissionManager, DEFAULT_SYSTEM_ACCESS
from core.events import EventBus
from core.orchestrator import ConversationOrchestrator
from core.tool_router import ToolRouter
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="HELIOS AI Router")

# Initialize core components
provider = OllamaProvider(host=OLLAMA_HOST)
monitor = SystemMonitor(provider=provider)
manager = ModelManager(provider=provider, monitor=monitor)
permission_manager = PermissionManager()
tool_executor = ToolExecutor(provider=provider, monitor=monitor,
                             permission_manager=permission_manager)
new_tool_router = ToolRouter(provider=provider, monitor=monitor,
                             permission_manager=permission_manager)
memory_manager = MemoryManager(provider=provider)
orchestrator = ConversationOrchestrator(
    manager, tool_executor, memory_manager, permission_manager, new_tool_router
)

# Serve static files for the web UI
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")



# ─── API ENDPOINTS ──────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse("static/app.html")

@app.get("/sw.js")
async def service_worker():
    return FileResponse("static/sw.js", media_type="application/javascript")

@app.get("/health")
async def health_check():
    return await monitor.get_full_status()

class UserCreate(BaseModel):
    username: str

@app.post("/api/users")
async def create_or_get_user(user: UserCreate):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username FROM users WHERE username = ?", (user.username,))
    row = cursor.fetchone()
    if row:
        conn.close()
        return dict(row)
    
    # New user — set default system_access
    default_access = json.dumps(DEFAULT_SYSTEM_ACCESS)
    cursor.execute("INSERT INTO users (username, system_access) VALUES (?, ?)",
                   (user.username, default_access))
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

# ─── SYSTEM ACCESS ENDPOINTS ────────────────────────────────────────────────

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

# ─── PRIVACY & DELETION ENDPOINTS (PHASE 8) ─────────────────────────────────

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

# ─── VOICE ENDPOINTS (PHASE 9) ──────────────────────────────────────────────

try:
    from voice.assistant import VoiceAssistant
    voice_assistant = VoiceAssistant()
except ImportError:
    voice_assistant = None
    logger.warning("Voice module could not be loaded. Voice features disabled.")

@app.post("/api/voice/start")
async def start_voice():
    if not voice_assistant:
        raise HTTPException(status_code=501, detail="Voice features are not available.")
    voice_assistant.start()
    return {"status": "success", "message": "Voice assistant started."}

@app.post("/api/voice/stop")
async def stop_voice():
    if not voice_assistant:
        raise HTTPException(status_code=501, detail="Voice features are not available.")
    voice_assistant.stop()
    return {"status": "success", "message": "Voice assistant stopped."}

# ─── SELF-MODIFICATION ENDPOINTS ────────────────────────────────────────────

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
    The LLM cannot call this endpoint — it requires an authenticated user action.
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

# ─── WEBSOCKET ──────────────────────────────────────────────────────────────


async def send_status(websocket: WebSocket, text: str):
    """Send a contextual loading status update to the frontend."""
    await websocket.send_text(json.dumps({"type": "status", "text": text}))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    event_bus = EventBus()
    
    async def ws_sender(data):
        try:
            await websocket.send_text(json.dumps(data))
        except (RuntimeError, WebSocketDisconnect, Exception):
            pass # Socket might be closed
            
    # Subscribe websocket sender to all event types
    event_bus.subscribe("status", lambda d: asyncio.create_task(ws_sender({"type": "status", "text": d})))
    event_bus.subscribe("chunk", lambda d: asyncio.create_task(ws_sender({"type": "chunk", "content": d})))
    event_bus.subscribe("meta", lambda d: asyncio.create_task(ws_sender({"type": "meta", **d})))
    event_bus.subscribe("approval_request", lambda d: asyncio.create_task(ws_sender({"type": "approval_request", **d})))
    event_bus.subscribe("done", lambda d: asyncio.create_task(ws_sender({"type": "done"})))
    
    try:
        while True:
            data = await websocket.receive_text()
            request_data = json.loads(data)
            
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
            
            if not messages or not user_id or not session_id:
                continue
                
            # Delegate all complex logic to the orchestrator
            await orchestrator.process_request(session_id, user_id, messages, event_bus)
                
    except WebSocketDisconnect:
        logger.info("Client disconnected")
        # Clear session approvals on disconnect
        permission_manager.approval_manager.clear_session()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

