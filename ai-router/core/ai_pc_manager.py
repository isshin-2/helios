import os
import socket
import logging
import subprocess
import time
import asyncio
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

DEFAULT_AI_PC_IP = os.environ.get("AI_PC_IP", "192.168.100.254")
DEFAULT_AI_PC_MAC = os.environ.get("AI_PC_MAC", "30:56:0F:A8:76:05")
DEFAULT_AI_PC_BROADCAST = os.environ.get("AI_PC_BROADCAST", "192.168.100.255")
DEFAULT_WAKE_SCRIPT = os.environ.get("AI_PC_WAKE_SCRIPT", "")
AUTO_WAKE_ENABLED = os.environ.get("AUTO_WAKE_AI_PC", "true").lower() == "true"


def send_wake_on_lan(
    mac_address: str = DEFAULT_AI_PC_MAC,
    broadcast_ip: str = DEFAULT_AI_PC_BROADCAST,
    port: int = 9,
    repeat: int = 3,
) -> bool:
    """
    Sends UDP Wake-on-LAN magic packet natively via Python socket.
    Standard WoL frame: 6 bytes of 0xFF followed by 16 repetitions of the target MAC address.
    Fast (<2ms), headless, zero desktop popup interference.
    """
    try:
        clean_mac = mac_address.replace(":", "").replace("-", "").replace(".", "").strip()
        if len(clean_mac) != 12:
            logger.error(f"[AI-PC-WOL] Invalid MAC address: '{mac_address}'")
            return False

        mac_bytes = bytes.fromhex(clean_mac)
        magic_packet = b"\xff" * 6 + mac_bytes * 16

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            for _ in range(repeat):
                sock.sendto(magic_packet, (broadcast_ip, port))
                time.sleep(0.01)

        logger.info(f"[AI-PC-WOL] Sent native WoL magic packet to {broadcast_ip}:{port} (MAC: {mac_address})")
        return True
    except Exception as e:
        logger.error(f"[AI-PC-WOL] Error sending native WoL packet: {e}")
        return False


def is_ai_pc_reachable(
    ip: str = DEFAULT_AI_PC_IP,
    ports: Optional[List[int]] = None,
    timeout: float = 1.0,
) -> bool:
    """
    Checks if the NVIDIA PAIR node is online and reachable on any of the designated ports.
    Port 3389: RDP
    Port 14321: NVIDIA PAIR inter-node cluster port
    Port 11434: Ollama / PAIR proxy
    """
    if ports is None:
        ports = [3389, 14321, 11434]

    for port in ports:
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                return True
        except (OSError, socket.timeout):
            continue
    return False


async def is_ai_pc_reachable_async(
    ip: str = DEFAULT_AI_PC_IP,
    ports: Optional[List[int]] = None,
    timeout: float = 1.0,
) -> bool:
    """
    Non-blocking async reachability check for FastAPI / async runtimes.
    """
    if ports is None:
        ports = [3389, 14321, 11434]

    for port in ports:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=timeout,
            )
            writer.close()
            await writer.wait_closed()
            return True
        except (OSError, asyncio.TimeoutError):
            continue
    return False


def wake_ai_pc(
    script_path: str = DEFAULT_WAKE_SCRIPT,
    wait_for_ready: bool = False,
    max_wait_sec: int = 90,
    launch_rdp: bool = False,
    use_native_wol: bool = True,
) -> bool:
    """
    Triggers Wake-on-LAN for the NVIDIA PAIR node.
    By default sends native UDP magic packets silently without opening GUI consoles.
    If launch_rdp is True, runs the desktop PowerShell script that opens Remote Desktop.
    """
    success = False
    if use_native_wol:
        success = send_wake_on_lan()

    # Fallback to or explicitly requested PowerShell script execution
    if (not success or launch_rdp) and os.path.isfile(script_path):
        logger.info(f"[NVIDIA-PAIR] Triggering wake script: '{script_path}' (launch_rdp={launch_rdp})...")
        try:
            creationflags = subprocess.CREATE_NEW_CONSOLE if (os.name == "nt" and launch_rdp) else 0
            subprocess.Popen(
                [
                    "powershell.exe",
                    "-ExecutionPolicy", "Bypass",
                    "-File", script_path,
                ],
                creationflags=creationflags,
            )
            success = True
        except Exception as e:
            logger.error(f"[NVIDIA-PAIR] Failed to execute wake script: {e}")

    if not wait_for_ready or not success:
        return success

    logger.info(f"[NVIDIA-PAIR] Waiting for node ({DEFAULT_AI_PC_IP}) to respond...")
    start_time = time.time()
    while time.time() - start_time < max_wait_sec:
        if is_ai_pc_reachable(DEFAULT_AI_PC_IP, timeout=1.0):
            logger.info("[NVIDIA-PAIR] Node is online and reachable!")
            return True
        time.sleep(3)

    logger.warning(f"[NVIDIA-PAIR] Timed out waiting for node after {max_wait_sec} seconds.")
    return False


