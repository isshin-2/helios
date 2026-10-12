#!/usr/bin/env bash
# HELIOS Mobile Phone Companion — Expo Go (Port 8081)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/mobile_v2"

echo "============================================================================"
echo "  HELIOS MOBILE PHONE COMPANION -- Expo Go / React Native"
echo "  Bare HELIOS AI Core HUD + Airi 3D Companion + Hikari Terminal"
echo "============================================================================"

# Reverse ADB if device connected
if command -v adb >/dev/null 2>&1; then
    DEVICE=$(adb devices 2>/dev/null | grep -w "device" | head -n 1 | awk '{print $1}')
    if [ -n "$DEVICE" ]; then
        echo "[+] Connected Android device detected via USB: $DEVICE"
        echo "[*] Setting up ADB reverse port forwarding (8081 Metro, 8000 Core, 8080 Airi)..."
        adb reverse tcp:8081 tcp:8081 2>/dev/null || true
        adb reverse tcp:8000 tcp:8000 2>/dev/null || true
        adb reverse tcp:8080 tcp:8080 2>/dev/null || true
        adb reverse tcp:8085 tcp:8085 2>/dev/null || true
    fi
fi

if [ ! -d "node_modules" ]; then
    echo "[!] Installing mobile dependencies..."
    npm install
fi

MODE="${1:-lan}"

case "$MODE" in
    usb|adb|1)
        exec npx expo start --localhost
        ;;
    tunnel|3)
        exec npx expo start --tunnel
        ;;
    web|4)
        exec npx expo start --web
        ;;
    *)
        exec npx expo start
        ;;
esac
