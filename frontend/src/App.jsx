import { useState, useEffect } from 'react';
import LoginPage from './components/LoginPage';
import Dashboard from './components/Dashboard';
import wsClient from './services/websocket';
import { getSession, setSession, clearSession, getAlerts, getLogs, setWatchlistDate, refreshWatchlist } from './services/api';
import { registerServiceWorker, requestNotificationPermission, showNotification } from './services/notifications';
import { Toaster, toast } from 'react-hot-toast';
import './App.css';

function App() {
  // Initialize watchlist from localStorage with lazy loading
  const [watchlist, setWatchlist] = useState(() => {
    try {
      const saved = localStorage.getItem('trade_yantra_watchlist');
      // Ensure we start with empty array if nothing saved
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [session, setSessionState] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [logs, setLogs] = useState([]);
  const [isPaused, setIsPaused] = useState(false);
  const [wsStatus, setWsStatus] = useState('disconnected');
  const [isLoadingData, setIsLoadingData] = useState(false);
  const [isVisible, setIsVisible] = useState(true);

  const [activeTab, setActiveTab] = useState('watchlist');
  const [preSelectedAlertSymbol, setPreSelectedAlertSymbol] = useState(null);

  // Sync reference date across tabs
  const [referenceDate, setReferenceDate] = useState(() => {
    try {
      const saved = localStorage.getItem('trade_yantra_alert_settings');
      if (saved) {
        const settings = JSON.parse(saved);
        return settings.date || new Date().toISOString().split('T')[0];
      }
    } catch (e) {
      console.error('Failed to parse settings:', e);
    }
    return new Date().toISOString().split('T')[0];
  });

  // Sync reference date to backend and refresh watchlist
  useEffect(() => {
    if (!session) return;
    const syncAndRefresh = async () => {
      try {
        console.log('📅 Syncing reference date to backend:', referenceDate);
        await setWatchlistDate(session.sessionId, referenceDate);
        // Refresh watchlist to get new High/Low for this date
        await refreshWatchlist(session.sessionId);
      } catch (err) {
        console.error('Failed to sync date or refresh watchlist:', err);
      }
    };
    syncAndRefresh();
  }, [referenceDate, session?.sessionId]);


  // Save watchlist to localStorage whenever it changes
  useEffect(() => {
    // Allows saving empty list if user intentionally clears it
    localStorage.setItem('trade_yantra_watchlist', JSON.stringify(watchlist));
  }, [watchlist]);

  const loadData = async (sessionId) => {
    setIsLoadingData(true);
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
    } finally {
      setIsLoadingData(false);
    }
  };

  // Stability: Define WebSocket listeners once outside the component's main flow
  // to avoid duplication on every reconnect
  useEffect(() => {
    if (!session) return;

    const handleConnected = () => setWsStatus('connected');
    const handleDisconnected = () => setWsStatus('disconnected');
    const handlePriceUpdate = (data) => {
      setWatchlist((prevWatchlist) =>
        prevWatchlist.map((stock) => {
          if (String(stock.token) === String(data.token)) {
            return {
              ...stock,
              ltp: data.ltp,
              pdc: stock.pdc,
              pdh: stock.pdh,
              pdl: stock.pdl,
            };
          }
          return stock;
        })
      );
    };

    const handleAlertTriggered = (data) => {
      // Remove triggered alert
      setAlerts((prevAlerts) =>
        prevAlerts.filter((alert) => alert.id !== data.alert.id)
      );

      // Add to logs
      setLogs((prevLogs) => [data.log, ...prevLogs]);

      // Show notification
      const alert = data.alert;
      const direction = alert.condition === 'ABOVE' ? '↑' : '↓';

      showNotification(`🔔 ${alert.symbol} Alert!`, {
        body: `Price ₹${data.log.current_price?.toFixed(2)} crossed ${direction} target ₹${alert.price.toFixed(2)}`,
        icon: '/logo.png',
        badge: '/logo.png',
        tag: `alert-${alert.id}`,
        vibrate: [200, 100, 200],
        requireInteraction: true,
        data: { url: '/' }
      });

      // Show Toast backup
      toast.success(`🔔 ${alert.symbol}: Crossed ${alert.price.toFixed(2)}`, {
        duration: 6000,
        style: {
          border: '1px solid #667EEA',
          padding: '16px',
          color: '#fff',
          background: '#1F2937',
        },
        iconTheme: {
          primary: '#667EEA',
          secondary: '#FFFAEE',
        },
      });

      // Vibration Feedback
      if ('vibrate' in navigator) {
        navigator.vibrate([200, 100, 200]);
      }
    };

    wsClient.on('connected', handleConnected);
    wsClient.on('disconnected', handleDisconnected);
    wsClient.on('price_update', handlePriceUpdate);
    wsClient.on('alert_triggered', handleAlertTriggered);
    wsClient.on('error', (error) => {
      console.error('WebSocket error:', error);
    });

    return () => {
      wsClient.off('connected', handleConnected);
      wsClient.off('disconnected', handleDisconnected);
      wsClient.off('price_update', handlePriceUpdate);
      wsClient.off('alert_triggered', handleAlertTriggered);
      wsClient.off('error', (error) => {
        console.error('WebSocket error:', error);
      });
    };
  }, [session]);

  const connectWebSocket = (sessionId) => {
    wsClient.connect(sessionId);
  };

  // Load session on mount
  useEffect(() => {
    const savedSession = getSession();
    if (savedSession) {
      setSessionState(savedSession);
      // Watchlist is already initialized from localStorage via useState

      // Auto-sync local watchlist to backend (if backend restarted)
      const localWatchlist = JSON.parse(localStorage.getItem('trade_yantra_watchlist') || '[]');
      if (localWatchlist.length > 0) {
        localWatchlist.forEach(stock => {
          // Re-subscribe silently
          import('./services/api').then(({ addToWatchlist }) => {
            addToWatchlist(savedSession.sessionId, stock.symbol, stock.token, stock.exch_seg)
              .catch(() => { });
          });
        });
      }

      loadData(savedSession.sessionId);
      connectWebSocket(savedSession.sessionId);
      requestNotificationPermission(); // Ask permission on session restore
    }

    // Register SW
    registerServiceWorker();

    // Visibility API listener
    const handleVisibilityChange = () => {
      const visible = document.visibilityState === 'visible';
      setIsVisible(visible);

      // If we become visible and session exists, ensure WS is connected
      if (visible) {
        const savedSession = getSession();
        if (savedSession && wsClient.ws?.readyState !== WebSocket.OPEN) {
          console.log('🔄 App became visible, ensuring WebSocket connection...');
          wsClient.connect(savedSession.sessionId);
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  const handleLoginSuccess = (sessionData) => {
    setSession(sessionData); // Saves to storage via api.js setSession
    setSessionState(sessionData);
    loadData(sessionData.sessionId);
    connectWebSocket(sessionData.sessionId);

    // Request notification permission
    requestNotificationPermission();
  };

  const handleLogout = () => {
    wsClient.disconnect();
    clearSession();
    // DON'T clear watchlist - it should persist across logins
    setSessionState(null);
    setAlerts([]);
    setLogs([]);
    setIsPaused(false);
    setWsStatus('disconnected');
    setActiveTab('watchlist');
  };

  return (
    <div className="min-h-screen">
      {!session ? (
        <>
          <Toaster
            position="top-right"
            toastOptions={{
              className: '',
              style: {
                background: '#1F2937',
                color: '#fff',
                border: '1px solid #374151',
              },
            }}
          />
          <LoginPage onLoginSuccess={handleLoginSuccess} />
        </>
      ) : (
        <>
          <Toaster
            position="top-right"
            toastOptions={{
              className: '',
              style: {
                background: '#1F2937',
                color: '#fff',
                border: '1px solid #374151',
              },
            }}
          />
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
            referenceDate={referenceDate}
            setReferenceDate={setReferenceDate}
            wsStatus={wsStatus}
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            preSelectedAlertSymbol={preSelectedAlertSymbol}
            setPreSelectedAlertSymbol={setPreSelectedAlertSymbol}
            isLoadingData={isLoadingData}
            isVisible={isVisible}
          />
        </>
      )}
    </div>
  );
}

export default App;
