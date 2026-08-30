import AsyncStorage from '@react-native-async-storage/async-storage';

export type ChatMessage = {
  id: number;
  role: 'user' | 'assistant' | 'system' | 'model';
  content: string;
};

export class HeliosClient {
  private ws: WebSocket | null = null;
  private serverUrl: string = '';
  private onMessageReceived: ((msg: any) => void) | null = null;

  constructor() {}

  async getServerUrl(): Promise<string> {
    return 'http://192.168.100.150:8000';
  }

  async setServerUrl(url: string) {
    this.serverUrl = url.replace(/\/$/, ''); // remove trailing slash
    await AsyncStorage.setItem('server_url', this.serverUrl);
  }

  setOnMessage(callback: (msg: any) => void) {
    this.onMessageReceived = callback;
  }

  async connectWebSocket(sessionId: number, username: string = 'krithik') {
    const baseUrl = await this.getServerUrl();
    if (!baseUrl) throw new Error("Server URL not configured");

    // Convert http(s) to ws(s)
    const wsUrl = baseUrl.replace(/^http/, 'ws') + `/ws?session_id=${sessionId}&username=${username}`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log("WebSocket Connected");
    };

    this.ws.onmessage = (e) => {
      if (this.onMessageReceived) {
        try {
          const data = JSON.parse(e.data);
          this.onMessageReceived(data);
        } catch (err) {
          console.error("Error parsing WS message:", e.data);
        }
      }
    };

    this.ws.onerror = (e: any) => {
      console.error("WebSocket Error:", e.message);
    };

    this.ws.onclose = (e) => {
      console.log("WebSocket Closed:", e.code, e.reason);
    };
  }

  disconnectWebSocket() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  async sendMessage(sessionId: number, text: string) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'message', content: text, session_id: sessionId }));
    } else {
      throw new Error("WebSocket is not connected");
    }
  }

  async sendInteractiveReply(sessionId: number, text: string) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'interactive_reply', content: text, session_id: sessionId }));
    }
  }
  
  async sendStop(sessionId: number) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'stop', session_id: sessionId }));
    }
  }

  async fetchSessions(username: string = 'krithik') {
    const baseUrl = await this.getServerUrl();
    if (!baseUrl) return [];
    try {
      const res = await fetch(`${baseUrl}/api/sessions?username=${username}`);
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {
      console.error("Failed to fetch sessions", e);
    }
    return [];
  }

  async fetchHistory(sessionId: number) {
    const baseUrl = await this.getServerUrl();
    if (!baseUrl) return [];
    try {
      const res = await fetch(`${baseUrl}/api/history/${sessionId}`);
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {
      console.error("Failed to fetch history", e);
    }
    return [];
  }
}

export const helios = new HeliosClient();
