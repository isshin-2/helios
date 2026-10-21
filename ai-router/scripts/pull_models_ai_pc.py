"""
HELIOS - NVIDIA PAIR Model Lifecycle & Cluster Management Tool
Manages models and hardware lifecycle directly on the dedicated NVIDIA PAIR Node (192.168.100.254)
leveraging its GPU VRAM and host RAM pool.
"""
import sys
import os
import json
import time
import argparse
import httpx
from typing import List, Tuple, Dict, Any

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from config import AI_PC_IP, PAIR_HOST, DEFAULT_AI_PC_MAC
    from core.ai_pc_manager import is_ai_pc_reachable, send_wake_on_lan, get_ai_pc_node_status
except ImportError:
    AI_PC_IP = os.getenv("AI_PC_IP", "192.168.100.254")
    PAIR_HOST = os.getenv("PAIR_HOST", f"http://{AI_PC_IP}:11434")
    DEFAULT_AI_PC_MAC = "30:56:0F:A8:76:05"

AI_PC_HOST = os.getenv("OLLAMA_HOST", PAIR_HOST).rstrip("/")

# Swarm Model Profiles for workstation GPU node
SWARM_MODELS: List[Tuple[str, str, str]] = [
    ("qwen2.5-coder:32b", "Flagship 32B Titan: Coder, Architect, Repair (19 GB, 16GB VRAM + 64GB RAM offload)", "flagship"),
    ("qwen2.5-coder:14b", "14B Workhorse: Planner, Tester, Reviewer, Security (9.0 GB, 100% in 16GB VRAM)", "primary"),
    ("qwen2.5-coder:7b", "7B Fast Local/Remote: Repo Mapper, Fallback (4.7 GB, instant load)", "fast"),
    ("hermes3:8b", "8B Tool Use & System Function Calling Workhorse (4.7 GB)", "tools"),
    ("llama3.2:3b", "3B Ultra-Fast Conversational & Fallback Model (2.0 GB)", "fast"),
    ("moondream:latest", "Lightweight Vision Model for UI & Diagram Inspection (1.7 GB)", "vision"),
    ("nomic-embed-text:latest", "Embedding Engine for Codebase Knowledge RAG (274 MB)", "embeddings"),
]


def check_node_online() -> bool:
    try:
        from core.ai_pc_manager import is_ai_pc_reachable
        return is_ai_pc_reachable(timeout=1.5)
    except Exception:
        try:
            r = httpx.get(f"{AI_PC_HOST}/api/tags", timeout=1.5)
            return r.status_code == 200
        except Exception:
            return False


def show_status():
    print("=" * 75)
    print(f"[*] NVIDIA PAIR Cluster Node: {AI_PC_HOST}")
    print("=" * 75)
    try:
        from core.ai_pc_manager import get_ai_pc_node_status
        status = get_ai_pc_node_status(timeout=2.0)
    except Exception as e:
        print(f"[-] Error retrieving status: {e}")
        return

    reachable = status.get("reachable", False)
    print(f"  Reachability:      {'ONLINE (Active)' if reachable else 'OFFLINE (Unreachable)'}")
    print(f"  IP Address:        {status.get('node_ip')}")
    print(f"  MAC Address:       {status.get('mac_address')}")
    print(f"  Ports:")
    for k, v in status.get("ports", {}).items():
        state = "[OPEN]" if v else "[CLOSED]"
        print(f"    - {k:28s}: {state}")

    hw = status.get("hardware_target", {})
    print(f"\n  Hardware Profile:")
    print(f"    - GPU:            {hw.get('gpu')}")
    print(f"    - System RAM:     {hw.get('ram_gb')} GB DDR5")
    print(f"    - CPU:            {hw.get('cpu')}")

    available = status.get("available_models", [])
    print(f"\n  Installed Models on Node ({len(available)}):")
    for m in sorted(available):
        print(f"    * {m}")

    running = status.get("running_models", [])
    print(f"\n  Currently Resident in VRAM/RAM ({len(running)}):")
    if not running:
        print("    (No models currently loaded in memory)")
    else:
        for rm in running:
            name = rm.get("name", "unknown")
            vram_mb = rm.get("size_vram", 0) / (1024 * 1024)
            size_mb = rm.get("size", 0) / (1024 * 1024)
            ctx = rm.get("context_length", "auto")
            print(f"    * {name:25s} | VRAM: {vram_mb:6.1f} MB / Total: {size_mb:6.1f} MB | Context: {ctx}")
    print("=" * 75)


