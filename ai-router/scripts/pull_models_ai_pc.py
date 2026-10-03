"""
HELIOS - Pull High-End Models to AI PC
Pulls large coding and reasoning models directly to the AI PC (192.168.100.254)
leveraging its RTX 5060 Ti (16 GB VRAM) and 64 GB DDR5 RAM.
"""
import sys
import os
import json
import time
import httpx

AI_PC_HOST = os.getenv("OLLAMA_HOST", "http://192.168.100.254:11434")

# Priority models for 16GB VRAM + 64GB RAM workstation
MODELS_TO_PULL = [
    ("qwen2.5-coder:14b", "14B parameter primary coding workhorse (9.0 GB, 100% in 16GB VRAM)"),
    ("qwen2.5-coder:32b", "32B parameter flagship coding titan (19 GB, 16GB VRAM + 64GB RAM offload)"),
]

def pull_model(model_name: str, description: str):
    print("=" * 70)
    print(f"[*] Target Model: {model_name}")
    print(f"[*] Description:  {description}")
    print(f"[*] Target Node:  {AI_PC_HOST}")
    print("=" * 70)

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

def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5-coder:14b"
    for m, desc in MODELS_TO_PULL:
        if m.startswith(target) or target == "all":
            pull_model(m, desc)

if __name__ == "__main__":
    main()
