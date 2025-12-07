import { useState, useEffect } from 'react';
import LoginPage from './components/LoginPage';
import Dashboard from './components/Dashboard';
import wsClient from './services/websocket';
import { getSession, setSession, clearSession, getWatchlist, getAlerts, getLogs } from './services/api';
import './App.css';

function App() {
  const [session, setSessionState] = useState(null);
  const [watchlist, setWatchlist] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [logs, setLogs] = useState([]);
  const [isPaused, setIsPaused] = useState(false);
  const [wsStatus, setWsStatus] = useState('disconnected');

  // Load session on mount
  useEffect(() => {
    const savedSession = getSession();
    if (savedSession) {
      setSessionState(savedSession);

      // Load watchlist from localStorage FIRST (before loadData)
      const savedWatchlist = localStorage.getItem('trade_yantra_watchlist');
      if (savedWatchlist) {
        try {
          const parsed = JSON.parse(savedWatchlist);
          setWatchlist(parsed);
          console.log('✅ Loaded watchlist from localStorage:', parsed.length, 'stocks');
        } catch (err) {
          console.error('❌ Failed to load watchlist from localStorage:', err);
        }
      }

      loadData(savedSession.sessionId);
      connectWebSocket(savedSession.sessionId);
    }
  }, []);

  // Save watchlist to localStorage whenever it changes
  useEffect(() => {
    if (watchlist.length > 0) {
      localStorage.setItem('trade_yantra_watchlist', JSON.stringify(watchlist));
      console.log('💾 Saved watchlist to localStorage:', watchlist.length, 'stocks');
    }
  }, [watchlist]);

  const loadData = async (sessionId) => {
    try {
      const [alertsData, logsData] = await Promise.all([
        getAlerts(sessionId),
        getLogs(sessionId),
      ]);

      // DON'T load watchlist from backend - use localStorage instead
      setAlerts(alertsData.alerts || []);
      setLogs(logsData.logs || []);
      setIsPaused(alertsData.is_paused || false);
    } catch (err) {
      console.error('Failed to load data:', err);
    }
  };

  const connectWebSocket = (sessionId) => {
    // WebSocket event listeners
    wsClient.on('connected', () => {
      setWsStatus('connected');
    });

    wsClient.on('disconnected', () => {
      setWsStatus('disconnected');
    });

    wsClient.on('price_update', (data) => {
      // Update watchlist with new prices
      setWatchlist((prevWatchlist) =>
        prevWatchlist.map((stock) => {
          if (data.updates && data.updates[stock.token]) {
            return {
              ...stock,
              ltp: data.updates[stock.token].ltp,
              wc: data.updates[stock.token].wc || stock.wc,
            };
          }
          return stock;
        })
      );
    });

    wsClient.on('alert_triggered', (data) => {
      // Remove triggered alert
      setAlerts((prevAlerts) =>
        prevAlerts.filter((alert) => alert.id !== data.alert.id)
      );

      // Add to logs
      setLogs((prevLogs) => [data.log, ...prevLogs]);

      // Show browser notification
      if (Notification.permission === 'granted') {
        const alert = data.alert;
        const direction = alert.condition === 'ABOVE' ? '↑' : '↓';
        new Notification(`🔔 ${alert.symbol} Alert!`, {
          body: `Price ₹${data.log.current_price?.toFixed(2)} crossed ${direction} target ₹${alert.price.toFixed(2)}`,
          icon: '/favicon.ico',
          requireInteraction: false,
          tag: alert.id,
        });
      }
    });

    wsClient.on('error', (error) => {
      console.error('WebSocket error:', error);
    });

    // Connect
    wsClient.connect(sessionId);
  };

  const handleLoginSuccess = (sessionData) => {
    setSession(sessionData);
    setSessionState(sessionData);
    loadData(sessionData.sessionId);
    connectWebSocket(sessionData.sessionId);

    // Request notification permission
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission().then((permission) => {
        if (permission === 'granted') {
          console.log('Notification permission granted');
        }
      });
    }
  };

  const handleLogout = () => {
    wsClient.disconnect();
    clearSession();
    // DON'T clear watchlist - it should persist across logins
    setSessionState(null);
    setWatchlist([]);
    setAlerts([]);
    setLogs([]);
    setIsPaused(false);
    setWsStatus('disconnected');
  };

  return (
    <div className="min-h-screen">
      {!session ? (
        <LoginPage onLoginSuccess={handleLoginSuccess} />
      ) : (
        <Dashboard
          session={session}
          onLogout={handleLogout}
          watchlist={watchlist}
          setWatchlist={setWatchlist}
          alerts={alerts}
          setAlerts={setAlerts}
          logs={logs}
          setLogs={setLogs}
          isPaused={isPaused}
          setIsPaused={setIsPaused}
          wsStatus={wsStatus}
        />
      )}
    </div>
  );
}

export default App;
