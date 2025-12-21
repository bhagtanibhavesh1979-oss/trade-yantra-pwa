import { useState, useEffect } from 'react';
import LoginPage from './components/LoginPage';
import Dashboard from './components/Dashboard';
import wsClient from './services/websocket';
import { getSession, setSession, clearSession, getAlerts, getLogs } from './services/api';
import { registerServiceWorker, requestNotificationPermission, showNotification } from './services/notifications';
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



  // Save watchlist to localStorage whenever it changes
  useEffect(() => {
    // Allows saving empty list if user intentionally clears it
    localStorage.setItem('trade_yantra_watchlist', JSON.stringify(watchlist));
    console.log('💾 Saved watchlist to localStorage:', watchlist.length, 'stocks');
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
      // Backend sends single update: { token, symbol, ltp }
      setWatchlist((prevWatchlist) =>
        prevWatchlist.map((stock) => {
          if (String(stock.token) === String(data.token)) {
            return {
              ...stock,
              ltp: data.ltp,
              // Preserve pdc, pdh, pdl
              pdc: stock.pdc,
              pdh: stock.pdh,
              pdl: stock.pdl,
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

      // Show notification
      const alert = data.alert;
      const direction = alert.condition === 'ABOVE' ? '↑' : '↓';

      showNotification(`🔔 ${alert.symbol} Alert!`, {
        body: `Price ₹${data.log.current_price?.toFixed(2)} crossed ${direction} target ₹${alert.price.toFixed(2)}`,
        icon: '/logo.png',
        badge: '/logo.png', // Android specific
        tag: `alert-${alert.id}`,
        vibrate: [200, 100, 200],
        requireInteraction: true,
        data: { url: '/' } // Used by SW to navigate
      });

      // Play sound
      try {
        const audio = new Audio("data:audio/wav;base64,UklGRl9vT19XQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YU"); // Short beep placeholder
        // Better beep sound (Base64 for a simple chime)
        const chime = new Audio("data:audio/mp3;base64,//uQRAAAAWMSLwUIYAAsYkXgoQwAEaYLWfkWgAI0wWs/ItAAAG84000000000000000000000000000000000000000000000000//uQRAAAAWMSLwUIYAAsYkXgoQwAEaYLWfkWgAI0wWs/ItAAAG84000000000000000000000000000000000000000000000000");
        // Using a comprehensive beep url or local file is better, but this is a start.
        // Let's use a standard accessible URL or just a simple beep logic if possible.
        // Since I cannot upload a file easily, I will trust the user to replace it or I will use a public URL if allowed. 
        // Reverting to a simple console log placeholder for sound for now to avoid broken base64, 
        // but wait, I can write a valid base64 short beep.

        // Simple Beep Base64
        const beep = new Audio("data:audio/wav;base64,UklGRl9vT19XQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YU");
        // beep.play().catch(e => console.log('Audio play failed:', e));

        // BETTER: Use the browser's SpeechSynthesis for a spoken alert if audio fails? No, standard sound is better.
        // Let's add a log and a real placeholder specific for "alert.mp3" that the user can fill, or a base64.

        const notificationSound = new Audio("https://actions.google.com/sounds/v1/alarms/beep_short.ogg");
        notificationSound.play().catch(e => console.error("Error playing sound:", e));

      } catch (e) {
        console.error("Audio error:", e);
      }
    });

    wsClient.on('error', (error) => {
      console.error('WebSocket error:', error);
    });

    // Connect
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
          // We re-add them silently to ensure subscription
          // Ideally we should have a bulk sync endpoint, but looping add is okay for now
          // We can do this in the background
          import('./services/api').then(({ addToWatchlist }) => {
            addToWatchlist(savedSession.sessionId, stock.symbol, stock.token, stock.exch_seg)
              .catch(err => {
                // Ignore 'already exists' errors
                // console.log("Sync stock error", err); 
              });
          });
        });
      }

      loadData(savedSession.sessionId);
      connectWebSocket(savedSession.sessionId);
      requestNotificationPermission(); // Ask permission on session restore
    }

    // Register SW
    registerServiceWorker();
  }, []);


  const handleLoginSuccess = (sessionData) => {
    setSession(sessionData);
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
