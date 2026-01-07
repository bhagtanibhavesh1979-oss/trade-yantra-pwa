import { useState, useEffect } from 'react';
import WatchlistTab from './WatchlistTab';
import AlertsTab from './AlertsTab';
import LogsTab from './LogsTab';
import MarketOverview from './MarketOverview';
import { logout } from '../services/api';
import { showNotification } from '../services/notifications';
import toast from 'react-hot-toast';

function Dashboard({
    session,
    onLogout,
    watchlist,
    setWatchlist,
    alerts,
    setAlerts,
    logs,
    isPaused,
    setIsPaused,
    referenceDate,
    setReferenceDate,
    wsStatus,
    activeTab: propActiveTab, // Receive from parent
    setActiveTab: propSetActiveTab, // Receive from parent
    preSelectedAlertSymbol,
    setPreSelectedAlertSymbol,
    isLoadingData,
    isVisible
}) {
    // If props are provided, use them. Otherwise default to local state (backward compatibility/safety)
    const [localActiveTab, setLocalActiveTab] = useState('watchlist');
    const activeTab = propActiveTab || localActiveTab;
    const setActiveTab = propSetActiveTab || setLocalActiveTab;

    // Theme State
    const [theme, setTheme] = useState(() => {
        if (typeof window !== 'undefined') {
            return localStorage.getItem('trade_yantra_theme') || 'dark';
        }
        return 'dark';
    });

    // ... existing useEffect ...

    useEffect(() => {
        localStorage.setItem('trade_yantra_theme', theme);
        if (theme === 'light') {
            document.documentElement.classList.add('light-theme');
        } else {
            document.documentElement.classList.remove('light-theme');
        }
    }, [theme]);

    const toggleTheme = () => {
        setTheme(prev => prev === 'dark' ? 'light' : 'dark');
    };

    const handleLogout = () => {
        onLogout();
    };

    return (
        <div className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)] transition-colors duration-300 flex flex-col pb-16 md:pb-0">
            {/* Top Bar */}
            <div className="bg-[var(--bg-secondary)] border-b border-[var(--border-color)] px-4 py-3 sticky top-0 z-20 shadow-sm">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <img src="/logo.png" alt="Logo" className="w-8 h-8 rounded-lg shadow-lg" />
                        <div>
                            <h1 className="text-xl font-bold text-white">Trade Yantra</h1>
                            <p className="text-xs text-gray-400">Client: {session.clientId}</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        {/* WebSocket Status */}
                        <div className={`w-2 h-2 rounded-full ${wsStatus === 'connected' ? 'bg-[#48BB78]' : 'bg-[#F56565]'} animate-pulse`} />

                        {/* Theme Toggle */}
                        <button
                            onClick={toggleTheme}
                            className="p-2 text-gray-400 hover:text-[var(--text-primary)] bg-[var(--bg-primary)] hover:bg-[var(--bg-card)] rounded-lg transition-all"
                            title={theme === 'dark' ? "Switch to Light Mode" : "Switch to Dark Mode"}
                        >
                            {theme === 'dark' ? (
                                <svg className="w-5 h-5 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                                </svg>
                            ) : (
                                <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                                </svg>
                            )}
                        </button>

                        {/* Notification Permission Button */}
                        {'Notification' in window && Notification.permission === 'default' && (
                            <button
                                onClick={() => Notification.requestPermission()}
                                className="p-2 bg-[var(--accent-blue)] hover:brightness-110 text-white rounded-lg transition-colors"
                            >
                                🔔
                            </button>
                        )}

                        {/* Test Notification Button */}
                        <button
                            onClick={() => {
                                toast.success('Test Toast! 🔔');
                                showNotification('Test Alert!', {
                                    body: 'This is a test notification from Trade Yantra.',
                                    icon: '/logo.png',
                                    vibrate: [200, 100, 200]
                                });
                            }}
                            className="p-2 text-gray-400 hover:text-white transition-colors"
                            title="Test Notification"
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                            </svg>
                        </button>

                        {/* Logout Button */}
                        <button
                            onClick={handleLogout}
                            className="p-2 text-gray-400 hover:text-white transition-colors"
                        >
                            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                            </svg>
                        </button>
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 overflow-y-auto overflow-x-hidden p-0">
                {/* Market Status Header */}
                <div className="px-4 pt-4">
                    <MarketOverview
                        sessionId={session.sessionId}
                        onAlertClick={(symbol, token, exchange) => {
                            setPreSelectedAlertSymbol && setPreSelectedAlertSymbol({ symbol, token, exchange });
                            setActiveTab('alerts');
                        }}
                        isVisible={isVisible}
                    />
                </div>

                {activeTab === 'watchlist' && (
                    <WatchlistTab
                        sessionId={session.sessionId}
                        watchlist={watchlist}
                        setWatchlist={setWatchlist}
                        referenceDate={referenceDate}
                        isVisible={isVisible}
                    />
                )}
                {activeTab === 'alerts' && (
                    <AlertsTab
                        sessionId={session.sessionId}
                        watchlist={watchlist}
                        alerts={alerts}
                        setAlerts={setAlerts}
                        isPaused={isPaused}
                        setIsPaused={setIsPaused}
                        referenceDate={referenceDate}
                        setReferenceDate={setReferenceDate}
                        preSelectedSymbol={preSelectedAlertSymbol}
                        isLoadingData={isLoadingData}
                    />
                )}
                {activeTab === 'logs' && (
                    <LogsTab logs={logs} />
                )}
            </div>

            {/* Bottom Navigation (Fixed) */}
            <div className="fixed bottom-0 left-0 right-0 bg-[var(--bg-secondary)] border-t border-[var(--border-color)] z-30">
                <div className="flex justify-around items-center h-16">
                    <button
                        onClick={() => setActiveTab('watchlist')}
                        className={`flex flex-col items-center justify-center w-full h-full ${activeTab === 'watchlist' ? 'text-[#667EEA]' : 'text-gray-400'}`}
                    >
                        <span className="text-xl">📋</span>
                        <span className="text-xs mt-1">Watchlist</span>
                    </button>
                    <button
                        onClick={() => setActiveTab('alerts')}
                        className={`flex flex-col items-center justify-center w-full h-full ${activeTab === 'alerts' ? 'text-[#667EEA]' : 'text-gray-400'}`}
                    >
                        <span className="text-xl">🔔</span>
                        <span className="text-xs mt-1">Alerts</span>
                    </button>
                    <button
                        onClick={() => setActiveTab('logs')}
                        className={`flex flex-col items-center justify-center w-full h-full ${activeTab === 'logs' ? 'text-[#667EEA]' : 'text-gray-400'}`}
                    >
                        <span className="text-xl">📝</span>
                        <span className="text-xs mt-1">Logs</span>
                    </button>
                </div>
            </div>
        </div>
    );
}

export default Dashboard;
