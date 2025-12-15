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
        <div className="min-h-screen bg-[#0A0E27] flex flex-col">
            {/* Top Bar */}
            <div className="bg-[#1A1F3A] border-b border-[#2D3748] px-4 py-3">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-xl font-bold text-white">Trade Yantra</h1>
                        <p className="text-xs text-gray-400">Client: {session.clientId}</p>
                    </div>
                    <div className="flex items-center gap-4">
                        {/* WebSocket Status */}
                        <div className="flex items-center gap-2">
                            <div className={`w-2 h-2 rounded-full ${wsStatus === 'connected' ? 'bg-[#48BB78]' : 'bg-[#F56565]'} animate-pulse`} />
                            <span className="text-xs text-gray-400">
                                {wsStatus === 'connected' ? 'Live' : 'Disconnected'}
                            </span>
                        </div>
                        {/* Logout Button */}
                        <button
                            onClick={handleLogout}
                            className="px-4 py-1.5 bg-[#F56565] hover:bg-red-600 text-white text-sm rounded-lg transition-colors"
                        >
                            Logout
                        </button>
                        {/* Notification Permission Button (Mobile mostly) */}
                        {'Notification' in window && Notification.permission === 'default' && (
                            <button
                                onClick={() => Notification.requestPermission()}
                                className="px-4 py-1.5 bg-[#667EEA] hover:bg-blue-600 text-white text-sm rounded-lg transition-colors"
                            >
                                🔔 Enable Alerts
                            </button>
                        )}
                    </div>
                </div>
            </div>

            {/* Tab Navigation */}
            <div className="bg-[#1A1F3A] border-b border-[#2D3748] px-4">
                <div className="flex gap-1">
                    <button
                        onClick={() => setActiveTab('watchlist')}
                        className={`px-6 py-3 text-sm font-medium transition-colors border-b-2 ${activeTab === 'watchlist'
                            ? 'border-[#667EEA] text-[#667EEA]'
                            : 'border-transparent text-gray-400 hover:text-white'
                            }`}
                    >
                        📋 Watchlist
                    </button>
                    <button
                        onClick={() => setActiveTab('alerts')}
                        className={`px-6 py-3 text-sm font-medium transition-colors border-b-2 ${activeTab === 'alerts'
                            ? 'border-[#667EEA] text-[#667EEA]'
                            : 'border-transparent text-gray-400 hover:text-white'
                            }`}
                    >
                        🔔 Alerts
                    </button>
                    <button
                        onClick={() => setActiveTab('indices')}
                        className={`px-6 py-3 text-sm font-medium transition-colors border-b-2 ${activeTab === 'indices'
                            ? 'border-[#667EEA] text-[#667EEA]'
                            : 'border-transparent text-gray-400 hover:text-white'
                            }`}
                    >
                        📊 Indices
                    </button>
                    <button
                        onClick={() => setActiveTab('logs')}
                        className={`px-6 py-3 text-sm font-medium transition-colors border-b-2 ${activeTab === 'logs'
                            ? 'border-[#667EEA] text-[#667EEA]'
                            : 'border-transparent text-gray-400 hover:text-white'
                            }`}
                    >
                        📝 Logs
                    </button>
                </div>
            </div>

            {/* Tab Content */}
            <div className="flex-1 overflow-auto">
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
        </div>
    );
}

export default Dashboard;
