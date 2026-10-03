# ⚡ Krithik Mahesh (@isshin-2) — Engineering Portfolio

A production-grade, highly interactive cyberpunk-themed portfolio showcasing all engineering projects, firmware architectures, hardware pinouts, and real-time simulators of **Krithik Mahesh (@isshin-2)**.

---

## 🚀 Quick Launch

### Option 1: Double Click `start_portfolio.bat`
Located in the project root:
```cmd
start_portfolio.bat
```
This automatically verifies Node.js, ensures dependencies are present, launches the Vite dev server on `http://localhost:5174`, and opens the browser.

### Option 2: CLI
```bash
npm install
npm run dev
# Or build & preview
npm run build
npm run preview
```

---

## 🛠️ Included Projects & Technical Modules

1. **AgriTech Rover (`Agritech_Rover`)**
   - Agricultural field robotics with dual BTS7960 high-current H-bridges
   - Inviolable real-time control path: ESP32-C (RC joystick) ──ESP-NOW (30Hz)──► ESP32-D (FreeRTOS Core 0) ──UART (115200)──► Arduino Mega 2560
   - 6x HC-SR04 ultrasonic sonar radar array with hard-stop failsafe (<25cm)
   - Edge Impulse AI crop diagnostics via ESP32-CAM MJPEG stream

2. **AquaPulse WLMS (`AquaPulse`)**
   - Commercial wireless liquid level telemetry hub with ST7789 240x320 IPS display
   - Ultra-low-power Seeed Studio XIAO ESP32-C3 remote tank nodes
   - DYP-A02YYTW industrial serial ultrasonic sensor with RS485 transceiver
   - Robust noise rejection: Median-of-5 window + Exponential Moving Average (EMA, α=0.25)
   - ESP-NOW peer-to-peer mesh with NVS persistent pairing

3. **TEMPSENSE Enterprise (`TEMPSENSE`)**
   - Enterprise pharmaceutical & cold chain IoT telemetry platform
   - High-concurrency Node.js net.Server raw TCP daemon ingesting sensor frames on port 1024
   - PostgreSQL 15 time-series schema handling millions of readings
   - React 19 Vite dashboard with Socket.IO live push
   - Automated regulatory compliance reports (PDF & CSV) with SHA-256 audit digest & SMTP alerting

4. **TEMPSENSE-OTA Companion (`TEMPSENSE_Companion`)**
   - Remote firmware delivery toolchain and Express portal on port 3000
   - Canary staged rollout to ESP32 node cohorts
   - Dual-partition (`app0` / `app1`) bootloader with hardware watchdog rollback

5. **VERDEX-Kappa S3 (`VERDEX_KAPPA`)**
   - Custom industrial ESP32-S3 development board with 16MB Flash and 8MB PSRAM
   - Wide-input buck regulator (6.5V - 36V DC) with TVS surge protection
   - Hardware SP3485 RS485 bus with auto-direction transceiver
   - ADS1115 16-bit ADC and Qwiic I2C sensor bus

6. **NodeLink Industrial OTA (`NodeLink_OTA`)**
   - Ultra-compact (<18KB) resilient firmware chunk streaming engine
   - SHA-256 binary validation and RTC watchdog boot confirmation

7. **HELIOS Autonomous AI Ecosystem (`HELIOS`)**
   - Local multi-modal AI router (FastAPI, Ollama, VRAM auto-provisioner)
   - Airi 3D VRM avatar presentation companion with procedural humanization and viseme audio sync
   - Expo React Native mobile client with offline on-device GGUF execution
   - Hikari Autonomous Coding CLI (8-agent swarm with Relativistic Black Hole ASCII HUD)

---

## 🕹️ Interactive Simulators Included
- **AquaPulse Tank Level Digital Twin**: Dynamic water level slider, volume calculator, DYP-A02YYTW 4-byte serial hex frame monitor, and median-of-5 vs EMA filter toggle.
- **TEMPSENSE Cold Chain Monitor**: Temperature & humidity sliders, ambient thermal drift engine, port 1024 TCP raw stream logger, and threshold alert triggers.
- **AgriTech Rover Telemetry Deck**: Virtual joystick (WASD / directional), 6x sonar radar scanner with collision failsafe hard-stop, and ESP-NOW 8-byte frame inspector.
