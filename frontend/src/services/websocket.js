const getWebSocketUrl = () => {
    // If explicitly set in env, use it
    if (import.meta.env.VITE_API_URL) {
        const url = import.meta.env.VITE_API_URL;
        return url.replace(/^https:/, 'wss:').replace(/^http:/, 'ws:');
    }

    // Otherwise detect if we are on localhost or production
    const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    return isLocal ? 'ws://localhost:8002' : 'wss://trade-yantra-api.onrender.com';
};

const WS_BASE_URL = getWebSocketUrl();

class WebSocketClient {
    constructor() {
        this.ws = null;
        this.sessionId = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 15; // Increased for mobile resilience
        this.reconnectDelay = 3000;
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

    connect(sessionId) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            console.log('WebSocket already connected');
            // Emit connected event immediately for new listeners (e.g., on React re-mount)
            this.emit('connected', { sessionId: this.sessionId });
            return;
        }

        this.sessionId = sessionId;
        const wsUrl = `${WS_BASE_URL}/ws/stream/${sessionId}`;

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

        // Ping every 20 seconds (increased from 15s for better mobile stability)
        this.pingInterval = setInterval(() => {
            this.ping();
        }, 20000);

        // Dead Man's Switch: Check if we haven't heard from server in 90s (increased from 45s)
        // This prevents false disconnects when browser throttles background tabs
        this.watchdogInterval = setInterval(() => {
            const idleTime = Date.now() - this.lastSeen;
            if (idleTime > 90000) { // 90 seconds instead of 45
                console.warn(`WebSocket dead man's switch triggered (idle: ${Math.round(idleTime / 1000)}s). Forcing reconnect...`);
                if (this.ws) {
                    this.ws.close(); // Triggers onclose -> attemptReconnect
                }
            }
        }, 10000); // Check every 10s instead of 5s
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
                this.connect(this.sessionId);
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
}

// Singleton instance
const wsClient = new WebSocketClient();

export default wsClient;
