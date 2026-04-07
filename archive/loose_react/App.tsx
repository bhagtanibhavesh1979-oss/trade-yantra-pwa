import React, { useState, useEffect } from 'react';
import { StockData, Alert, AlertCondition, ViewState, AlertLog } from './types';
// We import both, but in a real app you'd pick one. 
// Ideally we use realService if credentials are valid, but it falls back to simulation if CORS fails.
import { realAngelService } from './services/realAngelService';
import { angelService as mockService } from './services/mockAngelService';
import Navbar from './components/Navbar';
import AuthView from './components/AuthView';
import WatchlistView from './components/WatchlistView';
import AlertsView from './components/AlertsView';
import { v4 as uuidv4 } from 'uuid';

function App() {
  const [isDark, setIsDark] = useState(true);
  const [view, setView] = useState<ViewState>('AUTH');
  const [clientId, setClientId] = useState<string | null>(null);
  const [stocks, setStocks] = useState<StockData[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [logs, setLogs] = useState<AlertLog[]>([]);
  const [lastNotification, setLastNotification] = useState<string | null>(null);
  const [isPaused, setIsPaused] = useState(false);

  // Active Service - defaulting to realService wrapper
  const activeService = realAngelService; 

  // Theme Toggler
  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDark]);

  // Data Subscription
  useEffect(() => {
    let unsubscribe: (() => void) | undefined;

    if (clientId) {
      activeService.connect();
      unsubscribe = activeService.subscribe((data) => {
        setStocks([...data]); 
        checkAlerts(data);
      });
    }

    return () => {
      if (unsubscribe) unsubscribe();
      activeService.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId]); 

  const checkAlerts = (currentStocks: StockData[]) => {
    if (isPaused) return; 

    setAlerts(prevAlerts => {
      const activeAlerts = prevAlerts.filter(a => a.active);
      const remainingAlerts: Alert[] = [];
      const newLogs: AlertLog[] = [];
      let hasChanges = false;

      activeAlerts.forEach(alert => {
        const stock = currentStocks.find(s => s.token === alert.token);
        if (!stock) {
          remainingAlerts.push(alert);
          return;
        }

        let triggered = false;
        if (alert.condition === AlertCondition.ABOVE && stock.ltp > alert.price) {
          triggered = true;
        } else if (alert.condition === AlertCondition.BELOW && stock.ltp < alert.price) {
          triggered = true;
        }

        if (triggered) {
          hasChanges = true;
          newLogs.push({
            id: uuidv4(),
            symbol: stock.symbol,
            message: `${stock.symbol} crossed ${alert.condition} ${alert.price}`,
            timestamp: new Date(),
            price: stock.ltp,
            type: 'TRIGGERED'
          });
        } else {
          remainingAlerts.push(alert);
        }
      });

      if (newLogs.length > 0) {
        setLogs(prevLogs => [...newLogs, ...prevLogs].slice(0, 50)); 
        setLastNotification(newLogs[0].message);
        setTimeout(() => setLastNotification(null), 4000);
      }

      return hasChanges ? remainingAlerts : prevAlerts;
    });
  };

  const handleLogin = (id: string, apiKey: string, jwtToken: string, feedToken: string) => {
    setClientId(id);
    // Initialize the real service with tokens
    realAngelService.init(apiKey, jwtToken, feedToken);
    
    // Seed with mock data for initial view if empty
    if (realAngelService['currentStocks'].length === 0) {
       realAngelService.setInitialStocks(mockService.getStocks());
    }
    
    setView('WATCHLIST');
  };

  const handleLogout = () => {
    setClientId(null);
    setView('AUTH');
    setStocks([]);
    activeService.disconnect();
  };

  const handleAddStock = async (symbol: string) => {
    await activeService.addToken(symbol);
  };

  const handleRemoveStock = (token: string) => {
    activeService.removeToken(token);
  };

  const handleAutoAddAlerts = () => {
    const newAlerts: Alert[] = [];

    stocks.forEach(stock => {
      const wc = stock.weeklyClose;
      const ltp = stock.ltp;
      const pattern = wc > 3333 ? [30, 60, 90] : [3, 6, 9];
      const levels: number[] = [];

      // Resistance
      let currentLevel = wc;
      let i = 0;
      while (currentLevel < ltp * 1.2 || i < 5) {
        const step = pattern[i % 3];
        currentLevel += step;
        levels.push(currentLevel);
        i++;
      }

      // Support
      currentLevel = wc;
      i = 0;
      while (currentLevel > ltp * 0.8 || i < 5) {
        const step = pattern[i % 3];
        currentLevel -= step;
        levels.push(currentLevel);
        i++;
      }

      levels.forEach(level => {
        const cleanLevel = Math.round(level * 100) / 100;
        let condition: AlertCondition | null = null;

        if (cleanLevel > ltp) condition = AlertCondition.ABOVE;
        else if (cleanLevel < ltp) condition = AlertCondition.BELOW;

        if (condition) {
          const isDuplicate = 
            alerts.some(a => a.token === stock.token && a.condition === condition && Math.abs(a.price - cleanLevel) < 0.1) ||
            newAlerts.some(a => a.token === stock.token && a.condition === condition && Math.abs(a.price - cleanLevel) < 0.1);

          if (!isDuplicate) {
            newAlerts.push({
              id: uuidv4(),
              token: stock.token,
              symbol: stock.symbol,
              condition: condition,
              price: cleanLevel,
              active: true,
              createdAt: new Date(),
              type: 'AUTO'
            });
          }
        }
      });
    });
    
    if (newAlerts.length > 0) {
      setAlerts(prev => [...prev, ...newAlerts]);
      const message = `Generated ${newAlerts.length} levels in background`;
      setLastNotification(message);
      setLogs(prev => [{
        id: uuidv4(),
        symbol: 'SYSTEM',
        message: message,
        timestamp: new Date(),
        price: 0,
        type: 'INFO'
      }, ...prev]);
      setTimeout(() => setLastNotification(null), 3000);
    } else {
      setLastNotification(`No new unique levels needed.`);
      setTimeout(() => setLastNotification(null), 3000);
    }
  };

  const handleClearLogs = () => {
    setLogs([]);
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-background transition-colors duration-200 pb-20">
      <Navbar 
        currentView={view} 
        setView={setView} 
        isAuthenticated={!!clientId}
        onLogout={handleLogout}
        isDark={isDark}
        toggleTheme={() => setIsDark(!isDark)}
      />

      {lastNotification && (
        <div className="fixed top-20 right-4 z-50 animate-bounce">
          <div className="bg-primary text-white px-6 py-3 rounded-lg shadow-xl flex items-center gap-2">
            <span className="text-xl">🔔</span>
            <span className="font-medium">{lastNotification}</span>
          </div>
        </div>
      )}

      <main className="container mx-auto">
        {view === 'AUTH' && (
          <AuthView onLogin={handleLogin} />
        )}

        {view === 'WATCHLIST' && clientId && (
          <WatchlistView 
            stocks={stocks} 
            onAddStock={handleAddStock}
            onRemoveStock={handleRemoveStock}
          />
        )}

        {view === 'ALERTS' && clientId && (
          <AlertsView 
            stocks={stocks}
            alerts={alerts}
            logs={logs}
            isPaused={isPaused}
            onTogglePause={() => setIsPaused(!isPaused)}
            onAddAlert={(a) => setAlerts([...alerts, a])}
            onRemoveAlert={(id) => setAlerts(alerts.filter(a => a.id !== id))}
            onAutoAdd={handleAutoAddAlerts}
            onClearLogs={handleClearLogs}
          />
        )}
      </main>
    </div>
  );
}

export default App;