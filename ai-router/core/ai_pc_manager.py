import os
import socket
import logging
import subprocess
import time
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_AI_PC_IP = os.environ.get("AI_PC_IP", "192.168.100.254")
DEFAULT_WAKE_SCRIPT = os.environ.get("AI_PC_WAKE_SCRIPT", r"C:\Users\krithik\Desktop\AI-PC.ps1")
AUTO_WAKE_ENABLED = os.environ.get("AUTO_WAKE_AI_PC", "true").lower() == "true"


def is_ai_pc_reachable(ip: str = DEFAULT_AI_PC_IP, ports: list = [3389, 14321, 11434], timeout: float = 1.0) -> bool:
    """
    Checks if the AI PC is online and reachable on any of the designated ports.
    Port 3389: RDP
    Port 14321: NVIDIA PAIR inter-node cluster port
    Port 11434: Ollama / PAIR proxy
    """
    for port in ports:
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                return True
        except (OSError, socket.timeout):
            continue
    return False


def wake_ai_pc(script_path: str = DEFAULT_WAKE_SCRIPT, wait_for_ready: bool = True, max_wait_sec: int = 90) -> bool:
    """
    Triggers the Wake-on-LAN and RDP initialization script for the AI PC.
    """
    if not os.path.isfile(script_path):
        logger.warning(f"[AI-PC] Wake script not found at '{script_path}'. Cannot wake AI PC.")
        return False

    logger.info(f"[AI-PC] Triggering AI PC wake script: '{script_path}'...")
    try:
        # Launch PowerShell script in a visible or background process
        process = subprocess.Popen(
            [
                "powershell.exe",
                "-ExecutionPolicy", "Bypass",
                "-File", script_path
            ],
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
        )

        if not wait_for_ready:
            return True

        logger.info(f"[AI-PC] Waiting for AI PC ({DEFAULT_AI_PC_IP}) to respond...")
        start_time = time.time()
        while time.time() - start_time < max_wait_sec:
            if is_ai_pc_reachable(DEFAULT_AI_PC_IP, timeout=1.0):
                logger.info(f"[AI-PC] AI PC is online and reachable!")
                return True
            time.sleep(3)

        logger.warning(f"[AI-PC] Timed out waiting for AI PC after {max_wait_sec} seconds.")
        return False
    except Exception as e:
        logger.error(f"[AI-PC] Failed to execute wake script: {e}")
        return False


def ensure_ai_pc_ready(force_check: bool = False, wait_for_ready: bool = False) -> bool:
    """
    Ensures the AI PC is reachable. If unreachable, triggers the wake script.
    Defaults to non-blocking (wait_for_ready=False) so background wake can proceed
    without halting local execution.
    """
    if not AUTO_WAKE_ENABLED and not force_check:
        return True

    if is_ai_pc_reachable():
        logger.info(f"[AI-PC] AI PC at {DEFAULT_AI_PC_IP} is verified reachable.")
        return True

    logger.warning(f"[AI-PC] AI PC at {DEFAULT_AI_PC_IP} is NOT reachable. Initiating wake sequence (wait_for_ready={wait_for_ready})...")
    return wake_ai_pc(wait_for_ready=wait_for_ready)
