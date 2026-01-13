const getWebSocketUrl = () => {
    // If explicitly set in env, use it
    if (import.meta.env.VITE_API_URL) {
        const url = import.meta.env.VITE_API_URL;
        return url.replace(/^https:/, 'wss:').replace(/^http:/, 'ws:');
    }

    // Otherwise detect if we are on localhost or production
    const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

    // Use matching endpoint: ibynqazflq-uc
    return isLocal ? 'ws://localhost:8002' : 'wss://trade-yantra-api-ibynqazflq-uc.a.run.app';
};

const WS_BASE_URL = getWebSocketUrl();

class WebSocketClient {
    constructor() {
        this.ws = null;
        this.sessionId = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 999999; // Practically infinite
        this.reconnectDelay = 2000;
        this.pingInterval = null;
        this.lastSeen = Date.now();
        this.watchdogInterval = null;
        this.listeners = {
            price_update: [],
            alert_triggered: [],
            connected: [],
            disconnected: [],
            error: [],
        };
    }

    connect(sessionId, clientId = null) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            console.log('WebSocket already connected');
            // Emit connected event immediately for new listeners (e.g., on React re-mount)
            this.emit('connected', { sessionId: this.sessionId });
            return;
        }

        this.sessionId = sessionId;
        this.clientId = clientId;
        const wsUrl = clientId
            ? `${WS_BASE_URL}/ws/stream/${sessionId}?client_id=${clientId}`
            : `${WS_BASE_URL}/ws/stream/${sessionId}`;

        console.log(`Connecting to WebSocket: ${wsUrl}`);
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0; // Reset on successful connection
            this.startHeartbeat();
            this.emit('connected', { sessionId });
        };

        this.ws.onmessage = (event) => {
            this.lastSeen = Date.now(); // Update last seen timestamp
            try {
                const message = JSON.parse(event.data);
                this.handleMessage(message);
            } catch (error) {
                console.error('Failed to parse WebSocket message:', error);
            }
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.emit('error', error);
        };

        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.stopHeartbeat();
            this.emit('disconnected', { sessionId });
            this.attemptReconnect();
        };
    }

    handleMessage(message) {
        const { type, data } = message;

        switch (type) {
            case 'connected':
                console.log('WebSocket session established:', data);
                break;

            case 'price_update':
                this.emit('price_update', data);
                break;

            case 'alert_triggered':
                console.log('Alert triggered:', data);
                this.emit('alert_triggered', data);
                break;

            case 'heartbeat':
                // Server heartbeat received
                break;

            case 'pong':
                // Server responded to our ping
                // console.log('Pong received');
                break;

            case 'status':
                // Status update from server
                console.log('Server status:', data);
                break;

            case 'error':
                console.error('WebSocket error message:', data);
                this.emit('error', data);
                break;

            default:
                console.log('Unknown message type:', type, data);
        }
    }

    startHeartbeat() {
        this.stopHeartbeat();
        this.lastSeen = Date.now();

        // Ping every 5 seconds to match backend
        this.pingInterval = setInterval(() => {
            if (this.isConnected()) {
                this.ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
            }
        }, 5000);

        // Dead Man's Switch: Check if we haven't heard from server in 15s
        // If server is silent for 15s, it's likely dead. Force reconnect.
        this.watchdogInterval = setInterval(() => {
            const idleTime = Date.now() - this.lastSeen;
            if (idleTime > 15000) {
                console.warn(`⚠️ Connection stalled (${Math.round(idleTime / 1000)}s). Forcing reconnect...`);
                if (this.ws) {
                    this.ws.close();
                }
            }
        }, 5000);
    }

    stopHeartbeat() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
        if (this.watchdogInterval) {
            clearInterval(this.watchdogInterval);
            this.watchdogInterval = null;
        }
    }

    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnect attempts reached');
            return;
        }

        this.reconnectAttempts++;
        // Fast reconnect for first 3 attempts (1s), then backoff
        let delay;
        if (this.reconnectAttempts <= 3) {
            delay = 1000;
        } else {
            delay = this.reconnectDelay * (1 + (this.reconnectAttempts * 0.2));
        }

        console.log(`Reconnecting... (${this.reconnectAttempts}/${this.maxReconnectAttempts}) in ${delay}ms`);

        setTimeout(() => {
            if (this.sessionId) {
                this.connect(this.sessionId, this.clientId);
            }
        }, delay);
    }

    disconnect() {
        if (this.ws) {
            this.sessionId = null;
            this.reconnectAttempts = this.maxReconnectAttempts; // Prevent reconnect
            this.stopHeartbeat();
            this.ws.close();
            this.ws = null;
        }
    }

    send(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        } else {
            console.warn('WebSocket not connected');
        }
    }

    isConnected() {
        return this.ws && this.ws.readyState === WebSocket.OPEN;
    }

    isConnecting() {
        return this.ws && this.ws.readyState === WebSocket.CONNECTING;
    }

    on(event, callback) {
        if (this.listeners[event]) {
            this.listeners[event].push(callback);
        }
    }

    off(event, callback) {
        if (this.listeners[event]) {
            this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
        }
    }

    emit(event, data) {
        if (this.listeners[event]) {
            this.listeners[event].forEach(callback => callback(data));
        }
    }

    // --- Self-Healing Logic for Mobile/Background ---
    setupSelfHealing() {
        if (typeof window === 'undefined') return;

        // 1. Reconnect when tab becomes visible again
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible') {
                console.log('👀 App visible. Checking connection...');
                this.checkAndRecover();
            }
        });

        // 2. Reconnect when window gets focus
        window.addEventListener('focus', () => {
            console.log('🎯 App focused. Checking connection...');
            this.checkAndRecover();
        });

        // 3. Reconnect when coming back online
        window.addEventListener('online', () => {
            console.log('🌐 Network online. Reconnecting...');
            this.checkAndRecover();
        });
    }

    checkAndRecover() {
        if (!this.sessionId) return;

        const idleTime = Date.now() - this.lastSeen;

        // If disconnected OR stalled for more than 10s
        if (!this.isConnected() || idleTime > 10000) {
            console.warn(`♻️ Recovering connection... (Status: ${this.isConnected() ? 'Stalled' : 'Disconnected'})`);
            if (this.ws) {
                this.ws.onclose = null; // Prevent double trigger
                this.ws.close();
            }
            this.reconnectAttempts = 0; // Fresh start
            this.connect(this.sessionId, this.clientId);
        }
    }
}

// Singleton instance
const wsClient = new WebSocketClient();
wsClient.setupSelfHealing(); // Activate background recovery

export default wsClient;
