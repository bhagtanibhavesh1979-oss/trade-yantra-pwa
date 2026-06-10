import { useState, useEffect } from 'react';
import WatchlistTab from './WatchlistTab';
import AlertsTab from './AlertsTab';
import LogsTab from './LogsTab';
import BacktestTab from './BacktestTab';
import AstroChart from './AstroChart';
import { logout } from '../services/api';
import { showNotification } from '../services/notifications';
import MarketOverview from './MarketOverview';
import OrdersTab from './OrdersTab';
import LiveOrdersTab from './LiveOrdersTab';
import toast from 'react-hot-toast';

function Dashboard({
    session, onLogout, watchlist, setWatchlist,
    alerts, setAlerts, logs, isPaused, setIsPaused,
    referenceDate, setReferenceDate, wsStatus,
    activeTab: propActiveTab, setActiveTab: propSetActiveTab,
    preSelectedAlertSymbol, setPreSelectedAlertSymbol,
    isLoadingData, isVisible, onRefreshData,
    paperTrades, setPaperTrades, paperBalance, setPaperBalance,
    autoExec, setAutoExec, strategyMode, setStrategyMode, bufferPct,
    liveAutoExec, setLiveAutoExec, liveTradeQty, setLiveTradeQty,
    liveTradeCap, setLiveTradeCap,
}) {
    const [localActiveTab, setLocalActiveTab] = useState('watchlist');
    const activeTab    = propActiveTab    || localActiveTab;
    const setActiveTab = propSetActiveTab || setLocalActiveTab;

    // Symbol pushed from watchlist → AstroChart
    const [chartSymbol, setChartSymbol] = useState(null);

    const handleOpenInChart = (stock) => {
        setChartSymbol({ symbol: stock.symbol, token: stock.token, exch_seg: stock.exch_seg || 'NSE' });
        setActiveTab('astro_chart');
    };

    const [theme, setTheme] = useState(() => {
        if (typeof window !== 'undefined') return localStorage.getItem('trade_yantra_theme') || 'dark';
        return 'dark';
    });

    useEffect(() => {
        localStorage.setItem('trade_yantra_theme', theme);
        if (theme === 'light') document.documentElement.classList.add('light-theme');
        else document.documentElement.classList.remove('light-theme');
    }, [theme]);

    const handleIndexAlertClick = (symbol) => {
        setPreSelectedAlertSymbol(symbol);
        setActiveTab('alerts');
    };

    return (
        <div className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)] transition-colors duration-300 flex flex-col pb-16 md:pb-0">
            {/* Header */}
            <header className="bg-[var(--bg-secondary)] border-b border-[var(--border-color)] px-2.5 md:px-6 py-4 sticky top-0 z-30 shadow-2xl">
                <div className="flex items-center justify-between max-w-[1400px] mx-auto">
                    <div className="flex items-center gap-4">
                        <div className="relative">
                            <img src="/logo.png" alt="Logo" className="w-10 h-10 rounded-xl shadow-lg border border-[var(--border-color)]" />
                            <div className={`absolute -bottom-1 -right-1 w-3.5 h-3.5 rounded-full border-2 border-[var(--bg-secondary)] ${wsStatus === 'connected' ? 'bg-[var(--success-neon)] shadow-[0_0_10px_var(--success-neon)]' : 'bg-red-500'} animate-pulse`} />
                        </div>
                        <div>
                            <h1 className="text-xl font-black tracking-tight gradient-text">TRADE YANTRA <span className="text-[10px] font-bold bg-[var(--accent-blue)]/20 text-[var(--accent-blue)] px-1.5 py-0.5 rounded ml-1 tracking-widest">PRO</span></h1>
                            <div className="flex items-center gap-2">
                                <span className="text-[10px] text-gray-400 font-bold uppercase overflow-hidden text-ellipsis whitespace-nowrap max-w-[120px]">ID: {session.clientId}</span>
                                <span className="w-1 h-1 rounded-full bg-gray-600"></span>
                                <span className="text-[10px] text-[var(--accent-blue)] font-black uppercase tracking-tighter">Live Engine</span>
                            </div>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <button onClick={() => setTheme(p => p === 'dark' ? 'light' : 'dark')}
                            className="p-2.5 bg-[var(--bg-primary)] border border-[var(--border-color)] hover:border-[var(--accent-blue)] rounded-xl transition-all shadow-sm group">
                            {theme === 'dark' ? (
                                <svg className="w-5 h-5 text-yellow-400 group-hover:scale-110 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                                </svg>
                            ) : (
                                <svg className="w-5 h-5 text-indigo-500 group-hover:scale-110 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                                </svg>
                            )}
                        </button>
                        <button onClick={onLogout}
                            className="flex items-center gap-2 px-4 py-2.5 bg-red-500/10 hover:bg-red-500 text-red-500 hover:text-white border border-red-500/20 rounded-xl transition-all font-bold text-xs">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                            </svg>
                            <span className="hidden md:inline">LOGOUT</span>
                        </button>
                    </div>
                </div>
            </header>

            {/* Main content */}
            <div className="flex-1 overflow-y-auto overflow-x-hidden p-0">
                <div className="px-0 md:px-4 bg-[var(--bg-primary)] border-b border-[var(--border-color)]/30">
                    <MarketOverview
                        sessionId={session.sessionId || session.session_id}
                        isVisible={isVisible}
                        onAlertClick={handleIndexAlertClick}
                    />
                </div>
                <div className="pt-2"></div>

                {activeTab === 'watchlist' && (
                    <WatchlistTab
                        session={session}
                        watchlist={watchlist}
                        setWatchlist={setWatchlist}
                        referenceDate={referenceDate}
                        isVisible={isVisible}
                        onOpenInChart={handleOpenInChart}
                    />
                )}
                {activeTab === 'alerts' && (
                    <AlertsTab
                        clientId={session.clientId || session.client_id}
                        sessionId={session.sessionId || session.session_id}
                        watchlist={watchlist}
                        alerts={alerts}
                        setAlerts={setAlerts}
                        isPaused={isPaused}
                        setIsPaused={setIsPaused}
                        referenceDate={referenceDate}
                        setReferenceDate={setReferenceDate}
                        preSelectedSymbol={preSelectedAlertSymbol}
                        isLoadingData={isLoadingData}
                        onRefreshData={onRefreshData}
                    />
                )}
                {activeTab === 'logs'        && <LogsTab logs={logs} />}
                {activeTab === 'orders'      && (
                    <OrdersTab
                        clientId={session?.clientId}
                        sessionId={session?.sessionId || session?.session_id}
                        watchlist={watchlist}
                        isPaused={isPaused}
                    />
                )}
                {activeTab === 'live_orders' && (
                    <LiveOrdersTab
                        clientId={session?.clientId}
                        sessionId={session?.sessionId || session?.session_id}
                        watchlist={watchlist}
                        isPaused={isPaused}
                        liveAutoExec={liveAutoExec}  setLiveAutoExec={setLiveAutoExec}
                        liveTradeQty={liveTradeQty}  setLiveTradeQty={setLiveTradeQty}
                        liveTradeCap={liveTradeCap}  setLiveTradeCap={setLiveTradeCap}
                    />
                )}
                {activeTab === 'lab' && (
                    <BacktestTab
                        clientId={session.clientId || session.client_id}
                        sessionId={session.sessionId || session.session_id}
                        watchlist={watchlist}
                    />
                )}
                {activeTab === 'astro_chart' && (
                    <AstroChart
                        session={session}
                        watchlist={watchlist}
                        externalSymbol={chartSymbol}
                    />
                )}
            </div>

            {/* Bottom nav */}
            <nav className="fixed bottom-0 left-0 right-0 bg-[var(--bg-secondary)]/80 backdrop-blur-xl border-t border-[var(--border-color)] z-40 pb-safe shadow-[0_-10px_40px_rgba(0,0,0,0.4)]">
                <div className="flex justify-around items-center h-20 max-w-lg mx-auto">
                    {[
                        { id: 'watchlist',   label: 'Market', icon: '📋' },
                        { id: 'orders',      label: 'Paper',  icon: '💰' },
                        { id: 'live_orders', label: 'LIVE',   icon: '🔴' },
                        { id: 'lab',         label: 'Lab',    icon: '🧪' },
                        { id: 'astro_chart', label: 'Astro',  icon: '🔭' },
                        { id: 'alerts',      label: 'Alerts', icon: '🔔' },
                        { id: 'logs',        label: 'Logs',   icon: '📝' },
                    ].map((tab) => (
                        <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                            className={`flex flex-col items-center justify-center flex-1 h-full relative transition-all duration-300 ${activeTab === tab.id ? 'text-[var(--accent-blue)] scale-110' : 'text-gray-500 hover:text-gray-300'}`}>
                            {activeTab === tab.id && (
                                <span className="absolute top-2 w-1.5 h-1.5 rounded-full bg-[var(--accent-blue)] shadow-[0_0_10px_var(--accent-blue)]" />
                            )}
                            <span className="text-2xl mb-1">{tab.icon}</span>
                            <span className={`text-[9px] font-black uppercase tracking-widest ${activeTab === tab.id ? 'opacity-100' : 'opacity-60'}`}>{tab.label}</span>
                        </button>
                    ))}
                </div>
            </nav>
        </div>
    );
}

export default Dashboard;