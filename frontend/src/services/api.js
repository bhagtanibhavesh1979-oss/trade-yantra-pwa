import axios from 'axios';

const getBaseUrl = () => {
    const hostname = window.location.hostname;
    const isLocal = hostname === 'localhost' || hostname === '127.0.0.1';
    if (isLocal) return 'http://127.0.0.1:8002';

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

    if (isLocalIp) return `http://${hostname}:8002`;

    const envUrl = import.meta.env.VITE_API_URL;
    if (envUrl) return envUrl;

    return '';
};

export const API_BASE_URL = getBaseUrl();
console.log('🌐 API_BASE_URL:', API_BASE_URL);

const api = axios.create({
    baseURL: API_BASE_URL,
    timeout: 60000,
    headers: {
        'Content-Type': 'application/json',
    },
});

const SESSION_KEY = 'trade_yantra_session';

export const getSession = () => {
    const sessionData = localStorage.getItem(SESSION_KEY);
    return sessionData ? JSON.parse(sessionData) : null;
};

export const setSession = (sessionData) => {
    localStorage.setItem(SESSION_KEY, JSON.stringify(sessionData));
};

export const clearSession = () => {
    localStorage.removeItem(SESSION_KEY);
};

// Auth APIs
export const login = async (apiKey, clientId, password, totpSecret, dataApiKey = null) => {
    const response = await api.post('/api/auth/login', {
        api_key: apiKey,
        data_api_key: dataApiKey,
        client_id: clientId,
        password: password,
        totp_secret: totpSecret,
    });
    return response.data;
};


export const logout = async (sessionId) => {
    const response = await api.post('/api/auth/logout', {
        session_id: sessionId,
    });
    clearSession();
    return response.data;
};

export const checkSession = async (sessionId, clientId = null) => {
    const url = clientId ? `/api/auth/verify/${sessionId}?client_id=${clientId}` : `/api/auth/verify/${sessionId}`;
    const response = await api.get(url);
    return response.data;
};

// Watchlist APIs
export const getWatchlist = async (sessionId, clientId = null) => {
    const url = clientId ? `/api/watchlist/${sessionId}?client_id=${clientId}` : `/api/watchlist/${sessionId}`;
    const response = await api.get(url);
    return response.data;
};

export const addToWatchlist = async (sessionId, symbol, token, exchSeg, clientId = null) => {
    const response = await api.post('/api/watchlist/add', {
        session_id: sessionId,
        client_id: clientId,
        symbol: symbol,
        token: token,
        exch_seg: exchSeg,
    });
    return response.data;
};

export const removeFromWatchlist = async (sessionId, token, clientId = null) => {
    const response = await api.post('/api/watchlist/remove', {
        session_id: sessionId,
        client_id: clientId,
        token: token,
    });
    return response.data;
};

export const refreshWatchlist = async (sessionId, clientId = null) => {
    const response = await api.post('/api/watchlist/refresh', {
        session_id: sessionId,
        client_id: clientId,
    });
    return response.data;
};

export const setWatchlistDate = async (sessionId, date, clientId = null) => {
    const response = await api.post('/api/watchlist/set-date', {
        session_id: sessionId,
        client_id: clientId,
        date: date,
    });
    return response.data;
};

export const searchSymbols = async (query) => {
    const response = await api.get(`/api/watchlist/search/${query}`);
    return response.data;
};

// Alerts APIs
export const getAlerts = async (sessionId, clientId = null) => {
    const url = clientId ? `/api/alerts/${sessionId}?client_id=${clientId}` : `/api/alerts/${sessionId}`;
    const response = await api.get(url);
    return response.data;
};

// Generate High/Low alerts
export const generateAlerts = async (sessionId, params) => {
    const response = await api.post('/api/alerts/generate', {
        session_id: sessionId,
        ...params,
    });
    return response.data;
};

// Generate High/Low alerts for ALL watchlist stocks
export const generateBulkAlerts = async (sessionId, params) => {
    const response = await api.post('/api/alerts/generate-bulk', {
        session_id: sessionId,
        ...params,
    });
    return response.data;
};

export const deleteAlert = async (sessionId, alertId, clientId = null) => {
    const response = await api.post('/api/alerts/delete', {
        session_id: sessionId,
        client_id: clientId,
        alert_id: alertId,
    });
    return response.data;
};

export const pauseAlerts = async (sessionId, paused, clientId = null) => {
    const response = await api.post('/api/alerts/pause', {
        session_id: sessionId,
        client_id: clientId,
        paused,
    });
    return response.data;
};

export const clearAllAlerts = async (sessionId, clientId = null) => {
    const response = await api.post('/api/alerts/clear-all', {
        session_id: sessionId,
        client_id: clientId,
    });
    return response.data;
};

export const deleteMultipleAlerts = async (sessionId, alertIds, clientId = null) => {
    const response = await api.post('/api/alerts/delete-multiple', {
        session_id: sessionId,
        client_id: clientId,
        alert_ids: alertIds,
    });
    return response.data;
};

// Logs APIs
export const getLogs = async (sessionId, clientId = null) => {
    const url = clientId ? `/api/alerts/logs/${sessionId}?client_id=${clientId}` : `/api/alerts/logs/${sessionId}`;
    const response = await api.get(url);
    return response.data;
};

