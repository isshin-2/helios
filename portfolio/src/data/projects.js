export const PROJECTS = [
  {
    id: "agritech-rover",
    title: "AgriTech Rover",
    tagline: "Autonomous & RC Field Robotics with Real-Time Multi-Sensor Telemetry & Edge AI",
    category: "Robotics & RC",
    status: "Active / Field-Tested",
    version: "v2.4.0",
    stars: 12,
    forks: 3,
    github: "https://github.com/isshin-2/Agritech_Rover",
    heroImage: "https://images.unsplash.com/photo-1581092160607-ee22621dd758?auto=format&fit=crop&w=1000&q=80",
    description: "A distributed agricultural field robotics system featuring dual BTS7960 high-current H-bridges, 6x ultrasonic radar array for fail-safe collision avoidance, in-situ soil telemetry (moisture, air temp, soil temp, rain detection), and MJPEG video streaming coupled to Edge Impulse AI for real-time crop health diagnostics.",
    highlights: [
      "Inviolable real-time control path: RC command strictly isolated from the Raspberry Pi OS",
      "FreeRTOS dual-core task segregation: Core 0 dedicated to ESP-NOW reception & CRC-16 check, Core 1 handles display & telemetry",
      "Hardware fail-safe watchdog timer halts motors within 300ms of packet loss",
      "Full stack telemetry: Arduino Mega 2560 -> USB Serial -> Node.js -> WebSocket -> React frontend"
    ],
    architecture: {
      type: "Distributed Dual-Core Edge Topology",
      nodes: [
        { name: "ESP32-C Controller", role: "RC Transmitter with dual-axis joystick, push buttons, ILI9341 touch TFT display" },
        { name: "ESP32-D Rover Hub", role: "FreeRTOS hub receiving 30Hz ESP-NOW frames, UART bridge, WiFi gateway" },
        { name: "Arduino Mega 2560", role: "Dual BTS7960 motor driver PWM control, 6x HC-SR04 sonar scanning, sensor bus" },
        { name: "ESP32-CAM", role: "MJPEG low-latency streaming server on port 81" },
        { name: "Raspberry Pi 3B", role: "Edge Impulse AI inference, SQLite time-series storage, React web dashboard" }
      ],
      flow: "ESP32-C (ESP-NOW 30Hz) ──► ESP32-D (FreeRTOS Core 0) ──UART (115200)──► Arduino Mega 2560 ──► BTS7960 Motors"
    },
    pinouts: [
      { pin: "Mega D5, D6", func: "BTS7960 Left Motor RPWM / LPWM", note: "10-bit hardware PWM forward/reverse" },
      { pin: "Mega D7, D8", func: "BTS7960 Left Enable R_EN / L_EN", note: "High = motor driver active" },
      { pin: "Mega D9, D10", func: "BTS7960 Right Motor RPWM / LPWM", note: "10-bit hardware PWM forward/reverse" },
      { pin: "Mega D11, D12", func: "BTS7960 Right Enable R_EN / L_EN", note: "High = motor driver active" },
      { pin: "Mega D22-D33", func: "6x HC-SR04 Sonar Array", note: "Trig/Echo pairs for Front-L, C, R, Rear, Left, Right" },
      { pin: "Mega A0, A1", func: "Capacitive Soil & Rain Detectors", note: "Analog in-situ ground condition telemetry" },
      { pin: "Mega D2, D4", func: "DHT22 & DS18B20 1-Wire Probe", note: "Dual ambient air and subterranean soil temp" }
    ],
    protocols: [
      { name: "ESP-NOW Link", spec: "8-byte packed struct: throttle (int16), steering (int16), buttons (uint8), seq (uint8), crc16 (uint16)" },
      { name: "UART Command Bus", spec: "115200 8N1: 'DRIVE L<val> R<val>\\n', 'ESTOP\\n', 'PING\\n', 'PUMP ON\\n'" },
      { name: "USB Telemetry String", spec: "9600 8N1: 'M:<moist>|W:<rain>|AT:<temp>|ST:<soil>|H:<hum>|O:<blocked>'" }
    ],
    tech: ["C++", "FreeRTOS", "Arduino Mega", "ESP32", "ESP-NOW", "Raspberry Pi", "Node.js", "React", "Edge Impulse", "BTS7960", "WebSockets"]
  },
  {
    id: "aquapulse",
    title: "AquaPulse WLMS",
    tagline: "Commercial Dual-Core Wireless Water Tank Telemetry & Ultrasonic Monitoring Hub",
    category: "Industrial IoT & Cold Chain",
    status: "Production / Deployed",
    version: "v3.1.2",
    stars: 19,
    forks: 4,
    github: "https://github.com/isshin-2/AquaPulse",
    heroImage: "https://images.unsplash.com/photo-1541888946425-d0fbb18f15f7?auto=format&fit=crop&w=1000&q=80",
    description: "Commercial wireless liquid level management system (WLMS). Combines an ESP32 ST7789 240x320 IPS display master hub with ultra-low-power Seeed Studio XIAO ESP32-C3 remote tank nodes and DYP-A02YYTW industrial serial ultrasonic sensors. Uses peer-to-peer ESP-NOW mesh networking with NVS persistent pairing and a median-of-5 + Exponential Moving Average (EMA) noise rejection filter.",
    highlights: [
      "Sub-millimeter liquid level resolution with DYP-A02YYTW serial ultrasonic distance sensing",
      "Robust dual-stage filtering: 5-sample median window removes acoustic artifacts + α=0.2 EMA smoother",
      "ESP-NOW peer-to-peer mesh eliminates local WiFi dependency between remote reservoirs and the hub",
      "Persistent NVS flash pairing allows field addition of tank nodes without code recompilation"
    ],
    architecture: {
      type: "Wireless Mesh Remote Node & Display Hub",
      nodes: [
        { name: "XIAO ESP32-C3 Remote Node", role: "Battery/solar powered, wakes from deep sleep, polls DYP-A02YYTW via RS485/UART, broadcasts ESP-NOW" },
        { name: "ESP32 Master Hub", role: "Dual-core processor driving ST7789 240x320 IPS display, embedded setup webserver, audio alarm" },
        { name: "DYP-A02YYTW Sensor", role: "Waterproof ultrasonic transducer with 4-byte serial packet protocol" }
      ],
      flow: "DYP-A02YYTW ──UART(9600)──► XIAO C3 (Median+EMA) ──ESP-NOW──► ESP32 Hub ──SPI──► ST7789 IPS Display"
    },
    pinouts: [
      { pin: "XIAO C3 D1 / D2", func: "RS485 / Sensor UART TX / RX", note: "9600 baud 8N1 serial protocol interface" },
      { pin: "XIAO C3 D3", func: "RS485 Transceiver Direction (DE/RE)", note: "Switches transceiver between transmit & listen" },
      { pin: "ESP32 Hub GPIO 4, 16, 17", func: "ST7789 TFT DC, RST, CS", note: "High-speed hardware SPI display bus" },
      { pin: "ESP32 Hub GPIO 18, 23", func: "ST7789 TFT SCLK, MOSI", note: "40MHz hardware SPI for zero-flicker UI updates" },
      { pin: "ESP32 Hub GPIO 21, 22", func: "I2C SDA / SCL", note: "DS3231 high-precision real-time clock" }
    ],
    protocols: [
      { name: "DYP-A02YYTW Binary Protocol", spec: "4-byte packet: [0xFF, DataHigh, DataLow, Checksum] where Checksum = (0xFF + High + Low) & 0xFF" },
      { name: "ESP-NOW Tank Frame", spec: "12-byte payload: tank_id (uint8), distance_mm (uint16), battery_mv (uint16), rssi (int8), crc (uint16)" },
      { name: "Local Embedded Web API", spec: "ESP32 WebServer: GET /api/telemetry, POST /api/calibrate (height, alert thresholds)" }
    ],
    tech: ["C++", "PlatformIO", "ESP32-C3", "ESP32", "ST7789", "ESP-NOW", "DYP-A02YYTW", "RS485", "FreeRTOS", "NVS", "EMA Filter"]
  },
  {
    id: "tempsense",
    title: "TEMPSENSE Enterprise",
    tagline: "Enterprise Cold Chain IoT Monitoring & Compliance Management Platform",
    category: "Industrial IoT & Cold Chain",
    status: "Production",
    version: "v4.2.1",
    stars: 28,
    forks: 7,
    github: "https://github.com/isshin-2/TEMPSENSE",
    heroImage: "https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?auto=format&fit=crop&w=1000&q=80",
    description: "Mission-critical pharmaceutical and cold storage telemetry platform. Features a custom high-concurrency Node.js raw TCP daemon (port 1024) ingesting high-frequency temperature & humidity bursts from hardware sensor nodes, Socket.IO live dashboard streaming to React 19, PostgreSQL 15 time-series storage, automated PDFKit/csv-stringify compliance audit reports, and multi-site RBAC.",
    highlights: [
      "Custom high-throughput TCP ingestion daemon listening on port 1024 with zero JSON parser overhead",
      "PostgreSQL 15 time-series partition scheme handling millions of sensor readings with sub-50ms analytics queries",
      "Automated pharmaceutical regulatory compliance audit reports (PDF & CSV) with SHA-256 audit digest",
      "Instant multi-channel notifications: SMTP email alerts and Socket.IO broadcast when temperature breaches safety envelope"
    ],
    architecture: {
      type: "High-Throughput Raw TCP & WebSocket Reactive Pipeline",
      nodes: [
        { name: "Hardware Sensor Fleets", role: "ESP32 & industrial gateways transmitting binary TCP frames to port 1024" },
        { name: "Raw TCP Ingestion Service", role: "Dedicated Node.js net.Server decoding binary telemetry and bulk inserting to DB" },
        { name: "PostgreSQL 15 Cluster", role: "Relational multi-tenant schema with time-series partitioned sensor logs" },
        { name: "Express 5 API & Socket.IO", role: "RBAC authentication, alerting cron, and real-time frontend push" },
        { name: "React 19 Vite Dashboard", role: "Recharts real-time graphs, multi-site visual floorplans, and compliance center" }
      ],
      flow: "ESP32 Sensor Nodes ──Raw TCP (Port 1024)──► Node.js Net Daemon ──► PostgreSQL 15 ──Socket.IO──► React 19 UI"
    },
    pinouts: [
      { pin: "TCP Port 1024", func: "Raw Sensor Socket Ingestion", note: "Handles concurrent keep-alive socket connections" },
      { pin: "HTTP Port 3001", func: "Express 5 REST API & WebSocket", note: "Serves authenticated dashboard data & auth tokens" },
      { pin: "Vite Port 5173 / 5174", func: "Frontend Single Page App", note: "Production React 19 application" },
      { pin: "PostgreSQL 5432", func: "Database Cluster", note: "Relational & time-series storage" }
    ],
    protocols: [
      { name: "TCP Sensor Protocol", spec: "Structured payload: 'SITE_01|RM_02|T:-19.4|H:42.5|CRC:0x8A\\n' validated with CCITT CRC16" },
      { name: "WebSocket Stream", spec: "Socket.IO events: 'sensor:reading', 'alert:excursion', 'node:heartbeat'" },
      { name: "Compliance Export API", spec: "GET /api/reports/pdf?startDate=...&siteId=... generates signed PDF audit certs" }
    ],
    tech: ["Node.js", "Express 5", "React 19", "PostgreSQL", "Socket.IO", "TCP Sockets", "Docker Compose", "Recharts", "PDFKit", "nodemailer"]
  },
  {
    id: "tempsense-ota",
    title: "TEMPSENSE-OTA Toolchain",
    tagline: "Resilient Firmware Delivery Companion & Remote ESP32 Fleet Manager",
    category: "Industrial IoT & Cold Chain",
    status: "Production",
    version: "v2.0.0",
    stars: 14,
    forks: 2,
    github: "https://github.com/isshin-2/TEMPSENSE_Companion",
    heroImage: "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&w=1000&q=80",
    description: "Enterprise OTA update delivery engine and desktop companion running on port 3000. Provides automated release branch synchronization, binary checksum verification, staged rolling updates to remote ESP32 nodes, and live node health telemetry.",
    highlights: [
      "Staged canary deployments: rolls firmware to test cohorts before broadcast update",
      "Automatic fallback partition recovery: rolls back to factory partition if new firmware fails watchdog boot check",
      "Express companion web portal on port 3000 with visual node fleet topology and single-click update trigger",
      "Native GitHub release branch polling with automated artifact extraction and SHA-256 verification"
    ],
    architecture: {
      type: "Canary Rollout & Dual-Partition Bootloader Orchestrator",
      nodes: [
        { name: "Companion Server (Port 3000)", role: "Local Express management portal with node telemetry table and binary repository" },
        { name: "GitHub Release Sync", role: "Monitors upstream repo releases and downloads certified firmware .bin files" },
        { name: "ESP32 OTA Client", role: "HTTP update client checking MD5/SHA256 before flashing app0 / app1 partitions" }
      ],
      flow: "GitHub Release ──► Companion Server (Port 3000) ──Staged HTTP Stream──► ESP32 Dual-Partition Flash"
    },
    pinouts: [
      { pin: "Companion Port 3000", func: "OTA Portal & Update Server", note: "Serves firmware binary chunks & fleet status" },
      { pin: "ESP32 Flash Partition", func: "app0 (1.9MB) & app1 (1.9MB)", note: "Dual OTA flash layout with rollback support" }
    ],
    protocols: [
      { name: "HTTP Chunked OTA", spec: "HTTP POST /update with Content-Type: application/octet-stream and x-MD5 header" },
      { name: "Fleet Discovery", spec: "UDP broadcast beacon on port 8266 advertising node MAC, firmware version, and IP" }
    ],
    tech: ["Node.js", "Express", "ESP32 OTA", "GitHub API", "Python", "PowerShell", "Partition Tables", "SHA-256"]
  },
  {
    id: "verdex-kappa",
    title: "VERDEX-Kappa S3",
    tagline: "Custom ESP32-S3 Hardware Development Board for Harsh Edge Telemetry",
    category: "Embedded Hardware",
    status: "Hardware Prototype / V1.2",
    version: "Rev B",
    stars: 16,
    forks: 3,
    github: "https://github.com/isshin-2/VERDEX_KAPPA",
    heroImage: "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1000&q=80",
    description: "Custom embedded IoT hardware platform built around the dual-core Xtensa 32-bit LX7 ESP32-S3. Engineered for outdoor agricultural and industrial installations with wide input voltage toleration (6.5V - 36V DC via buck regulator), ESD-protected RS485 transceiver, isolated analog inputs with 16-bit ADC, and dedicated power management IC.",
    highlights: [
      "Custom 4-layer PCB design optimized for industrial EMC compliance and high noise immunity",
      "Wide input buck converter (6.5V - 36V DC down to 3.3V @ 3A) with TVS surge protection",
      "Integrated SP3485 RS485 differential bus with auto-direction hardware control",
      "Qwiic/STEMMA QT I2C connector and dedicated SPI header for rapid field sensor expansion"
    ],
    architecture: {
      type: "Industrial Microcontroller Motherboard",
      nodes: [
        { name: "Xtensa LX7 ESP32-S3", role: "240MHz dual-core with vector instructions, 16MB Flash, 8MB PSRAM" },
        { name: "MP2315 Buck Regulator", role: "High-efficiency step-down converter accepting 6.5V - 36V DC" },
        { name: "SP3485 RS485 Subsystem", role: "Galvanically isolated differential serial bus for long-distance industrial cables" },
        { name: "ADS1115 16-bit ADC", role: "High-precision analog frontend for strain gauges and pH/EC probes" }
      ],
      flow: "Industrial 24V DC ──TVS Surge──► MP2315 Buck (3.3V) ──► ESP32-S3 ──RS485/WiFi/BLE──► Field Infrastructure"
    },
    pinouts: [
      { pin: "VIN / GND", func: "6.5V - 36V DC Terminal Block", note: "Reverse polarity diode & 40V TVS diode protection" },
      { pin: "GPIO 17, 18", func: "Hardware RS485 TX / RX", note: "Tied to SP3485 transceiver with onboard 120Ω termination" },
      { pin: "GPIO 8, 9", func: "I2C SDA / SCL", note: "Qwiic 4-pin JST connector with 4.7kΩ pull-ups" },
      { pin: "GPIO 11, 12, 13, 10", func: "High-Speed SPI Bus", note: "MOSI, MISO, SCK, CS for display and micro-SD card" },
      { pin: "GPIO 1, 2", func: "ADC Channels with Attenuation", note: "Configurable 0-3.3V or 0-10V industrial analog inputs" }
    ],
    protocols: [
      { name: "Industrial Modbus RTU", spec: "RS485 half-duplex binary packet with CRC-16 Modbus checking" },
      { name: "I2C Fast Mode+", spec: "Up to 1MHz clock speed for multi-sensor daughterboards" }
    ],
    tech: ["ESP32-S3", "KiCad", "Hardware Design", "RS485", "PCB Layout", "Power Electronics", "Embedded C++", "Modbus"]
  },
  {
    id: "nodelink-ota",
    title: "NodeLink Industrial OTA",
    tagline: "Distributed Firmware Infrastructure for Mission-Critical Controllers",
    category: "Embedded Hardware",
    status: "Active / Tested",
    version: "v1.5.0",
    stars: 9,
    forks: 1,
    github: "https://github.com/isshin-2/NodeLink_OTA",
    heroImage: "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=1000&q=80",
    description: "Lightweight, resilient over-the-air firmware update server and bootloader client specifically targeted at low-memory microcontrollers (ESP8266, ESP32, STM32 via ESP serial bridge). Implements chunked binary streaming, SHA-256 integrity verification, and automatic rollback partition recovery.",
    highlights: [
      "Ultra-compact bootloader footprint (<18KB flash overhead)",
      "Zero-downtime dual-slot bank switching with cryptographic firmware verification",
      "Network-resilient chunk retry mechanism capable of resuming flashing after WiFi dropouts",
      "Compatible with ESP32, ESP8266, and UART-bridged Cortex-M controllers"
    ],
    architecture: {
      type: "Partition-Aware Chunked Binary Dispatcher",
      nodes: [
        { name: "NodeLink Dispatcher", role: "Lightweight firmware binary stream manager with HMAC signing" },
        { name: "Client OTA Engine", role: "Bootloader extension validating chunks into alternate partition" }
      ],
      flow: "Firmware Binary ──SHA256 + HMAC──► Chunk Streamer ──► Dual-Slot Bootloader ──Watchdog Boot──► App Switched"
    },
    pinouts: [
      { pin: "Flash Partition OTA_0", func: "Primary Application Bank", note: "Runs active production firmware" },
      { pin: "Flash Partition OTA_1", func: "Secondary Application Bank", note: "Receives new candidate build" }
    ],
    protocols: [
      { name: "Chunked Stream Protocol", spec: "4KB data chunks with per-chunk MD5 verification and handshake acknowledge" },
      { name: "Boot Watchdog", spec: "Hardware RTC timer requires firmware to call `nodelink_confirm_boot()` within 15s" }
    ],
    tech: ["C++", "PlatformIO", "ESP32", "ESP8266", "Bootloader", "SHA-256", "OTA Updates", "Memory Partitions"]
  },
  {
    id: "helios",
    title: "HELIOS Autonomous AI Ecosystem",
    tagline: "Local Multi-Modal AI Router, 3D VRM Avatar Presentation, & Hikari Swarm CLI",
    category: "AI & Tooling",
    status: "Active / Cutting-Edge",
    version: "v3.0.0-PRO",
    stars: 47,
    forks: 9,
    github: "https://github.com/isshin-2/HELIOS",
    heroImage: "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=1000&q=80",
    description: "Advanced locally-hosted AI engineering ecosystem. Features an intelligent task-based LLM router (FastAPI, Ollama, VRAM auto-provisioner), zero-trust execution sandbox with MCP integration, 'Airi' — a real-time 3D VRM techwear avatar companion with procedural humanization and viseme lip-sync, an Expo React Native mobile companion with offline GGUF fallback, and 'Hikari' — an autonomous multi-agent terminal coding swarm with git worktree isolation.",
    highlights: [
      "Task-based LLM classifier intelligently dispatching coding, reasoning, vision, and system commands to local or cloud models",
      "Airi 3D VRM presentation companion: 30fps procedural head tracking, blinking, breathing, and viseme audio sync",
      "Hikari Autonomous Coding CLI: 8-agent swarm with Relativistic Black Hole ASCII HUD, git worktree isolation, and self-repairing tests",
      "Expo 57 / React Native mobile client with live WebSocket HUD and offline on-device llama.rn model execution"
    ],
    architecture: {
      type: "Multi-Agent Cluster & 3D Avatar Companion",
      nodes: [
        { name: "ai-router (Port 8000)", role: "Task classifier, VRAM auto-provisioner, SQLite vector memory RAG, zero-trust sandbox" },
        { name: "helios-character (Port 8080)", role: "Airi 3D VRM / Live2D companion driven by HELIOS EventBus and VoiceManager" },
        { name: "mobile_v2 (Expo)", role: "React Native mobile client with offline GGUF local model execution via llama.rn" },
        { name: "Hikari CLI (hikari.bat)", role: "Autonomous coding swarm with git worktree isolation and test rollback protection" }
      ],
      flow: "User Intent ──► HELIOS Router (Port 8000) ──► Hikari 8-Agent Swarm / Ollama / Airi 3D Avatar (Port 8080)"
    },
    pinouts: [
      { pin: "Router Port 8000", func: "FastAPI Core AI Server", note: "LLM routing, memory, sandbox, MCP integration" },
      { pin: "Avatar Port 8080", func: "Airi 3D VRM Companion", note: "Three.js / VRM renderer with WebSocket EventBus" },
      { pin: "Mobile WebSocket", func: "Expo Mobile Bridge", note: "Real-time bidirectional session stream" }
    ],
    protocols: [
      { name: "HELIOS Character Protocol", spec: "WebSocket /ws/character streaming emotion states, gesture triggers, and viseme timelines" },
      { name: "MCP Protocol", spec: "Model Context Protocol for seamless external tool integration (GitHub, Shell, CAD)" },
      { name: "Hikari Agent Swarm Protocol", spec: "Multi-agent peer messaging with Planner, Architect, Coder, Tester, and Security Reviewer" }
    ],
    tech: ["Python", "FastAPI", "Three.js", "VRM", "React Native", "Expo", "Ollama", "PyQt5", "Git Worktrees", "WebSockets", "MCP", "Docker"]
  }
];

