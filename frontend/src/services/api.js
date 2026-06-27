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

// Paper Trading APIs
export const runBacktest = async (sessionId, params, clientId = null) => {
    const response = await api.post(`/api/paper/backtest/${sessionId}`, { ...params, client_id: clientId });
    return response.data;
};

// Planet Nakshatra Backtest
export const runPlanetNakshatraBacktest = async (sessionId, { years }, clientId = null) => {
    const response = await api.get(`/api/astro/backtest/planet-nakshatra`, {
        params: {
            years,
            session_id: sessionId,
            client_id: clientId,
        },
    });
    return response.data;
};

export default api;

