"""Hikari Autonomous Coding Swarm Engine (Port 8001).
Strict process and memory isolation with dedicated data/hikari.db SQLite store.
"""

import os
import sys
import sqlite3
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header
import uvicorn

# Path configuration
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
AI_ROUTER_DIR = os.path.join(BASE_DIR, "ai-router")
if AI_ROUTER_DIR not in sys.path:
    sys.path.insert(0, AI_ROUTER_DIR)

from core.hardware_governor import HardwareGovernor
from core.security.bridge_guard import get_bridge_guard, IsolationViolationError
from core.security.zero_leak import ZeroLeakFilter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("helios.hikari")

app = FastAPI(title="Hikari Coding Swarm Engine", version="2.0.0")

# Isolated SQLite Database initialization
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
HIKARI_DB_PATH = os.path.join(DATA_DIR, "hikari.db")

def init_hikari_db():
    conn = sqlite3.connect(HIKARI_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hikari_tasks (
            id TEXT PRIMARY KEY,
            prompt TEXT,
            status TEXT,
            result TEXT,
            created_at REAL
        )
    """)
    conn.commit()
    conn.close()

init_hikari_db()
governor = HardwareGovernor()

@app.on_event("startup")
async def on_startup():
    ZeroLeakFilter.enforce_local_telemetry_block()
    logger.info("[Hikari Swarm] Starting on Port 8001 (Isolated Process)")
    if governor.decision.is_budget:
        logger.warning(f"[Hikari Swarm Governor] Budget hardware detected: Concurrency throttled to {governor.decision.max_concurrent_agents} agents.")

@app.get("/health")
def health():
    return {
        "engine": "hikari",
        "status": "online",
        "port": 8001,
        "database": HIKARI_DB_PATH,
        "hardware_tier": governor.decision.tier,
        "is_budget": governor.decision.is_budget,
        "max_concurrent_agents": governor.decision.max_concurrent_agents
    }

@app.get("/status")
def status(x_helios_bridge_token: Optional[str] = Header(None)):
    # Validate IPC if called from another engine
    bg = get_bridge_guard()
    if bg.is_enabled and x_helios_bridge_token:
        try:
            bg.validate_request("helios", "hikari", "status_query", x_helios_bridge_token)
        except IsolationViolationError as e:
            raise HTTPException(status_code=403, detail=str(e))

    return {
        "engine": "hikari",
        "active_worktrees": 0,
        "active_agents": 8 if not governor.decision.is_budget else governor.decision.max_concurrent_agents,
        "database_size_bytes": os.path.getsize(HIKARI_DB_PATH) if os.path.exists(HIKARI_DB_PATH) else 0
    }

@app.websocket("/ws/hikari")
async def websocket_hikari_terminal(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({
        "type": "terminal_init",
        "engine": "Hikari Swarm v2.0",
        "tier": governor.decision.tier_name,
        "is_budget": governor.decision.is_budget
    })
    try:
        while True:
            data = await websocket.receive_json()
            command = data.get("command", "")
            # Sanitize input
            clean_cmd, _ = ZeroLeakFilter.sanitize_text(command)
            
            # Simulated swarm response acknowledgment
            await websocket.send_json({
                "type": "output",
                "text": f"[Hikari Swarm] Received command: {clean_cmd}",
                "status": "completed"
            })
    except WebSocketDisconnect:
        logger.info("[Hikari] Terminal client disconnected")

def start_hikari_server(port: int = 8001):
    uvicorn.run("engines.hikari.server:app", host="0.0.0.0", port=port, log_level="info")

if __name__ == "__main__":
    start_hikari_server()
