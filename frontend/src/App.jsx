import { useState, useEffect } from 'react';
import LoginPage from './components/LoginPage';
import Dashboard from './components/Dashboard';
import wsClient from './services/websocket';
import { getSession, setSession, clearSession, getAlerts, getLogs, setWatchlistDate, refreshWatchlist, getWatchlist, getPaperSummary } from './services/api';
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
  const [alerts, setAlerts] = useState(() => {
    try {
      const saved = localStorage.getItem('trade_yantra_alerts');
      return saved ? JSON.parse(saved) : [];
    } catch { return []; }
  });
  const [logs, setLogs] = useState(() => {
    try {
      const saved = localStorage.getItem('trade_yantra_logs');
      return saved ? JSON.parse(saved) : [];
    } catch { return []; }
  });
  const [paperTrades, setPaperTrades] = useState([]);
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
    const sid = session?.sessionId || session?.session_id;
    const cid = session?.clientId || session?.client_id;
    if (!sid) return;
    const syncAndRefresh = async () => {
      try {
        console.log('📅 Syncing reference date to backend:', referenceDate);
        await setWatchlistDate(sid, referenceDate, cid);
        // Refresh watchlist to get new High/Low for this date
        await refreshWatchlist(sid, cid);
      } catch (err) {
        console.error('Failed to sync date or refresh watchlist:', err);
      }
    };
    syncAndRefresh();
  }, [referenceDate, session?.sessionId, session?.session_id]);


  useEffect(() => {
    localStorage.setItem('trade_yantra_watchlist', JSON.stringify(watchlist));
  }, [watchlist]);

  useEffect(() => {
    localStorage.setItem('trade_yantra_alerts', JSON.stringify(alerts));
  }, [alerts]);

  useEffect(() => {
    localStorage.setItem('trade_yantra_logs', JSON.stringify(logs));
  }, [logs]);

  const loadData = async (sessionId, isManualSync = false) => {
    setIsLoadingData(true);
    if (isManualSync) toast.loading('Syncing data from backend...', { id: 'sync-data' });

    // Use current session data from getSession() if not passed to ensure we have clientId
    const currentSession = session || getSession();
    const clientId = currentSession?.clientId || currentSession?.client_id;

    try {
      const [alertsData, logsData, wlData, paperData] = await Promise.all([
        getAlerts(sessionId, clientId).catch(() => ({ alerts: [] })),
        getLogs(sessionId, clientId).catch(() => ({ logs: [] })),
        getWatchlist(sessionId, clientId).catch(() => ({ watchlist: [] })),
        getPaperSummary(sessionId).catch(() => ({ trades: [] }))
      ]);

      console.log('📊 Loaded data from server:', {
        alerts: alertsData.alerts?.length || 0,
        logs: logsData.logs?.length || 0,
        watchlist: wlData.watchlist?.length || 0,
        healing: !!clientId
      });

      // --- DATA SYNC ---
      // If server returns data, it's the source of truth.
      if (Array.isArray(alertsData.alerts)) {
        setAlerts(alertsData.alerts);
        setIsPaused(alertsData.is_paused || false);
      }

      if (Array.isArray(logsData.logs)) {
        setLogs(logsData.logs);
      }

      if (Array.isArray(wlData.watchlist)) {
        setWatchlist(wlData.watchlist);
      }

      if (Array.isArray(paperData.trades)) {
        setPaperTrades(paperData.trades);
      }

      if (isManualSync) toast.success('Data synced from server!', { id: 'sync-data' });

    } catch (err) {
      console.error('Failed to load data:', err);
      if (isManualSync) toast.error('Sync failed', { id: 'sync-data' });
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

      if (data.paper_trades) {
        setPaperTrades(data.paper_trades);
      }
    };

    const handleAlertTriggered = (data) => {
      if (!data || !data.alert || !data.log) {
        console.error('Invalid alert_triggered data:', data);
        return;
      }

      const { alert, log } = data;

      // Remove triggered alert
      setAlerts((prevAlerts) =>
        prevAlerts.filter((a) => a.id !== alert.id)
      );

      // Add to logs
      setLogs((prevLogs) => [log, ...prevLogs]);

      // Show notification
      const direction = alert.condition === 'ABOVE' ? '↑' : '↓';

      showNotification(`🔔 ${alert.symbol} Alert!`, {
        body: `Price ₹${log.price?.toFixed(2)} crossed ${direction} target ₹${alert.price?.toFixed(2)}`,
        icon: '/logo.png',
        badge: '/logo.png',
        tag: `alert-${alert.id}`,
        vibrate: [200, 100, 200],
        requireInteraction: true,
        data: { url: '/' }
      });

      // Show Toast backup
      toast.success(`🔔 ${alert.symbol}: Crossed ${alert.price?.toFixed(2)}`, {
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

  const connectWebSocket = (sessionId, clientId = null) => {
    wsClient.connect(sessionId, clientId);
  };

  // Load session on mount
  useEffect(() => {
    const savedSession = getSession();
    if (savedSession) {
      // Set local state temporarily for fast UI load
      setSessionState(savedSession);

      const sid = savedSession.sessionId || savedSession.session_id;
      const cid = savedSession.clientId || savedSession.client_id;
      // Verify with backend
      import('./services/api').then(({ checkSession }) => {
        console.log('🔍 Verifying background session:', sid);
        checkSession(sid, cid).then((data) => {
          console.log('✅ Session verified at:', new Date().toLocaleTimeString());
        }).catch((err) => {
          const status = err.response?.status;
          console.warn(`⚠️ Session verification returned ${status || 'network error'}: ${err.message}`);

          if (status === 401 || status === 404) {
            console.error('❌ Session expired or invalid on server. Logging out...');
            // Wait, even here we should be careful. If it's a cold start, 404 might be temporary.
            // But checkSession is only called on MOUNT. If it fails here, the server really doesn't know us.
            handleLogout();
          } else {
            console.log('🛡️ Persistence: Keeping session alive despite server/network hiccup.');
          }
        });
      }).catch((importErr) => {
        console.error('❌ Critical failure during session check:', importErr);
      });

      connectWebSocket(sid, cid);
      requestNotificationPermission();

      // Silent restore on refresh (no toast)
      loadData(sid, false);
    }

    // CROSS-TAB SYNC: Detect if logged out in another tab
    const handleStorageChange = (e) => {
      if (e.key === 'trade_yantra_session' && !e.newValue) {
        console.log('🚪 Session cleared in another tab, logging out...');
        handleLogout();
      }
    };
    window.addEventListener('storage', handleStorageChange);

    // Register SW
    registerServiceWorker();

    // Visibility API listener
    const handleVisibilityChange = () => {
      const visible = document.visibilityState === 'visible';
      setIsVisible(visible);

      // If we become visible and session exists, ensure WS is connected
      if (visible) {
        const savedSession = getSession();
        if (savedSession && !wsClient.isConnected() && !wsClient.isConnecting()) {
          console.log('🔄 App became visible, ensuring WebSocket connection...');
          // Small delay to let browser stabilize after becoming visible
          setTimeout(() => {
            wsClient.connect(savedSession.sessionId);
          }, 1000);
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('storage', handleStorageChange);
    };
  }, []);

  const handleLoginSuccess = (sessionData) => {
    const sid = sessionData.sessionId || sessionData.session_id;
    const cid = sessionData.clientId || sessionData.client_id;
    setSession(sessionData); // Saves to storage via api.js setSession
    setSessionState(sessionData);
    loadData(sid);
    connectWebSocket(sid, cid);

    // Request notification permission
    requestNotificationPermission();
  };

  const handleLogout = async () => {
    // 1. Clear locally FIRST - instant UI reaction
    wsClient.disconnect();
    clearSession();
    setSessionState(null);
    setAlerts([]);
    setLogs([]);
    setIsPaused(false);
    setWsStatus('disconnected');
    setActiveTab('watchlist');

    // 2. Notify backend in background (don't block UI)
    try {
      if (session) {
        import('./services/api').then(({ logout }) => {
          logout(session.sessionId || session.session_id).catch(e => console.warn('Backend logout failed:', e));
        });
      }
    } catch (err) {
      console.error('Logout handler cleanup error:', err);
    }

    toast.success('Logged out successfully');
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
            paperTrades={paperTrades}
            setPaperTrades={setPaperTrades}
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
            onRefreshData={loadData}
          />
        </>
      )}
    </div>
  );
}

export default App;
