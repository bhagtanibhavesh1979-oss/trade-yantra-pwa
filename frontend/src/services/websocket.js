const getWebSocketUrl = () => {
    // 1. Detective work based on location (Highest priority for local dev)
    const hostname = window.location.hostname;
    const isLocal = hostname === 'localhost' || hostname === '127.0.0.1';
    if (isLocal) return 'ws://127.0.0.1:8002';

    // 2. Detect local network IPs (e.g. 192.168.x.x, 10.x.x.x, 172.16-31.x.x) for local mobile testing
    const isLocalIp = hostname.startsWith('192.168.') || 
                      hostname.startsWith('10.') || 
                      (hostname.startsWith('172.') && (() => {
                          const parts = hostname.split('.');
                          if (parts.length >= 2) {
                              const sec = parseInt(parts[1], 10);
                              return sec >= 16 && sec <= 31;
                          }
                          return false;
                      })());
                      
    if (isLocalIp) {
        return `ws://${hostname}:8002`;
    }

    // 3. Prioritize environment variable for cloud/custom deployments
    const envUrl = import.meta.env.VITE_API_URL;
    if (envUrl) {
        return envUrl.replace(/^https:/, 'wss:').replace(/^http:/, 'ws:');
    }

    // 4. Default Fallback: Unified secure WebSocket path via Caddy (wss://tradeyantra.co.in)
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${wsProtocol}//${window.location.host}`;
};

const WS_BASE_URL = getWebSocketUrl();

class WebSocketClient {
    constructor() {
        this.ws = null;
        this.sessionId = null;
        this.clientId = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 999999; // Practically infinite
        this.reconnectDelay = 2000;
        this.pingInterval = null;
        this.watchdogInterval = null;
        this.lastSeen = Date.now();
        this.tokenCallbacks = new Map();
        this.subscribedTokens = new Set();
        this.pendingMessages = [];
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
            this.lastSeen = Date.now();
            this.emit('connected', { sessionId });

            // Re-subscribe all persisted chart tokens after reconnect
            for (const token of this.subscribedTokens) {
                this.send({ type: 'subscribe_token', token });
            }

            // Flush any queued messages that were waiting for an open socket
            if (this.pendingMessages.length > 0) {
                this.pendingMessages.forEach((message) => this.send(message));
                this.pendingMessages = [];
            }
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
                // Also emit to update UI status (covers race conditions where onopen fired before listeners attached)
                this.emit('connected', data);
                break;

            case 'price_update':
                console.log('[WS] Price update received:', data.symbol, data.ltp);
                this.emit('price_update', data);
                if (data.token != null) {
                    const tokenKey = String(data.token);
                    if (this.tokenCallbacks.has(tokenKey)) {
                        const callback = this.tokenCallbacks.get(tokenKey);
                        callback(data);
                    }
                }
                break;

            case 'subscription_confirmation':
                console.log('[WS] Subscription confirmed:', data);
                break;

            case 'unsubscription_confirmation':
                console.log('[WS] Unsubscription confirmed:', data);
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
                    // console.log('💓 Sending Ping'); // Uncomment for deep debug
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

    subscribeToToken(token, callback) {
        const tokenKey = String(token);
        this.tokenCallbacks.set(tokenKey, callback);
        this.subscribedTokens.add(tokenKey);
        const message = { type: 'subscribe_token', token: tokenKey };
        console.log('[WS] subscribeToToken', tokenKey, 'connected=', this.isConnected());
        if (this.isConnected()) {
            this.send(message);
        } else {
            this.pendingMessages.push(message);
        }
    }

    unsubscribeFromToken(token) {
        const tokenKey = String(token);
        this.tokenCallbacks.delete(tokenKey);
        this.subscribedTokens.delete(tokenKey);
        const message = { type: 'unsubscribe_token', token: tokenKey };
        if (this.isConnected()) {
            this.send(message);
        } else {
            // If the socket is not connected yet, remove any queued subscribe for this token
            this.pendingMessages = this.pendingMessages.filter(msg => !(msg.type === 'subscribe_token' && msg.token === tokenKey));
        }
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
                console.log('👀 App visible. Force checking connection...');
                // Immediate check for mobile responsiveness
                this.checkAndRecover();
                // Follow up check
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