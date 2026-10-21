# HELIOS Sovereign Mobile Addon (React Native / Expo)

Standalone mobile companion application for HELIOS.
Streams real-time Hikari terminal sessions, displays affective companion states, and provides on-device offline GGUF model execution.

## Addon Architecture
- **Location**: `C:\projects\mobile-addon`
- **Standalone Addon**: Connects over WebSocket and REST to HELIOS Core (`:8000`), Hikari Swarm (`:8001`), and Solstice Avatar (`:8082`).
- **Offline Mode**: Includes local embedded GGUF fallback for air-gapped operations.

## Running the Mobile Addon
```bash
cd C:\projects\mobile-addon
npm install
npm start
# Or for Android emulator / physical device:
npm run android
```

## Environment Configuration
Set `EXPO_PUBLIC_ROUTER_URL` or default to `http://localhost:8000`.
