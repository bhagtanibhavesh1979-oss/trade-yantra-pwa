import { useState } from 'react';
import WatchlistTab from './WatchlistTab';
import AlertsTab from './AlertsTab';
import IndicesTab from './IndicesTab';
import LogsTab from './LogsTab';
import { logout } from '../services/api';

function Dashboard({ session, onLogout, watchlist, setWatchlist, alerts, setAlerts, logs, setLogs, isPaused, setIsPaused, wsStatus }) {
    const [activeTab, setActiveTab] = useState('watchlist');

    const handleLogout = async () => {
        try {
            await logout(session.sessionId);
        } catch (err) {
            console.error('Logout error:', err);
        } finally {
            onLogout();
        }
    };

    return (
        <div className="min-h-screen bg-[#0A0E27] flex flex-col pb-16 md:pb-0">
            {/* Top Bar */}
            <div className="bg-[#1A1F3A] border-b border-[#2D3748] px-4 py-3 sticky top-0 z-20">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-xl font-bold text-white">Trade Yantra</h1>
                        <p className="text-xs text-gray-400">Client: {session.clientId}</p>
                    </div>
                    <div className="flex items-center gap-3">
                        {/* WebSocket Status */}
                        <div className={`w-2 h-2 rounded-full ${wsStatus === 'connected' ? 'bg-[#48BB78]' : 'bg-[#F56565]'} animate-pulse`} />

                        {/* Notification Permission Button */}
                        {'Notification' in window && Notification.permission === 'default' && (
                            <button
                                onClick={() => Notification.requestPermission()}
                                className="p-2 bg-[#667EEA] hover:bg-blue-600 text-white rounded-lg transition-colors"
                            >
                                🔔
                            </button>
                        )}

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
            <div className="flex-1 overflow-y-auto overflow-x-hidden p-2 md:p-4">
                {activeTab === 'watchlist' && (
                    <WatchlistTab
                        sessionId={session.sessionId}
                        watchlist={watchlist}
                        setWatchlist={setWatchlist}
                    />
                )}
                {activeTab === 'alerts' && (
                    <AlertsTab
                        sessionId={session.sessionId}
                        alerts={alerts}
                        setAlerts={setAlerts}
                        isPaused={isPaused}
                        setIsPaused={setIsPaused}
                    />
                )}
                {activeTab === 'indices' && (
                    <IndicesTab sessionId={session.sessionId} />
                )}
                {activeTab === 'logs' && (
                    <LogsTab logs={logs} />
                )}
            </div>

            {/* Bottom Navigation (Fixed) */}
            <div className="fixed bottom-0 left-0 right-0 bg-[#1A1F3A] border-t border-[#2D3748] z-30">
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
                        onClick={() => setActiveTab('indices')}
                        className={`flex flex-col items-center justify-center w-full h-full ${activeTab === 'indices' ? 'text-[#667EEA]' : 'text-gray-400'}`}
                    >
                        <span className="text-xl">📊</span>
                        <span className="text-xs mt-1">Indices</span>
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
