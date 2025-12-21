import React, { useState } from 'react';
import { Alert, AlertCondition, StockData, AlertLog } from '../types';
import Input from './Input';
import Button from './Button';
import { Bell, Trash2, Zap, History, Layers, EyeOff, Eye, Pause, Play, AlertTriangle } from 'lucide-react';
import { v4 as uuidv4 } from 'uuid';

interface AlertsViewProps {
  stocks: StockData[];
  alerts: Alert[];
  logs: AlertLog[];
  isPaused: boolean;
  onAddAlert: (alert: Alert) => void;
  onRemoveAlert: (id: string) => void;
  onAutoAdd: () => void;
  onClearLogs: () => void;
  onTogglePause: () => void;
}

const AlertsView: React.FC<AlertsViewProps> = ({ 
  stocks, 
  alerts, 
  logs,
  isPaused,
  onAddAlert, 
  onRemoveAlert,
  onAutoAdd,
  onClearLogs,
  onTogglePause
}) => {
  const [selectedToken, setSelectedToken] = useState<string>(stocks[0]?.token || '');
  const [condition, setCondition] = useState<AlertCondition>(AlertCondition.ABOVE);
  const [price, setPrice] = useState<string>('');
  const [showAutoAlerts, setShowAutoAlerts] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedToken || !price) return;

    const stock = stocks.find(s => s.token === selectedToken);
    if (!stock) return;

    const newAlert: Alert = {
      id: uuidv4(),
      token: stock.token,
      symbol: stock.symbol,
      condition,
      price: parseFloat(price),
      active: true,
      createdAt: new Date(),
      type: 'MANUAL'
    };

    onAddAlert(newAlert);
    setPrice('');
  };

  const manualAlerts = alerts.filter(a => a.type === 'MANUAL');
  const autoAlerts = alerts.filter(a => a.type === 'AUTO');

  // Group auto alerts by symbol for the summary
  const autoSummary = autoAlerts.reduce((acc, alert) => {
    acc[alert.symbol] = (acc[alert.symbol] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="max-w-6xl mx-auto py-6 px-4 space-y-6">
      
      {/* Top Section: Controls and Creation */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left: Create Manual Alert */}
        <div className="lg:col-span-1 bg-white dark:bg-surface p-6 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700">
          <h3 className="font-bold text-lg mb-4 text-slate-900 dark:text-white flex items-center gap-2">
            <Zap className="text-warning" size={20} /> New Manual Alert
          </h3>
          
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Symbol</label>
              <select 
                className="px-3 py-2 bg-white dark:bg-surface border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-primary w-full"
                value={selectedToken}
                onChange={(e) => setSelectedToken(e.target.value)}
              >
                {stocks.length === 0 && <option value="">No stocks in watchlist</option>}
                {stocks.map(s => (
                  <option key={s.token} value={s.token}>{s.symbol} (₹{s.ltp})</option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Condition</label>
              <div className="flex bg-slate-100 dark:bg-slate-800 p-1 rounded-lg">
                <button
                  type="button"
                  onClick={() => setCondition(AlertCondition.ABOVE)}
                  className={`flex-1 py-1 text-sm font-medium rounded-md transition-colors ${condition === AlertCondition.ABOVE ? 'bg-white dark:bg-slate-600 shadow-sm text-primary' : 'text-slate-500'}`}
                >
                  Above
                </button>
                <button
                  type="button"
                  onClick={() => setCondition(AlertCondition.BELOW)}
                  className={`flex-1 py-1 text-sm font-medium rounded-md transition-colors ${condition === AlertCondition.BELOW ? 'bg-white dark:bg-slate-600 shadow-sm text-danger' : 'text-slate-500'}`}
                >
                  Below
                </button>
              </div>
            </div>

            <Input 
              label="Target Price"
              type="number"
              step="0.05"
              placeholder="0.00"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              required
            />

            <Button type="submit" fullWidth disabled={stocks.length === 0}>
              Set Alert
            </Button>
          </form>
        </div>

        {/* Center: Auto Generation Control */}
        <div className="lg:col-span-1 flex flex-col gap-6">
          <div className="bg-gradient-to-br from-indigo-500 to-purple-600 p-6 rounded-xl shadow-lg text-white flex-1 flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Layers className="text-indigo-100" />
                <h3 className="font-bold text-lg">3-6-9 Strategy</h3>
              </div>
              <p className="text-sm opacity-90 mb-4 leading-relaxed">
                Automatically generate Support & Resistance levels relative to Weekly Close. <br/>
                <span className="opacity-75 text-xs block mt-2 font-mono bg-black/20 p-1 rounded">
                  Price &gt; 3333 ? [30, 60, 90] : [3, 6, 9]
                </span>
              </p>
              
              {/* Active Background Summary */}
              {Object.keys(autoSummary).length > 0 && (
                <div className="mb-4 bg-white/10 p-3 rounded-lg backdrop-blur-sm max-h-[120px] overflow-y-auto custom-scrollbar">
                  <div className="text-xs font-semibold uppercase tracking-wider opacity-70 mb-2 sticky top-0">Monitoring</div>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(autoSummary).map(([symbol, count]) => (
                      <span key={symbol} className="text-xs bg-white/20 px-2 py-1 rounded text-white border border-white/10">
                        {symbol}: {count}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
            
            <Button 
              variant="warning" 
              fullWidth 
              onClick={onAutoAdd}
              disabled={stocks.length === 0}
            >
              Generate Levels
            </Button>
          </div>
        </div>

        {/* Right: History / Logs */}
        <div className="lg:col-span-1 bg-white dark:bg-surface rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 flex flex-col h-[380px]">
          <div className="p-4 border-b border-slate-200 dark:border-slate-700 flex justify-between items-center bg-slate-50 dark:bg-slate-800/50 rounded-t-xl">
             <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <History size={18} /> Recent Activity
            </h3>
            <button onClick={onClearLogs} className="text-xs text-slate-400 hover:text-danger">Clear</button>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {logs.length === 0 ? (
              <div className="text-center py-10 text-slate-400 text-sm">
                No recent activity.
              </div>
            ) : (
              logs.map(log => (
                <div key={log.id} className="text-sm border-l-2 border-slate-200 dark:border-slate-700 pl-3 py-1">
                  <div className="flex justify-between items-start">
                    <span className={`font-semibold ${log.type === 'TRIGGERED' ? 'text-primary' : 'text-slate-500'}`}>
                      {log.symbol}
                    </span>
                    <span className="text-xs text-slate-400">
                      {log.timestamp.toLocaleTimeString()}
                    </span>
                  </div>
                  <p className="text-slate-600 dark:text-slate-300 mt-0.5">{log.message}</p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Bottom: Active Alerts List */}
      <div className={`bg-white dark:bg-surface rounded-xl shadow-sm border transition-colors
        ${isPaused ? 'border-amber-400 dark:border-amber-600' : 'border-slate-200 dark:border-slate-700'}
      `}>
        <div className="p-6 border-b border-slate-200 dark:border-slate-700 flex flex-col sm:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-3">
             <h3 className="font-bold text-lg text-slate-900 dark:text-white flex items-center gap-2">
              <Bell className={isPaused ? "text-slate-400" : "text-primary"} size={20} /> 
              Active Alerts
            </h3>
            {isPaused && (
              <span className="text-xs bg-amber-100 dark:bg-amber-900/30 text-amber-600 px-2 py-1 rounded flex items-center gap-1 font-semibold">
                <AlertTriangle size={12} /> PAUSED
              </span>
            )}
          </div>
          
          <div className="flex items-center gap-4">
             {/* Pause Toggle */}
             <Button 
                onClick={onTogglePause}
                variant={isPaused ? 'primary' : 'ghost'}
                className={`flex items-center gap-2 text-xs py-1.5 h-8 border ${isPaused ? '' : 'border-slate-200 dark:border-slate-600'}`}
             >
                {isPaused ? <Play size={14} fill="currentColor" /> : <Pause size={14} fill="currentColor" />}
                {isPaused ? "Resume Monitoring" : "Pause All"}
             </Button>

             <div className="h-6 w-px bg-slate-200 dark:bg-slate-700 mx-1"></div>

             {/* Toggle Background Alerts visibility */}
             {autoAlerts.length > 0 && (
                <button 
                  onClick={() => setShowAutoAlerts(!showAutoAlerts)}
                  className="text-xs flex items-center gap-1.5 text-slate-500 hover:text-primary transition-colors"
                >
                  {showAutoAlerts ? <EyeOff size={14} /> : <Eye size={14} />}
                  {showAutoAlerts ? 'Hide' : 'Show'} Auto ({autoAlerts.length})
                </button>
             )}
             <span className="bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 text-xs px-2 py-0.5 rounded-full">
               Manual: {manualAlerts.length}
             </span>
          </div>
        </div>
        
        <div className={`p-4 grid grid-cols-1 md:grid-cols-2 gap-4 transition-opacity duration-300 ${isPaused ? 'opacity-50 grayscale-[0.5]' : 'opacity-100'}`}>
          {(showAutoAlerts ? alerts : manualAlerts).length === 0 ? (
            <div className="col-span-full text-center py-12 text-slate-500">
              <Bell size={48} className="mx-auto mb-3 opacity-20" />
              <p>No active alerts visible.</p>
            </div>
          ) : (
            (showAutoAlerts ? alerts : manualAlerts).map(alert => {
               const currentLtp = stocks.find(s => s.token === alert.token)?.ltp || 0;
               const isClose = Math.abs(currentLtp - alert.price) / alert.price < 0.005; // 0.5% away

               return (
                <div key={alert.id} className={`flex items-center justify-between p-4 rounded-lg border transition-all 
                  ${isClose ? 'bg-amber-50 dark:bg-amber-900/10 border-amber-200 dark:border-amber-800' : 'bg-slate-50 dark:bg-slate-800/50 border-slate-200 dark:border-slate-700'}
                  ${alert.type === 'AUTO' ? 'opacity-80 border-dashed' : ''}
                `}>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-900 dark:text-white">{alert.symbol}</span>
                      {alert.type === 'AUTO' && (
                        <span className="text-[10px] bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-300 px-1 rounded">AUTO</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-xl font-mono font-medium ${alert.condition === AlertCondition.ABOVE ? 'text-emerald-600' : 'text-rose-600'}`}>
                        {alert.condition === AlertCondition.ABOVE ? '>' : '<'} {alert.price}
                      </span>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-3">
                    <div className="text-right mr-2">
                       <div className="text-xs text-slate-400">Current</div>
                       <div className="font-mono text-slate-700 dark:text-slate-300">{currentLtp}</div>
                    </div>
                    <button 
                      onClick={() => onRemoveAlert(alert.id)}
                      className="text-slate-400 hover:text-danger hover:bg-white dark:hover:bg-slate-800 p-2 rounded-lg transition-colors"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
               );
            })
          )}
        </div>
      </div>
    </div>
  );
};

export default AlertsView;