def ensure_ai_pc_ready(force_check: bool = False, wait_for_ready: bool = False) -> bool:
    """
    Ensures the NVIDIA PAIR node is reachable. If unreachable, triggers the wake sequence.
    Defaults to non-blocking (wait_for_ready=False) so background wake can proceed
    without halting local execution.
    """
    if not AUTO_WAKE_ENABLED and not force_check:
        return True

    if is_ai_pc_reachable():
        logger.info(f"[NVIDIA-PAIR] Node at {DEFAULT_AI_PC_IP} is verified reachable.")
        return True

    logger.warning(
        f"[NVIDIA-PAIR] Node at {DEFAULT_AI_PC_IP} is NOT reachable. "
        f"Initiating wake sequence (wait_for_ready={wait_for_ready})..."
    )
    return wake_ai_pc(wait_for_ready=wait_for_ready)


def get_ai_pc_node_status(timeout: float = 1.5) -> Dict[str, Any]:
    """
    Probes the NVIDIA PAIR node and queries its live services and model status.
    """
    import httpx

    ports_status = {}
    check_ports = {
        3389: "RDP",
        14321: "PAIR Cluster",
        11434: "Ollama / Inference",
    }
    any_reachable = False
    for port, label in check_ports.items():
        try:
            with socket.create_connection((DEFAULT_AI_PC_IP, port), timeout=timeout):
                ports_status[f"{port}_{label.lower().replace(' ', '_')}"] = True
                any_reachable = True
        except (OSError, socket.timeout):
            ports_status[f"{port}_{label.lower().replace(' ', '_')}"] = False

    models_available = []
    models_running = []
    if ports_status.get("11434_ollama_/_inference", False):
        try:
            res = httpx.get(f"http://{DEFAULT_AI_PC_IP}:11434/api/tags", timeout=timeout)
            if res.status_code == 200:
                models_available = [m.get("name") for m in res.json().get("models", [])]
        except Exception:
            pass

        try:
            res = httpx.get(f"http://{DEFAULT_AI_PC_IP}:11434/api/ps", timeout=timeout)
            if res.status_code == 200:
                models_running = res.json().get("models", [])
        except Exception:
            pass

    return {
        "node_ip": DEFAULT_AI_PC_IP,
        "mac_address": DEFAULT_AI_PC_MAC,
        "reachable": any_reachable,
        "ports": ports_status,
        "hardware_target": {
            "gpu": "Dedicated NVIDIA GPU",
            "ram_gb": 64.0,
            "cpu": "Host CPU",
        },
        "available_models": models_available,
        "running_models": models_running,
    }


def verify_service_http(url: str, timeout: float = 1.5) -> bool:
    """Check if an HTTP service responds to a ping or GET request."""
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HELIOS-Preflight"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 204, 301, 302, 404, 405)
    except urllib.error.HTTPError as e:
        return e.code in (200, 204, 301, 302, 404, 405)
    except Exception:
        return False


def attempt_remote_service_start(ip: str, service: str) -> bool:
    """
    Attempts to trigger remote service startup on the target host.
    Uses SSH if paramiko is installed and credentials exist in environment.
    """
    user = os.environ.get("AI_PC_SSH_USER", os.environ.get("USER_NAME", "krithik"))
    pwd = os.environ.get("AI_PC_SSH_PASS", "Krithik@2026")
    try:
        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=user, password=pwd, timeout=4)
        if service.lower() in ("ollama", "models", "inference"):
            # Launch ollama service in background
            cmd = 'powershell -Command "if (-not (Get-Process ollama -ErrorAction SilentlyContinue)) { Start-Process ollama -ArgumentList serve }"'
            ssh.exec_command(cmd)
            time.sleep(2)
        elif service.lower() in ("gpt_sovits", "voice", "tts"):
            # Attempt to launch GPT-SoVITS server if present
            cmd = 'powershell -Command "if (Test-Path D:\\helios\\ai-router\\venv\\Scripts\\python.exe) { cd D:\\helios; Start-Process -FilePath D:\\helios\\ai-router\\venv\\Scripts\\python.exe -ArgumentList \\"-m uvicorn main:app --host 0.0.0.0 --port 9880\\" -WindowStyle Minimized }"'
            ssh.exec_command(cmd)
            time.sleep(2)
        ssh.close()
        return True
    except Exception as e:
        logger.debug(f"[REMOTE-START] Remote service trigger error: {e}")
        return False