def pull_model(model_name: str, description: str = "") -> bool:
    print("=" * 75)
    print(f"[*] Target Model: {model_name}")
    if description:
        print(f"[*] Description:  {description}")
    print(f"[*] Target Node:  {AI_PC_HOST}")
    print("=" * 75)

    url = f"{AI_PC_HOST}/api/pull"
    payload = {"name": model_name, "stream": True}

    last_pct = -1
    start_time = time.time()

    try:
        with httpx.Client(timeout=None) as client:
            with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    print(f"[-] Error: HTTP {response.status_code} - {response.text}")
                    return False

                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    status = data.get("status", "")
                    total = data.get("total", 0)
                    completed = data.get("completed", 0)

                    if total > 0:
                        pct = int((completed / total) * 100)
                        if pct != last_pct and pct % 5 == 0:
                            mb_done = completed / (1024 * 1024)
                            mb_total = total / (1024 * 1024)
                            elapsed = time.time() - start_time
                            speed = mb_done / elapsed if elapsed > 0 else 0
                            print(f"  -> [{pct:3d}%] {mb_done:6.1f} MB / {mb_total:6.1f} MB ({speed:.1f} MB/s) | {status}", flush=True)
                            last_pct = pct
                    else:
                        if status:
                            print(f"  -> {status}", flush=True)

                    if status == "success":
                        print(f"[+] Successfully pulled {model_name} in {time.time() - start_time:.1f}s!", flush=True)
                        return True

    except Exception as e:
        print(f"[-] Failed pulling {model_name}: {e}")
        return False
    return True


def unload_model(model_name: str) -> bool:
    print(f"[*] Requesting unload of '{model_name}' from {AI_PC_HOST}...")
    try:
        r = httpx.post(f"{AI_PC_HOST}/api/generate", json={"model": model_name, "keep_alive": 0}, timeout=5.0)
        if r.status_code == 200:
            print(f"[+] Model '{model_name}' successfully evicted from NVIDIA PAIR Node VRAM/RAM.")
            return True
        else:
            print(f"[-] Failed to unload: HTTP {r.status_code} - {r.text}")
            return False
    except Exception as e:
        print(f"[-] Error unloading model: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="HELIOS NVIDIA PAIR Cluster & Model Management")
    parser.add_argument("model", nargs="?", default=None, help="Model name to pull (e.g. qwen2.5-coder:14b)")
    parser.add_argument("--status", "-s", action="store_true", help="Display cluster node status and VRAM residency")
    parser.add_argument("--wake", "-w", action="store_true", help="Send native Wake-on-LAN magic packet to NVIDIA PAIR Node")
    parser.add_argument("--unload", "-u", type=str, default=None, help="Unload a model from NVIDIA PAIR memory")
    parser.add_argument("--all", "-a", action="store_true", help="Pull all recommended swarm models")
    parser.add_argument("--check", "-c", action="store_true", help="Check missing models vs recommended profiles")

    args = parser.parse_args()

    if args.wake:
        print(f"[*] Sending Wake-on-LAN packet to NVIDIA PAIR Node (MAC: {DEFAULT_AI_PC_MAC})...")
        try:
            from core.ai_pc_manager import send_wake_on_lan
            ok = send_wake_on_lan()
            print(f"[+] WoL packet sent: {ok}")
        except Exception as e:
            print(f"[-] WoL failed: {e}")
        return

    if args.status:
        show_status()
        return

    if args.unload:
        unload_model(args.unload)
        return

    # Check node reachability before pulling
    if not check_node_online():
        print(f"[-] NVIDIA PAIR Node at {AI_PC_HOST} is currently offline or unreachable.")
        print("[*] Attempting automatic Wake-on-LAN...")
        try:
            from core.ai_pc_manager import send_wake_on_lan
            send_wake_on_lan()
            print("[+] Magic packet transmitted. Allow 30-45 seconds for system boot.")
        except Exception as e:
            print(f"[-] WoL error: {e}")
        return

    if args.check:
        try:
            r = httpx.get(f"{AI_PC_HOST}/api/tags", timeout=2.0)
            installed = {m.get("name") for m in r.json().get("models", [])}
            print(f"[*] Installed models on {AI_PC_HOST}:")
            for m, desc, role in SWARM_MODELS:
                status = "[INSTALLED]" if any(m == inst or inst.startswith(f"{m}:") for inst in installed) else "[MISSING]"
                print(f"  {status:12s} {m:24s} ({role}): {desc}")
        except Exception as e:
            print(f"[-] Check failed: {e}")
        return

    if args.all:
        for m, desc, _ in SWARM_MODELS:
            pull_model(m, desc)
        return

    if args.model:
        # Match model against catalog or pull directly
        target_desc = ""
        for m, desc, _ in SWARM_MODELS:
            if m.startswith(args.model):
                args.model = m
                target_desc = desc
                break
        pull_model(args.model, target_desc)
    else:
        show_status()


if __name__ == "__main__":
    main()
