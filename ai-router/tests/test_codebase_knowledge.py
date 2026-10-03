"""
Automated Test Suite for HELIOS Knowledge on Desktop Codebases:
1. Agritech_Rover
2. aquapulse
3. tempsense
4. TEMPSENSE-OTA

Tests all 4 required evaluation criteria:
- Understanding purpose of code
- Identifying platform and hardware pinouts/frameworks
- Guiding user in setup and flashing sequences
- Safe modification constraints (packet structures, failsafes, build flags)
"""

import sys
import os
import asyncio
import json

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Setup import path
router_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if router_dir not in sys.path:
    sys.path.insert(0, router_dir)

from db import get_db, init_db
from config import PAIR_HOST
from providers.pair import PairProvider
from router.memory import MemoryManager
from core.orchestrator import _skills_cache, inject_system_prompt

TEST_CASES = [
    {
        "id": "TC-01",
        "domain": "Agritech_Rover",
        "category": "Purpose & Safety Architecture",
        "query": "What is the purpose of Agritech Rover, and what is the strict inviolable safety rule regarding motor control?",
        "required_keywords": ["agricultural", "rover", "mega", "rc", "raspberry pi", "motor"]
    },
    {
        "id": "TC-02",
        "domain": "Agritech_Rover",
        "category": "Platform & Protocol",
        "query": "What are the hardware platforms for Agritech Rover and what is the structure of the ESP-NOW control packet?",
        "required_keywords": ["esp32-c", "esp32-d", "mega", "crc", "packet", "bytes"]
    },
    {
        "id": "TC-03",
        "domain": "AquaPulse",
        "category": "Platform & Hardware Pinout",
        "query": "What hardware boards and display driver does AquaPulse use, and what are the SPI pins for the Hub TFT?",
        "required_keywords": ["esp32", "xiao", "st7789", "dyp", "23", "18"]
    },
    {
        "id": "TC-04",
        "domain": "AquaPulse",
        "category": "Signal Processing & Filtering",
        "query": "How does AquaPulse filter ultrasonic sensor data to prevent water slosh false alarms?",
        "required_keywords": ["median", "ema", "deadband"]
    },
    {
        "id": "TC-05",
        "domain": "TEMPSENSE",
        "category": "Tech Stack & Ingestion Architecture",
        "query": "What is the backend and database stack for TEMPSENSE, and what special port is used for high-performance sensor ingestion?",
        "required_keywords": ["node", "express", "postgres", "1024"]
    },
    {
        "id": "TC-06",
        "domain": "TEMPSENSE",
        "category": "Setup & Deployment",
        "query": "How do you start TEMPSENSE for local Windows development vs Docker, and what are the default admin credentials?",
        "required_keywords": ["run.bat", "docker", "admin@tempsense.com", "admin123"]
    },
    {
        "id": "TC-07",
        "domain": "TEMPSENSE-OTA",
        "category": "OTA Workflow & Safe Modification",
        "query": "Explain the exact step-by-step procedure to deploy a firmware update using TEMPSENSE-OTA companion app.",
        "required_keywords": ["fw_version", "main.cpp", "companion", "3000", "build", "github"]
    }
]

async def run_knowledge_benchmark():
    print("=" * 80)
    print(" HELIOS AUTONOMOUS CODEBASE KNOWLEDGE VERIFICATION BENCHMARK")
    print("=" * 80)
    print(f"Host: {PAIR_HOST}")
    print(f"Verifying Core Memory, Skills Cache, and RAG Knowledge Retrieval")
    print("-" * 80)

    init_db()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT section, length(content) FROM core_memory WHERE user_id = 1")
    core_rows = cursor.fetchall()
    conn.close()

    print(f"\n[1/3] Core Memory Verification:")
    for row in core_rows:
        print(f"  [OK] Section '{row[0]}': {row[1]} characters loaded into active memory.")

    print(f"\n[2/3] Markdown Skills Cache Verification:")
    skills = ["agritech_rover", "aquapulse", "tempsense", "tempsense_ota"]
    for s in skills:
        if s in _skills_cache:
            print(f"  [OK] Skill '{s}.md' loaded ({len(_skills_cache[s])} bytes).")
        else:
            print(f"  [FAIL] Skill '{s}.md' NOT found in cache!")

    print(f"\n[3/3] Executing Model Knowledge Test Queries:")
    provider = PairProvider(host=PAIR_HOST)
    memory_mgr = MemoryManager(provider)

    passed_count = 0
    total_count = len(TEST_CASES)

    for tc in TEST_CASES:
        print("\n" + "-" * 72)
        print(f"[{tc['id']}] {tc['domain']} -- {tc['category']}")
        print(f"Question: \"{tc['query']}\"")

        # 1. Test vector search
        search_results = await memory_mgr.search_memory(1, tc['query'], threshold=0.35, limit=2)
        
        # 2. Test prompt injection
        test_messages = [{"role": "user", "content": tc['query']}]
        injected = inject_system_prompt(test_messages, category="coding", rag_context=search_results)
        
        # 3. Ask model via provider
        sys_prompt = injected[0]["content"] if injected[0]["role"] == "system" else ""
        full_prompt = f"{sys_prompt}\n\nUser Question: {tc['query']}\n\nPlease answer accurately and concisely based on your system knowledge."
        
        try:
            res = await provider.generate("llama3.2:3b", prompt=full_prompt, stream=False)
            answer = res.get("response", "").strip()
        except Exception as e:
            answer = f"Error during generation: {e}"

        # 4. Check keyword presence
        ans_lower = answer.lower()
        matched = [k for k in tc["required_keywords"] if k.lower() in ans_lower]
        missing = [k for k in tc["required_keywords"] if k.lower() not in ans_lower]

        score = (len(matched) / len(tc["required_keywords"])) * 100
        is_passed = score >= 50

        if is_passed:
            passed_count += 1
            status = "[PASSED]"
        else:
            status = "[FAILED]"

        print(f"\nResult: {status} (Match Score: {score:.1f}%)")
        print(f"Answer Extract:\n{answer[:350]}...\n")
        print(f"Matched Keywords: {matched}")
        if missing:
            print(f"Missing Keywords: {missing}")

    print("\n" + "=" * 80)
    print(f" BENCHMARK SUMMARY: {passed_count}/{total_count} Tests Passed ({passed_count/total_count*100:.1f}%)")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_knowledge_benchmark())