export const CATEGORIES = [
  "All Projects",
  "Robotics & RC",
  "Industrial IoT & Cold Chain",
  "Embedded Hardware",
  "AI & Tooling"
];

export const HARDWARE_SKILLS = [
  {
    category: "Microcontrollers & SoCs",
    items: [
      { name: "ESP32-S3 (Xtensa LX7)", level: "Architect", desc: "Dual-core, vector instructions, PSRAM, USB CDC/JTAG" },
      { name: "ESP32-C3 (RISC-V)", level: "Production", desc: "Ultra-low-power, wireless node design, BLE 5, ESP-NOW" },
      { name: "Arduino Mega 2560 (AVR)", level: "Advanced", desc: "Hardware timers, 4x UARTs, BTS7960 high-current motor control" },
      { name: "Raspberry Pi 3B/4B", level: "Senior", desc: "Linux embedded backend, Edge Impulse AI, video transcoding" },
      { name: "RP2040 (Dual ARM Cortex-M0+)", level: "Proficient", desc: "PIO state machines, dual-core bare-metal firmware" }
    ]
  },
  {
    category: "Protocols & Buses",
    items: [
      { name: "ESP-NOW Mesh", level: "Expert", desc: "Direct 2.4GHz peer-to-peer 30Hz telemetry without WiFi AP dependency" },
      { name: "RS485 / Modbus RTU", level: "Production", desc: "Differential serial bus, industrial noise immunity, DYP-A02YYTW" },
      { name: "Raw TCP / Net Sockets", level: "Senior", desc: "High-throughput telemetry ingestion on port 1024 with binary frames" },
      { name: "WebSockets & Socket.IO", level: "Senior", desc: "Sub-50ms bi-directional full-duplex live streaming" },
      { name: "Hardware SPI & I2C", level: "Architect", desc: "ST7789 IPS 40MHz displays, ADS1115 ADCs, DS3231 RTCs" },
      { name: "UART / Serial Streaming", level: "Master", desc: "Custom packet framing, CCITT CRC16 validation, ring buffers" }
    ]
  },
  {
    category: "Software & Cloud Stack",
    items: [
      { name: "C++ / FreeRTOS / PlatformIO", level: "Core", desc: "Dual-core task orchestration, queue passing, NVS flash storage" },
      { name: "Node.js & Express 5", level: "Senior", desc: "High-concurrency daemons, REST APIs, automated PDF generation" },
      { name: "React 19 & Vite", level: "Senior", desc: "Modern reactive dashboards, Tailwind CSS, live telemetry visualizers" },
      { name: "PostgreSQL 15+", level: "Production", desc: "Time-series partitioned schemas, complex aggregations, RBAC" },
      { name: "Python & FastAPI", level: "Senior", desc: "Local AI routing, Ollama integration, zero-trust sandbox" },
      { name: "Docker & Containerization", level: "Production", desc: "Multi-container compose stacks for instant reproducible deployment" }
    ]
  }
];

export const SYSTEM_METRICS = {
  activeMcuDeployments: "140+",
  packetsIngested: "12.8M+",
  uptimeRate: "99.98%",
  linesOfFirmware: "85,000+",
  githubHandle: "isshin-2",
  fullName: "Krithik Mahesh",
  title: "Embedded Systems Architect, Robotics & Full-Stack IoT Engineer",
  location: "Bangalore, India"
};
