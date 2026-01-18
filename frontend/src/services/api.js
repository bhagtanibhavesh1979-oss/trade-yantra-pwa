import axios from 'axios';

const getBaseUrl = () => {
    // 1. Detective work based on location (Highest priority for local dev)
    const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    if (isLocal) return 'http://127.0.0.1:8002';

    // 2. Prioritize environment variable for cloud/custom deployments
    const envUrl = import.meta.env.VITE_API_URL;
    if (envUrl) return envUrl;

    // Default Fallback (US-Central1 - Original Working Region)
    return 'https://trade-yantra-api-ibynnqazflq-uc.a.run.app';
};

const API_BASE_URL = getBaseUrl();
console.log('🌐 API_BASE_URL:', API_BASE_URL);

// Axios instance with default config
const api = axios.create({
    baseURL: API_BASE_URL,
    timeout: 30000, // 30 seconds for GCS cold starts
    headers: {
        'Content-Type': 'application/json',
    },
});

// Session storage keys
const SESSION_KEY = 'trade_yantra_session';

// Session helpers
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
export const login = async (apiKey, clientId, password, totpSecret) => {
    const response = await api.post('/api/auth/login', {
        api_key: apiKey,
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
    // params: { symbol, date, start_time, end_time, is_custom_range, client_id }
    const response = await api.post('/api/alerts/generate', {
        session_id: sessionId,
        ...params
    });
    return response.data;
};

// Generate High/Low alerts for ALL watchlist stocks
export const generateBulkAlerts = async (sessionId, params) => {
    // params: { date, start_time, end_time, is_custom_range, levels, client_id }
    const response = await api.post('/api/alerts/generate-bulk', {
        session_id: sessionId,
        ...params
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

export const clearAllAlerts = async (sessionId, clientId = null) => {
    const response = await api.post('/api/alerts/clear-all', {
        session_id: sessionId,
        client_id: clientId,
    });
    return response.data;
};

export const deleteMultipleAlerts = async (sessionId, alertIds, clientId = null) => {
    // Using POST for delete-multiple to ensure body is handled correctly by all network layers
    const response = await api.post('/api/alerts/delete-multiple', {
        session_id: sessionId,
        client_id: clientId,
        alert_ids: alertIds,
    });
    return response.data;
};

export const pauseAlerts = async (sessionId, isPaused, clientId = null) => {
    const response = await api.post('/api/alerts/pause', {
        session_id: sessionId,
        client_id: clientId,
        paused: isPaused,
    });
    return response.data;
};

export const getLogs = async (sessionId, clientId = null) => {
    const url = clientId ? `/api/alerts/logs/${sessionId}?client_id=${clientId}` : `/api/alerts/logs/${sessionId}`;
    const response = await api.get(url);
    return response.data;
};

// Paper Trading APIs
export const getPaperSummary = async (sessionId) => {
    const response = await api.get(`/api/paper/summary/${sessionId}`);
    return response.data;
};

export const togglePaperTrading = async (sessionId, enabled) => {
    const response = await api.post(`/api/paper/toggle/${sessionId}`, { enabled });
    return response.data;
};

export const closePaperTrade = async (sessionId, tradeId, ltp) => {
    const response = await api.post(`/api/paper/close/${sessionId}/${tradeId}?ltp=${ltp}`);
    return response.data;
};

// ... existing code ...
export const clearPaperTrades = async (sessionId) => {
    const response = await api.post(`/api/paper/clear/${sessionId}`);
    return response.data;
};

export const setVirtualBalance = async (sessionId, amount) => {
    const response = await api.post(`/api/paper/balance/${sessionId}`, { amount });
    return response.data;
};

export const setStopLoss = async (sessionId, tradeId, slPrice) => {
    const response = await api.post(`/api/paper/stoploss/${sessionId}/${tradeId}`, { sl_price: slPrice });
    return response.data;
};

export const manualTrade = async (sessionId, symbol, token, ltp, side, quantity) => {
    const response = await api.post(`/api/paper/trade/${sessionId}`, {
        symbol,
        token,
        ltp,
        side,
        quantity: parseInt(quantity) || 100
    });
    return response.data;
};
// ... existing code ...

export default api;
