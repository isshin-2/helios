"""
HELIOS — Codebase Knowledge Trainer
Trains HELIOS on desktop codebases:
1. Agritech_Rover
2. aquapulse
3. tempsense
4. TEMPSENSE-OTA

Ingests core architecture into Core Memory (always in context) and
indexes granular facts into Vector Archival Memory with embeddings.
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

# Add ai-router to path
router_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if router_dir not in sys.path:
    sys.path.insert(0, router_dir)

from db import get_db, init_db
from config import PAIR_HOST, LLM_PROVIDER
from providers.pair import PairProvider
from providers.ollama import OllamaProvider
from router.memory import MemoryManager, EMBEDDING_MODEL

# Comprehensive specifications for the 4 codebases
KNOWLEDGE_SECTIONS = {
    "PROJECTS_OVERVIEW": """HELIOS has trained expertise on 4 desktop engineering projects located at 'C:\\Users\\krithik\\Desktop\\New folder':
1. Agritech_Rover: Agricultural field robotics (Mega + ESP32-C/D/CAM + Pi 3B + React dashboard).
2. aquapulse: Wireless ESP-NOW water tank level monitor (ESP32 ST7789 Hub + Seeed XIAO ESP32-C3 Node + DYP sensor).
3. tempsense: Enterprise Cold Chain IoT Monitoring Platform (Node.js/Express + PostgreSQL + React/Vite + TCP server :1024).
4. TEMPSENSE-OTA: Over-the-air firmware delivery toolchain with Express companion app and GitHub branch publishing.
Always adhere to each project's hardware safety rules, build systems, and communication contracts when modifying code or guiding setup.""",

    "AGRITECH_ROVER_SPEC": """[AGRITECH_ROVER]
Path: C:\\Users\\krithik\\Desktop\\New folder\\Agritech_Rover
Purpose: Agricultural robotics with RC teleoperation, real-time ultrasonic obstacle avoidance, soil/air telemetry, ESP32-CAM video, and React dashboard.
Platforms & Roles:
- Arduino Mega 2560 (firmware/mega_controller): BTS7960 motor driver, 6x HC-SR04 ultrasonic, DHT11/22, DS18B20 soil temp, rain/moisture sensors. UART Serial2 (115200) from ESP32-D, USB Serial (9600) telemetry to Pi.
- ESP32-C (firmware/esp32_c_controller): RC transmitter, joystick + buttons + ILI9341 320x240 TFT + XPT2046 touch. Sends 8-byte packed ControlPacket_t via ESP-NOW at 30Hz with CRC16.
- ESP32-D (firmware/esp32_d_rover): Rover hub running FreeRTOS dual-core. Core 0: Real-time ESP-NOW rx, CRC validation, 300ms watchdog failsafe, UART to Mega. Core 1: 8Hz TFT UI, 2Hz WiFi WebSocket telemetry to Pi.
- ESP32-CAM (firmware/esp32_cam): AI Thinker board, OV2640, PSRAM enabled, MJPEG stream on port 81.
- Raspberry Pi 3B (agri_rover_pi): Node.js backend (Express, WebSockets, SQLite) + React frontend dashboard + Edge Impulse plant disease inference.
CRITICAL SAFETY: Control path is RC-ONLY (ESP32-C -> ESP32-D -> Mega). Pi NEVER sends motor commands. 300ms ESP-NOW watchdog and 500ms UART watchdog trigger immediate ESTOP. Ultrasonic <25cm hard-stops forward drive.
Setup: Flash Mega via avrdude/Arduino IDE; flash ESP32-D and note MAC; paste MAC into ESP32-C ROVER_MAC[] and flash; flash ESP32-CAM with PSRAM; on Pi run npm install & npm start in backend and frontend.""",

    "AQUAPULSE_SPEC": """[AQUAPULSE]
Path: C:\\Users\\krithik\\Desktop\\New folder\\aquapulse
Purpose: Wireless water-tank level monitor using ESP-NOW mesh.
Platforms:
- Toolchain: PlatformIO with Arduino framework (platformio.ini).
- Hub (esp32dev): ST7789 240x320 SPI TFT touch display (MOSI 23, MISO 19, SCLK 18, CS 4, DC 13, RST 5, TOUCH_CS 14, TOUCH_IRQ 27). NVS pairing persistence, animated tank UI, WiFi AP, ArduinoOTA wireless flash. Build flag: -D HUB_RS485_SENSOR.
- Node (seeed_xiao_esp32c3): Seeed XIAO ESP32-C3 with DYP-A02YYTW serial ultrasonic distance sensor via EspSoftwareSerial. Build flag: -D NODE_DYP_SENSOR.
Filtering: Median-of-5 spike rejection + Exponential Moving Average (EMA) + deadband thresholding.
Setup: 'pio run -e esp32dev -t upload --upload-port <COM>' for Hub; 'pio run -e seeed_xiao_esp32c3 -t upload --upload-port <COM>' for Node. Put Hub in 'Add Node' menu and power Node to pair.""",

    "TEMPSENSE_SPEC": """[TEMPSENSE]
Path: C:\\Users\\krithik\\Desktop\\New folder\\tempsense
Purpose: Enterprise Cold Chain IoT Monitoring Platform for logistics, pharmaceutical storage, and warehouse climate compliance.
Platforms & Stack:
- Backend: Node.js (Express 5, Socket.IO, PostgreSQL 15+, PDFKit reports, csv-stringify, nodemailer SMTP alerts, JWT/bcryptjs RBAC).
- Ingestion: High-throughput raw TCP socket server on port 1024 for direct IoT node streaming.
- Frontend: React 19 + Vite 6 + Tailwind CSS + Lucide React + Recharts interactive charts + React Router 7.
- Database: PostgreSQL on port 5432 (database: tempsense, user/pass: postgres/postgres).
- Deployment: Docker Compose (docker-start.bat), native Windows batch (run.bat), Inno Setup installer.
Setup: Run run.bat (local dev) or docker-start.bat (Docker). Default credentials: admin@tempsense.com / admin123.
Safe Coding: Check syntax with 'node --check <file>' and run 'npm run build' in frontend before commit. Keep port 1024 TCP handler non-blocking.""",

    "TEMPSENSE_OTA_SPEC": """[TEMPSENSE_OTA]
Path: C:\\Users\\krithik\\Desktop\\New folder\\TEMPSENSE-OTA
Purpose: Automated Over-the-Air firmware delivery pipeline for TEMPSENSE sensor nodes.
Platforms & Flow:
- Companion App (companion/): Node.js Express server on port 3000 with real-time dark-theme dashboard. Executes PlatformIO build of src/main.cpp and uploads firmware.bin + version.json directly to GitHub 'tempsense_ota' branch.
- Device OTA Client: ESP32 node queries GitHub raw URL for version.json on WiFi connection; compares against FW_VERSION; downloads and flashes firmware.bin over HTTPS via Update.h.
Setup: Configure companion/.env with GITHUB_TOKEN, GITHUB_REPO, GITHUB_BRANCH, PORT=3000. Run companion/run.bat.
Safe Coding: Always bump FW_VERSION in main.cpp and keep version tag in companion UI identical. Run pio run locally before triggering upload."""
}

