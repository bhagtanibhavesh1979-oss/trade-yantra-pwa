const WS_BASE_URL = import.meta.env.VITE_API_URL?.replace('http', 'ws') || 'ws://localhost:8002';

class WebSocketClient {
    constructor() {
        this.ws = null;
        this.sessionId = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 15; // Increased for mobile resilience
        this.reconnectDelay = 3000;
        this.pingInterval = null;
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
            this.reconnectAttempts = 0; // Reset on successful connection
            this.startHeartbeat();
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
        // Ping every 20 seconds to keep Render/Mobile connection alive
        this.pingInterval = setInterval(() => {
            this.ping();
        }, 20000);
    }

    stopHeartbeat() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
    }

    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnect attempts reached');
            return;
        }

        this.reconnectAttempts++;
        // Implement simple backoff or keep it linear
        const delay = this.reconnectDelay * (1 + (this.reconnectAttempts * 0.2)); // Slight backoff

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