def verify_remote_host_and_services(interactive: bool = True) -> bool:
    """
    Comprehensive boot-time verification for remote model hosts:
    1. Tests network and port reachability of the designated host.
    2. Verifies whether required inference (Ollama) and TTS (GPT-SoVITS) services are running.
    3. If services are down, attempts automated startup via WoL and remote trigger.
    4. If still unavailable, prompts user: switch to lightweight local fallback or reattempt.
    """
    provider = os.environ.get("LLM_PROVIDER", "pair").lower()
    host_ip = os.environ.get("AI_PC_IP", DEFAULT_AI_PC_IP)

    # Only run remote verification if configured for remote host
    if provider != "pair" or host_ip in ("127.0.0.1", "localhost", ""):
        return True

    print("\n" + "=" * 78)
    print("  HELIOS BOOT PREFLIGHT: REMOTE HOST & SERVICE VERIFICATION")
    print(f"  Target Host: {host_ip} (Provider: {provider.upper()})")
    print("=" * 78)

    while True:
        print(f"[*] Checking host network availability at {host_ip}...")
        host_up = is_ai_pc_reachable(host_ip, timeout=1.5)

        if not host_up:
            print(f"[!] Host {host_ip} is currently UNREACHABLE (sleeping or offline).")
            print("    Attempting Wake-on-LAN beacon...")
            send_wake_on_lan(
                mac_address=os.environ.get("AI_PC_MAC", DEFAULT_AI_PC_MAC),
                broadcast_ip=os.environ.get("AI_PC_BROADCAST", DEFAULT_AI_PC_BROADCAST),
            )
            # Give short window for wake
            print("    Waiting 8 seconds for host to respond to wake packet...")
            for _ in range(8):
                time.sleep(1)
                if is_ai_pc_reachable(host_ip, timeout=0.8):
                    host_up = True
                    break

        if host_up:
            print(f"[OK] Host {host_ip} is ONLINE.")
            # Check required services
            ollama_url = f"http://{host_ip}:11434/api/tags"
            gpt_url = os.environ.get("GPT_SOVITS_API_URL", f"http://{host_ip}:9880")

            ollama_running = verify_service_http(ollama_url)
            gpt_running = verify_service_http(f"{gpt_url}/")

            print(f"[*] Inference Service (Ollama :11434) : {'RUNNING' if ollama_running else 'DOWN / STOPPED'}")
            if os.environ.get("GPT_SOVITS_ENABLED", "true").lower() == "true":
                print(f"[*] Voice Cloning  (GPT-SoVITS :9880) : {'RUNNING' if gpt_running else 'STANDBY / DOWN'}")

            # Attempt automatic restart if services down
            if not ollama_running:
                print("    [!] Required LLM inference service is not running. Attempting remote start...")
                attempt_remote_service_start(host_ip, "ollama")
                time.sleep(3)
                ollama_running = verify_service_http(ollama_url)

            if ollama_running:
                print("[OK] Remote inference services verified operational.")
                return True
            else:
                print("[!] Automatic startup could not confirm Ollama is active.")

        # Host or critical services unavailable: Offer user choice
        print("\n" + "-" * 78)
        print("  REMOTE HOST SERVICE WARNING:")
        print(f"  Remote machine ({host_ip}) could not provide required AI inference services.")
        print("-" * 78)
        print("  Options:")
        print("    [1] Use lightweight local fallback (Switches LLM to local Ollama / Cloud fallback)")
        print("    [2] Reattempt connection and service verification")
        print("    [3] Exit startup")
        print("-" * 78)

        if not interactive or not sys.stdin.isatty():
            print("[i] Non-interactive environment detected: automatically engaging lightweight fallback.")
            _engage_lightweight_fallback()
            return True

        try:
            choice = input("Select option [1-3, default=1]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nStartup interrupted.")
            sys.exit(0)

        if choice == "2":
            print("[*] Reattempting remote host verification...")
            continue
        elif choice == "3":
            print("[*] Aborting startup as requested.")
            sys.exit(0)
        else:
            print("[*] Engaging lightweight local fallback...")
            _engage_lightweight_fallback()
            return True


def _engage_lightweight_fallback():
    """Switches active runtime session to local lightweight fallback mode."""
    os.environ["LLM_PROVIDER"] = "ollama"
    os.environ["PAIR_HOST"] = "http://127.0.0.1:11434"
    os.environ["OLLAMA_HOST"] = "http://127.0.0.1:11434"
    os.environ["VOICE_BACKEND"] = "kokoro"
    os.environ["GPT_SOVITS_ENABLED"] = "false"
    print("[OK] Switched session to local lightweight mode (Local Ollama + Kokoro ONNX TTS).")