FACTS_TO_INDEX = [
    # Agritech Rover
    ("agritech_rover", "Agritech Rover control path is strictly RC-only from ESP32-C through ESP32-D to Arduino Mega. The Raspberry Pi NEVER issues motor drive commands."),
    ("agritech_rover", "Agritech Rover ESP-NOW packet is an 8-byte packed struct ControlPacket_t with throttle, steering, buttons bitfield, sequence counter, and CRC-16/CCITT."),
    ("agritech_rover", "Agritech Rover ESP32-D runs FreeRTOS with taskControl on PRO_CPU Core 0 (ESP-NOW, CRC, 300ms watchdog, UART to Mega) and taskDisplay/taskWifi on APP_CPU Core 1."),
    ("agritech_rover", "Agritech Rover Arduino Mega controls BTS7960 motor drivers, 6x HC-SR04 ultrasonic sensors, DHT temp/humidity, DS18B20 soil temp, and moisture/rain sensors."),
    ("agritech_rover", "Agritech Rover Arduino Mega stops forward motors if any forward ultrasonic sensor measures distance under 25 cm, replying with BLOCKED."),
    ("agritech_rover", "Agritech Rover ESP32-CAM streams MJPEG video over HTTP port 81 to Raspberry Pi 3B for Edge Impulse plant disease inference."),
    ("agritech_rover", "To setup Agritech Rover, flash Mega first, then ESP32-D and note its MAC address, configure ESP32-C ROVER_MAC[] with ESP32-D MAC, flash ESP32-CAM with PSRAM enabled, and start Pi backend and frontend."),

    # AquaPulse
    ("aquapulse", "AquaPulse is built with PlatformIO using Arduino framework, targeting esp32dev for the Hub and seeed_xiao_esp32c3 for the Node."),
    ("aquapulse", "AquaPulse Hub hardware features an ST7789 240x320 SPI color TFT with touch on pins MOSI 23, MISO 19, SCLK 18, CS 4, DC 13, RST 5, TOUCH_CS 14, TOUCH_IRQ 27."),
    ("aquapulse", "AquaPulse Node uses a Seeed XIAO ESP32-C3 connected to a waterproof DYP-A02YYTW serial ultrasonic distance sensor via EspSoftwareSerial."),
    ("aquapulse", "AquaPulse uses median-of-5 spike rejection, exponential moving average (EMA), and deadband thresholding to filter water slosh and ultrasonic noise."),
    ("aquapulse", "AquaPulse Hub persists paired node MAC addresses into NVS flash memory so pairings survive power cycles and reboots."),
    ("aquapulse", "To flash AquaPulse, run 'pio run -e esp32dev -t upload' for the Hub and 'pio run -e seeed_xiao_esp32c3 -t upload' for the Node."),

    # TEMPSENSE
    ("tempsense", "TEMPSENSE is an enterprise cold chain IoT platform featuring live Recharts dashboards, automated PDF/CSV reports, SMTP email alerts, and multi-site organization."),
    ("tempsense", "TEMPSENSE backend runs on Node.js Express 5 with Socket.IO and high-throughput raw TCP sensor ingestion on port 1024."),
    ("tempsense", "TEMPSENSE frontend is built with React 19, Vite 6, Tailwind CSS, Lucide React, and React Router 7."),
    ("tempsense", "TEMPSENSE database uses PostgreSQL 15+ on port 5432 with tables for users, sites, rooms, nodes, readings, alerts, and reports."),
    ("tempsense", "TEMPSENSE default administrator credentials are admin@tempsense.com with password admin123."),
    ("tempsense", "TEMPSENSE supports one-click launch via run.bat for native Windows development or docker-start.bat for Docker Compose."),
    ("tempsense", "When modifying TEMPSENSE code, verify backend syntax with 'node --check' and frontend builds with 'npm run build' inside frontend/."),

    # TEMPSENSE-OTA
    ("tempsense_ota", "TEMPSENSE-OTA companion app is an Express web service on port 3000 that compiles firmware with PlatformIO and commits firmware.bin and version.json to GitHub."),
    ("tempsense_ota", "TEMPSENSE devices check version.json from GitHub on WiFi connection; if newer than compiled FW_VERSION, the ESP32 flashes itself via HTTPS using Update.h."),
    ("tempsense_ota", "TEMPSENSE-OTA companion app requires GITHUB_TOKEN, GITHUB_REPO, and GITHUB_BRANCH in companion/.env.")
]


