import AsyncStorage from '@react-native-async-storage/async-storage';
import NetInfo from '@react-native-community/netinfo';
// @ts-ignore
import { initLlama, LlamaContext } from 'llama.rn';

export class HeliosClient {
    private userId: string | null = null;
    private ws: WebSocket | null = null;
    private llamaContext: any = null;
    public isOffline: boolean = false;
    private localModelPath: string | null = null;

    constructor(private onMessage: (msg: any) => void) {
        this.initialize();
    }

    private async initialize() {
        // 1. Setup Persistent User ID for cross-device Memory Sync
        let storedId = await AsyncStorage.getItem('HELIOS_USER_ID');
        if (!storedId) {
            // Generate a random ID if first time
            storedId = Math.random().toString(36).substring(2, 15);
            await AsyncStorage.setItem('HELIOS_USER_ID', storedId);
        }
        this.userId = storedId;

        // 2. Setup Network Monitoring
        NetInfo.addEventListener(state => {
            this.isOffline = !(state.isConnected && state.isInternetReachable);
            if (!this.isOffline) {
                this.connectWebSocket();
            }
        });

        // Initial check
        const state = await NetInfo.fetch();
        this.isOffline = !(state.isConnected && state.isInternetReachable);
        
        if (!this.isOffline) {
            this.connectWebSocket();
        }
    }

    public async setupOfflineModel(modelPath: string) {
        this.localModelPath = modelPath;
        try {
            this.llamaContext = await initLlama({
                model: modelPath,
                use_mlock: true,
                n_ctx: 2048,
                n_gpu_layers: 50, // Use metal/vulkan if available
            });
            console.log("Local model initialized successfully!");
        } catch (e) {
            console.error("Failed to init local model:", e);
        }
    }

    private connectWebSocket(isRetry = false) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) return;

        // Try Wi-Fi first, fallback to ADB USB tunnel on retry
        const wsUrl = isRetry ? `ws://127.0.0.1:8000/ws` : `ws://192.168.100.150:8000/ws`;
        
        console.log("Connecting to:", wsUrl);
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.onMessage(data);
            } catch (e) {
                console.error("Error parsing WS message:", e);
            }
        };

        this.ws.onerror = (e) => {
            console.error("WebSocket error:", e);
        };

        this.ws.onclose = () => {
            console.log("WebSocket closed");
            if (!isRetry && !this.isOffline) {
                // If Wi-Fi failed, try USB tunnel immediately
                console.log("Wi-Fi failed, falling back to USB ADB tunnel...");
                this.connectWebSocket(true);
            } else {
                this.isOffline = true;
            }
        };
    }

    public async sendMessage(text: string) {
        if (this.isOffline && this.llamaContext) {
            // OFFLINE: Use On-Device Model
            this.onMessage({ type: 'status', text: 'Generating locally (Offline)...' });
            
            try {
                const response = await this.llamaContext.completion({
                    prompt: `[INST] ${text} [/INST]`,
                    n_predict: 200,
                    temperature: 0.7,
                });
                
                this.onMessage({ type: 'chunk', content: response.text });
                this.onMessage({ type: 'done' });
            } catch (e) {
                console.error("Local generation failed:", e);
                this.onMessage({ type: 'status', text: 'Local generation failed.' });
            }
        } else if (!this.isOffline && this.ws && this.ws.readyState === WebSocket.OPEN) {
            // ONLINE: Route to AI-Router (OpenRouter + Memory)
            const request = {
                type: 'chat',
                user_id: this.userId,
                session_id: Date.now(), // Create a new session or pass existing
                messages: [{ role: 'user', content: text }],
                agent_mode: true // Use the powerful models configured in the backend
            };
            this.ws.send(JSON.stringify(request));
        } else {
            this.onMessage({ type: 'status', text: 'Error: Cannot send message. Network offline and no local model loaded.' });
        }
    }
}
