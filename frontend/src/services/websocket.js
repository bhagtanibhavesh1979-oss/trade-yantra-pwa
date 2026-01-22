const getWebSocketUrl = () => {
    // If explicitly set in env, use it
    if (import.meta.env.VITE_API_URL) {
        const url = import.meta.env.VITE_API_URL;
        return url.replace(/^https:/, 'wss:').replace(/^http:/, 'ws:');
    }

    // Otherwise detect if we are on localhost or production
    const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

    // Use matching endpoint: ibynqazflq-as (Asia-South1)
    return isLocal ? 'ws://localhost:8002' : 'wss://trade-yantra-api-ibynqazflq-as.a.run.app';
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

        this.ws.onclose = (event) => {
            console.log('WebSocket disconnected, code:', event.code, 'reason:', event.reason);
            this.stopHeartbeat();
            this.emit('disconnected', { sessionId });

            // Only auto-reconnect if it wasn't a clean close
            // Code 1000 = normal closure, don't reconnect  
            // Code 1001 = going away (page refresh), don't reconnect
            if (event.code !== 1000 && event.code !== 1001) {
                this.attemptReconnect();
            } else {
                console.log('Clean disconnect, not reconnecting automatically');
            }
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

        // Ping every 10 seconds to match backend heartbeat  
        this.pingInterval = setInterval(() => {
            if (this.isConnected()) {
                try {
                    this.ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
                } catch (err) {
                    console.error('Failed to send ping:', err);
                }
            }
        }, 10000);

        // Watchdog: Only check if truly stale (no data for 90 seconds)
        // Don't be too aggressive - Angel One might have quiet periods
        this.watchdogInterval = setInterval(() => {
            const idleTime = Date.now() - this.lastSeen;
            // Only reconnect if REALLY stalled (90+ seconds with zero messages)
            if (idleTime > 90000 && this.isConnected()) {
                console.warn(`⚠️ Connection appears stalled (${Math.round(idleTime / 1000)}s idle). Reconnecting...`);
                if (this.ws) {
                    this.ws.close();
                }
            }
        }, 30000); // Check every 30 seconds
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
        // Don't reconnect if we intentionally disconnected
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnect attempts reached or intentional disconnect');
            return;
        }

        this.reconnectAttempts++;

        // Progressive backoff: Start fast, then slow down
        let delay;
        if (this.reconnectAttempts <= 3) {
            delay = 1000; // First 3: reconnect after 1 second
        } else if (this.reconnectAttempts <= 10) {
            delay = 3000; // Next 7: reconnect after 3 seconds
        } else {
            delay = 10000; // After that: 10 seconds
        }

        console.log(`Reconnecting... (attempt ${this.reconnectAttempts}) in ${delay}ms`);

        setTimeout(() => {
            if (this.sessionId && this.reconnectAttempts < this.maxReconnectAttempts) {
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
                // Add a small delay to let the system stabilize after visibility change
                setTimeout(() => this.checkAndRecover(), 2000);
            }
        });

        // 2. Reconnect when window gets focus
        window.addEventListener('focus', () => {
            console.log('🎯 App focused. Checking connection...');
            // Add a small delay to prevent race conditions
            setTimeout(() => this.checkAndRecover(), 2000);
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

        // If truly disconnected (not just idle)
        if (!this.isConnected()) {
            console.warn(`♻️ Recovering lost connection...`);
            if (this.ws && this.ws.readyState !== WebSocket.CLOSED) {
                this.ws.onclose = null; // Prevent double trigger
                this.ws.close();
            }
            this.reconnectAttempts = 0; // Fresh start
            this.connect(this.sessionId, this.clientId);
        } else if (idleTime > 90000) {
            // Only if REALLY stale and still showing as connected
            console.warn(`♻️ Connection stale for ${Math.round(idleTime / 1000)}s, refreshing...`);
            if (this.ws) {
                this.ws.onclose = null;
                this.ws.close();
            }
            this.reconnectAttempts = 0;
            this.connect(this.sessionId, this.clientId);
        } else {
            console.log('Connection healthy, no recovery needed');
        }
    }
}

// Singleton instance
const wsClient = new WebSocketClient();
wsClient.setupSelfHealing(); // Activate background recovery

export default wsClient;