// Paper Trading APIs

export const runBacktest = async (sessionId, params, clientId = null) => {
    const response = await api.post(`/api/paper/backtest/${sessionId}`, { ...params, client_id: clientId });
    return response.data;
};

// NOTE: keep existing exports used by other tabs.
// WatchlistTab imports manualTrade
export const manualTrade = async (sessionId, symbol, token, ltp, side, quantity) => {
    const response = await api.post(`/api/paper/trade/${sessionId}`, {
        symbol,
        token,
        ltp,
        side,
        quantity: parseInt(quantity) || 100,
    });
    return response.data;
};

// Planet Nakshatra/Pada Backtest
export const runPlanetNakshatraBacktest = async (sessionId, { years, planets } = {}, clientId = null) => {
    const response = await api.get(`/api/astro/backtest/planet-nakshatra`, {
        params: {
            years,
            planets, // optional: array of planet strings
            session_id: sessionId,
            client_id: clientId,
        },
    });
    return response.data;
};


// Paper / Orders APIs (required by OrdersTab.jsx)
export const getPaperSummary = async (sessionId, clientId = null) => {
    const url = clientId ? `/api/paper/summary/${sessionId}?client_id=${clientId}` : `/api/paper/summary/${sessionId}`;
    const response = await api.get(url);
    return response.data;
};

export const getPaperAnalytics = async (sessionId) => {
    const response = await api.get(`/api/paper/analytics/${sessionId}`);
    return response.data;
};

export const togglePaperTrading = async (sessionId, paused, clientId = null) => {
    const response = await api.post(`/api/paper/toggle/${sessionId}`, { paused, client_id: clientId });
    return response.data;
};

export const setStrategyMode = async (sessionId, mode, clientId = null) => {
    const response = await api.post(`/api/paper/strategy-mode/${sessionId}`, { strategy_mode: mode, client_id: clientId });
    return response.data;
};

export const setTriggerMode = async (sessionId, mode, clientId = null) => {
    const response = await api.post(`/api/paper/trigger-mode/${sessionId}`, { trigger_mode: mode, client_id: clientId });
    return response.data;
};

export const setBufferPct = async (sessionId, bufferPct, clientId = null) => {
    const response = await api.post(`/api/paper/buffer/${sessionId}`, { buffer_pct: bufferPct, client_id: clientId });
    return response.data;
};

export const setPaperSarTestMode = async (sessionId, mode, clientId = null) => {
    const response = await api.post(`/api/paper/sar-test-mode/${sessionId}`, { paper_sar_test_mode: mode, client_id: clientId });
    return response.data;
};

export const closePaperTrade = async (sessionId, tradeId, ltp, clientId = null) => {
    const response = await api.post(`/api/paper/close/${sessionId}`, { trade_id: tradeId, ltp, client_id: clientId });
    return response.data;
};

export const clearPaperTrades = async (sessionId, clientId = null) => {
    const response = await api.post(`/api/paper/clear-trades/${sessionId}`, { client_id: clientId });
    return response.data;
};

export const setVirtualBalance = async (sessionId, amount, clientId = null) => {
    const response = await api.post(`/api/paper/balance/${sessionId}`, { amount, client_id: clientId });
    return response.data;
};

export const setStopLoss = async (sessionId, tradeId, stopLoss, clientId = null) => {
    const response = await api.post(`/api/paper/stop-loss/${sessionId}`, { trade_id: tradeId, stop_loss: stopLoss, client_id: clientId });
    return response.data;
};

export const setTarget = async (sessionId, tradeId, target, clientId = null) => {
    const response = await api.post(`/api/paper/target/${sessionId}`, { trade_id: tradeId, target, client_id: clientId });
    return response.data;
};

export const squareOffPositions = async (sessionId, clientId = null) => {
    const response = await api.post(`/api/paper/square-off/${sessionId}`, { client_id: clientId });
    return response.data;
};

// Live Orders APIs (required by LiveOrdersTab.jsx)
export const getLivePositions = async (sessionId, clientId = null) => {
    const url = clientId ? `/api/live/positions/${sessionId}?client_id=${clientId}` : `/api/live/positions/${sessionId}`;
    const response = await api.get(url);
    return response.data;
};

export const getLiveFunds = async (sessionId, clientId = null) => {
    const url = clientId ? `/api/live/funds/${sessionId}?client_id=${clientId}` : `/api/live/funds/${sessionId}`;
    const response = await api.get(url);
    return response.data;
};

export const toggleLiveTrading = async (sessionId, paused, clientId = null) => {
    const response = await api.post(`/api/live/toggle/${sessionId}`, { paused, client_id: clientId });
    return response.data;
};

export const updateLiveSettings = async (sessionId, settings, clientId = null) => {
    const response = await api.post(`/api/live/settings/${sessionId}`, { ...settings, client_id: clientId });
    return response.data;
};

export const placeLiveOrder = async (sessionId, order, clientId = null) => {
    const response = await api.post(`/api/live/order/${sessionId}`, { ...order, client_id: clientId });
    return response.data;
};

export const getLiveStatus = async (sessionId, clientId = null) => {
    const url = clientId ? `/api/live/status/${sessionId}?client_id=${clientId}` : `/api/live/status/${sessionId}`;
    const response = await api.get(url);
    return response.data;
};

export default api;











