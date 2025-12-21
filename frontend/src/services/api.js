import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8002';

// Axios instance with default config
const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Session storage keys
const SESSION_KEY = 'trade_yantra_session';

// Session helpers
export const getSession = () => {
    const sessionData = sessionStorage.getItem(SESSION_KEY);
    return sessionData ? JSON.parse(sessionData) : null;
};

export const setSession = (sessionData) => {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(sessionData));
};

export const clearSession = () => {
    sessionStorage.removeItem(SESSION_KEY);
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

export const checkSession = async (sessionId) => {
    const response = await api.get(`/api/auth/session/${sessionId}`);
    return response.data;
};

// Watchlist APIs
export const getWatchlist = async (sessionId) => {
    const response = await api.get(`/api/watchlist/${sessionId}`);
    return response.data;
};

export const addToWatchlist = async (sessionId, symbol, token, exchSeg) => {
    const response = await api.post('/api/watchlist/add', {
        session_id: sessionId,
        symbol: symbol,
        token: token,
        exch_seg: exchSeg,
    });
    return response.data;
};

export const removeFromWatchlist = async (sessionId, token) => {
    const response = await api.delete('/api/watchlist/remove', {
        data: {
            session_id: sessionId,
            token: token,
        },
    });
    return response.data;
};

export const refreshWatchlist = async (sessionId) => {
    const response = await api.post('/api/watchlist/refresh', {
        session_id: sessionId,
    });
    return response.data;
};

export const setWatchlistDate = async (sessionId, date) => {
    const response = await api.post('/api/watchlist/set-date', {
        session_id: sessionId,
        date: date,
    });
    return response.data;
};

export const searchSymbols = async (query) => {
    const response = await api.get(`/api/watchlist/search/${query}`);
    return response.data;
};

// Alerts APIs
export const getAlerts = async (sessionId) => {
    const response = await api.get(`/api/alerts/${sessionId}`);
    return response.data;
};

// Generate High/Low alerts
export const generateAlerts = async (sessionId, params) => {
    // params: { symbol, date, start_time, end_time, is_custom_range }
    const response = await api.post('/api/alerts/generate', {
        session_id: sessionId,
        ...params
    });
    return response.data;
};

// Generate High/Low alerts for ALL watchlist stocks
export const generateBulkAlerts = async (sessionId, params) => {
    // params: { date, start_time, end_time, is_custom_range, levels }
    const response = await api.post('/api/alerts/generate-bulk', {
        session_id: sessionId,
        ...params
    });
    return response.data;
};

export const deleteAlert = async (sessionId, alertId) => {
    const response = await api.delete('/api/alerts/delete', {
        data: {
            session_id: sessionId,
            alert_id: alertId,
        },
    });
    return response.data;
};

export const clearAllAlerts = async (sessionId) => {
    const response = await api.delete('/api/alerts/clear-all', {
        data: {
            session_id: sessionId,
        },
    });
    return response.data;
};

export const pauseAlerts = async (sessionId, isPaused) => {
    const response = await api.post('/api/alerts/pause', {
        session_id: sessionId,
        paused: isPaused,
    });
    return response.data;
};

export const getLogs = async (sessionId) => {
    const response = await api.get(`/api/alerts/logs/${sessionId}`);
    return response.data;
};

export default api;
