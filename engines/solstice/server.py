"""Solstice ("Sol") Avatar & Companion Engine (Port 8082).
Dedicated engine for Airi and Ren VRM avatars, 3D WebGL telemetry, emotion sync, and local voice biometrics.
Strict process and memory isolation with dedicated data/solstice.db SQLite store.
"""

import os
import sys
import sqlite3
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header, Depends
from pydantic import BaseModel
import uvicorn

# Path configuration
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
AI_ROUTER_DIR = os.path.join(BASE_DIR, "ai-router")
if AI_ROUTER_DIR not in sys.path:
    sys.path.insert(0, AI_ROUTER_DIR)

from core.hardware_governor import HardwareGovernor
from core.security.bridge_guard import get_bridge_guard, IsolationViolationError
from core.security.zero_leak import ZeroLeakFilter
from core.security.voice_biometrics import get_voice_biometrics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("helios.solstice")

app = FastAPI(title="Solstice (Sol) Avatar & Companion Engine", version="1.0.0")

# Isolated SQLite Database initialization
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
SOLSTICE_DB_PATH = os.path.join(DATA_DIR, "solstice.db")

def init_solstice_db():
    conn = sqlite3.connect(SOLSTICE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sol_telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            avatar_name TEXT,
            emotion TEXT,
            viseme TEXT,
            timestamp REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sol_voice_auth_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            authenticated INTEGER,
            method TEXT,
            score REAL,
            timestamp REAL
        )
    """)
    conn.commit()
    conn.close()

init_solstice_db()
governor = HardwareGovernor()

class VoiceVerifyRequest(BaseModel):
    fallback_pin: Optional[str] = None

@app.on_event("startup")
async def on_startup():
    ZeroLeakFilter.enforce_local_telemetry_block()
    logger.info("[Solstice / Sol] Starting Avatar Companion Engine on Port 8082 (Isolated Process)")
    if governor.decision.is_budget:
        logger.warning("[Solstice 3D Governor] Budget hardware: 3D scene targeted at 30 FPS low-overhead profile.")

@app.get("/health")
def health():
    vb = get_voice_biometrics()
    return {
        "engine": "solstice",
        "alias": "sol",
        "role": "Avatar Presentation & Companion Telemetry (Airi & Ren)",
        "status": "online",
        "port": 8082,
        "database": SOLSTICE_DB_PATH,
        "voice_enrolled": vb.profile.get("enrolled", False),
        "target_fps_3d": governor.decision.target_fps_3d,
        "is_budget": governor.decision.is_budget
    }

@app.get("/api/sol/avatars")
def get_avatars():
    """Returns the dual-twin avatar registry."""
    return {
        "avatars": [
            {
                "id": "airi",
                "name": "Airi",
                "role": "Cybernetic Companion",
                "model_path": "models/Helios_Airi.vrm",
                "signature_color": "#00E5FF",
                "height": 1.68
            },
            {
                "id": "twin",
                "name": "Ren (Helios Twin)",
                "role": "Tactical Operative",
                "model_path": "models/Helios_Twin.vrm",
                "signature_color": "#76FF03",
                "height": 1.82
            }
        ],
        "default_mode": "dual_presence",
        "webgl_viewer_url": "http://localhost:8080"
    }

@app.post("/api/sol/verify-voice")
def verify_voice(req: VoiceVerifyRequest):
    """Voice Biometrics Gate verification endpoint."""
    vb = get_voice_biometrics()
    success, msg = vb.authenticate_access(fallback_pin=req.fallback_pin)
    
    # Log auth attempt in isolated database
    conn = sqlite3.connect(SOLSTICE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sol_voice_auth_logs (authenticated, method, score, timestamp) VALUES (?, ?, ?, strftime('%s', 'now'))",
        (1 if success else 0, "pin" if req.fallback_pin else "voice", 1.0 if success else 0.0)
    )
    conn.commit()
    conn.close()

    if not success:
        raise HTTPException(status_code=401, detail=msg)
    return {"authenticated": True, "message": msg}

@app.websocket("/ws/solstice")
async def websocket_solstice_telemetry(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({
        "type": "sol_init",
        "avatars": ["Airi", "Ren"],
        "target_fps": governor.decision.target_fps_3d,
        "shadows_enabled": not governor.decision.is_budget
    })
    try:
        while True:
            data = await websocket.receive_json()
            # Broadcast or respond with telemetry
            await websocket.send_json({
                "type": "avatar_telemetry",
                "source": "solstice",
                "state": "idle",
                "eye_gaze": [0.0, 0.0],
                "blink": 0.0
            })
    except WebSocketDisconnect:
        logger.info("[Solstice] Telemetry client disconnected")

def start_solstice_server(port: int = 8082):
    uvicorn.run("engines.solstice.server:app", host="0.0.0.0", port=port, log_level="info")

if __name__ == "__main__":
    start_solstice_server()
