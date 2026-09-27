# HELIOS Mobile Companion (`mobile_v2`)

A cross-platform **Expo / React Native** mobile client for the **HELIOS** AI ecosystem. It connects in real time to your desktop HELIOS `ai-router` server over WebSockets and automatically falls back to local on-device LLM inference (`llama.rn` GGUF models) when offline.

---

## ✨ Features

* **Interactive AI Core HUD (`AICoreWebView.tsx`)**: Renders the animated HELIOS AI Core interface directly on mobile with voice/chat state visualization.
* **Real-Time HELIOS Backend Sync (`src/api/client.ts`)**: Streams responses from the desktop `ai-router` server over WebSockets when online.
* **Offline On-Device Inference (`llama.rn`)**: Load any quantized `.gguf` model from device storage via `expo-document-picker` to run conversations completely offline on Android/iOS.

---

## 📁 Directory Structure

```text
mobile_v2/
├── App.tsx                 # Main application entry with AI Core toggle & Classic Chat UI
├── AICoreWebView.tsx       # Embedded AI Core visualizer WebView component
├── src/
│   └── api/
│       └── client.ts       # Hybrid HeliosClient (WebSocket online + llama.rn offline fallback)
├── assets/                 # App icons and splash screens
├── android/                # Native Android project configuration
└── package.json            # Expo 57 / React Native 0.86 dependencies
```

---

## 🚀 Getting Started

### 1. Install Dependencies
```powershell
cd mobile_v2
npm install
```

### 2. Start the Development Server
```powershell
npx expo start
```

### 3. Build & Run Native App (Required for `llama.rn` Offline Mode)
```powershell
npx expo run:android
# or on macOS:
npx expo run:ios
```
