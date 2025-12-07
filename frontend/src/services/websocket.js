const WS_BASE_URL = import.meta.env.VITE_API_URL?.replace('http', 'ws') || 'ws://localhost:8002';

class WebSocketClient {
    constructor() {
        this.ws = null;
        this.sessionId = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 3000;
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
            return;
        }

        this.sessionId = sessionId;
        const wsUrl = `${WS_BASE_URL}/ws/stream/${sessionId}`;

        console.log(`Connecting to WebSocket: ${wsUrl}`);
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
            this.emit('connected', { sessionId });
        };

        this.ws.onmessage = (event) => {
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
                // Silent heartbeat
                break;

            case 'pong':
                // Response to ping
                break;

            case 'error':
                console.error('WebSocket error message:', data);
                this.emit('error', data);
                break;

            default:
                console.log('Unknown message type:', type, data);
        }
    }

    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnect attempts reached');
            return;
        }

        this.reconnectAttempts++;
        console.log(`Reconnecting... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

        setTimeout(() => {
            if (this.sessionId) {
                this.connect(this.sessionId);
            }
        }, this.reconnectDelay);
    }

    disconnect() {
        if (this.ws) {
            this.sessionId = null;
            this.reconnectAttempts = this.maxReconnectAttempts; // Prevent reconnect
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

    ping() {
        this.send({ type: 'ping' });
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