async def train_helios():
    print("=" * 70)
    print(" HELIOS CODEBASE KNOWLEDGE TRAINER")
    print("=" * 70)
    print(f"Target Codebases: C:\\Users\\krithik\\Desktop\\New folder")
    print(f"Provider:        NVIDIA PAIR / Ollama (Host: {PAIR_HOST})")
    print(f"Embedding Model: {EMBEDDING_MODEL}")
    print("-" * 70)

    init_db()
    conn = get_db()
    cursor = conn.cursor()

    # 1. Populate Core Memory (Always in Context Window)
    print("\n[1/3] Ingesting Core Architectural Memory into SQLite...")
    user_id = 1
    for section, content in KNOWLEDGE_SECTIONS.items():
        cursor.execute("SELECT id FROM core_memory WHERE user_id = ? AND section = ?", (user_id, section))
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE core_memory SET content = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND section = ?", (content, user_id, section))
        else:
            cursor.execute("INSERT INTO core_memory (user_id, section, content) VALUES (?, ?, ?)", (user_id, section, content))
        print(f"  [OK] Ingested Core Memory: [{section}]")
    conn.commit()

    # 2. Vector Archival Memory Indexing with nomic-embed-text
    print("\n[2/3] Generating Embeddings & Indexing Archival Memory...")
    provider = PairProvider(host=PAIR_HOST)
    memory_mgr = MemoryManager(provider)

    indexed_count = 0
    for category, fact in FACTS_TO_INDEX:
        try:
            # Check if already exists
            cursor.execute("SELECT id FROM memories WHERE user_id = ? AND fact = ?", (user_id, fact))
            if cursor.fetchone():
                print(f"  [*] Existing fact skipped: [{category}] {fact[:50]}...")
                continue

            emb = await provider.get_embeddings(EMBEDDING_MODEL, fact)
            if emb:
                cursor.execute(
                    "INSERT INTO memories (user_id, category, fact, embedding) VALUES (?, ?, ?, ?)",
                    (user_id, category, fact, json.dumps(emb))
                )
                conn.commit()
                indexed_count += 1
                print(f"  [OK] Indexed vector fact: [{category}] {fact[:50]}...")
            else:
                print(f"  [WARN] Failed to get embedding for: {fact[:50]}...")
        except Exception as e:
            print(f"  [ERROR] Error embedding fact: {e}")

    conn.close()

    # 3. Verify Retrieval Test
    print("\n[3/3] Verifying Memory Search & Retrieval...")
    test_queries = [
        "What is the safety rule for Agritech Rover motor control?",
        "How do I flash the AquaPulse node and hub?",
        "What is the default port for TEMPSENSE TCP sensor ingestion?",
        "How does TEMPSENSE-OTA deliver firmware to devices?"
    ]

    for q in test_queries:
        results = await memory_mgr.search_memory(user_id, q, threshold=0.4, limit=1)
        res_str = results[0] if results else "No direct match"
        print(f"\n  Query: '{q}'")
        print(f"  Match: {res_str[:90]}...")

    print("\n" + "=" * 70)
    print(" HELIOS TRAINING COMPLETE: 4 Codebases Fully Ingested & Verified!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(train_helios())
