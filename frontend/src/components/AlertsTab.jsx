import { useState } from 'react';
import { generateAlerts, generateBulkAlerts, deleteAlert, pauseAlerts } from '../services/api';

function AlertsTab({ sessionId, watchlist = [], alerts = [], setAlerts, isPaused, setIsPaused }) {
    const [generating, setGenerating] = useState(false);
    const [bulkGenerating, setBulkGenerating] = useState(false);

    // Ensure watchlist is always an array
    const safeWatchlist = Array.isArray(watchlist) ? watchlist : [];

    // Form state
    const [selectedSymbol, setSelectedSymbol] = useState(safeWatchlist.length > 0 ? safeWatchlist[0].symbol : '');
    const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
    const [isCustomRange, setIsCustomRange] = useState(false);
    const [startTime, setStartTime] = useState('09:15');
    const [endTime, setEndTime] = useState('15:30');
    const [selectedLevels, setSelectedLevels] = useState(['High', 'Low', 'R1', 'S1']);

    const handleLevelToggle = (level) => {
        setSelectedLevels(prev =>
            prev.includes(level)
                ? prev.filter(l => l !== level)
                : [...prev, level]
        );
    };

    const handleGenerateAlerts = async () => {
        if (!selectedSymbol) {
            alert('Please select a stock');
            return;
        }
        if (selectedLevels.length === 0) {
            alert('Please select at least one level');
            return;
        }

        try {
            setGenerating(true);
            const response = await generateAlerts(sessionId, {
                symbol: selectedSymbol,
                date: date,
                start_time: startTime,
                end_time: endTime,
                is_custom_range: isCustomRange,
                levels: selectedLevels
            });

            // Alerts will be updated via parent state triggered by backend refresh/websocket, 
            // but we might need to manually trigger a refresh if the parent doesn't auto-poll alerts.
            // In App.jsx, alerts are loaded on mount, but not polled. 
            // However, the backend adds them to the session, and they'll show up on next fetch.
            // Let's manually updae the state with new alerts to be safe.
            if (response.alerts) {
                setAlerts(prev => [...prev, ...response.alerts]);
            }
            alert(`Generated ${response.count || 0} alerts`);
        } catch (err) {
            console.error('Generate alerts error:', err);
            alert(err.response?.data?.detail || 'Failed to generate alerts');
        } finally {
            setGenerating(false);
        }
    };

    const handleGenerateBulkAlerts = async () => {
        if (safeWatchlist.length === 0) {
            alert('Watchlist is empty');
            return;
        }
        if (selectedLevels.length === 0) {
            alert('Please select at least one level');
            return;
        }

        try {
            setBulkGenerating(true);
            const response = await generateBulkAlerts(sessionId, {
                date: date,
                start_time: startTime,
                end_time: endTime,
                is_custom_range: isCustomRange,
                levels: selectedLevels
            });

            // Update alerts state
            if (response.results) {
                // Fetch fresh alerts from backend to ensure sync
                const { getAlerts } = await import('../services/api');
                const alertsData = await getAlerts(sessionId);
                setAlerts(alertsData.alerts);
            }

            // Show detailed summary
            const successCount = response.results.filter(r => r.success).length;
            const failCount = response.results.filter(r => !r.success).length;
            alert(`Bulk Generation Complete!\n\nTotal Alerts: ${response.total_alerts}\nStocks Processed: ${successCount}/${response.total_stocks}\n${failCount > 0 ? `Failed: ${failCount}` : ''}`);
        } catch (err) {
            console.error('Bulk generate alerts error:', err);
            alert(err.response?.data?.detail || 'Failed to generate bulk alerts');
        } finally {
            setBulkGenerating(false);
        }
    };

    const handleDeleteAlert = async (alertId) => {
        try {
            await deleteAlert(sessionId, alertId);
            setAlerts(alerts.filter(a => a.id !== alertId));
        } catch (err) {
            console.error('Delete alert error:', err);
        }
    };

    const handleTogglePause = async (newValue) => {
        try {
            await pauseAlerts(sessionId, newValue);
            setIsPaused(newValue);
        } catch (err) {
            console.error('Pause alerts error:', err);
        }
    };

    return (
        <div className="max-w-4xl mx-auto space-y-4 pb-20">
            {/* Strategy Control Panel */}
            <div className="bg-[#222844] rounded-lg p-5 border border-[#2D3748] shadow-xl">
                <div className="flex items-center justify-between mb-6">
                    <div>
                        <h3 className="text-white font-bold text-xl">High/Low Alert Strategy</h3>
                        <p className="text-gray-400 text-sm">Target historical Highs, Lows and S/R levels</p>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                        <span className="text-xs text-gray-500 font-medium">Monitoring</span>
                        <button
                            onClick={() => handleTogglePause(!isPaused)}
                            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-all duration-300 focus:outline-none ${isPaused ? 'bg-[#F26565]' : 'bg-[#48BB78]'}`}
                        >
                            <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-300 ${isPaused ? 'translate-x-6' : 'translate-x-1'}`} />
                        </button>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Stock & Date Selection */}
                    <div className="space-y-4">
                        <div className="flex flex-col gap-1.5">
                            <label className="text-gray-400 text-xs font-semibold uppercase tracking-wider">Select Stock</label>
                            <select
                                value={selectedSymbol}
                                onChange={(e) => setSelectedSymbol(e.target.value)}
                                className="bg-[#1A1F3A] text-white border border-[#2D3748] rounded-lg p-2.5 focus:border-[#667EEA] focus:ring-1 focus:ring-[#667EEA] outline-none transition-all"
                            >
                                <option value="">Select a stock...</option>
                                {safeWatchlist.map(s => (
                                    <option key={s.token} value={s.symbol}>{s.symbol}</option>
                                ))}
                            </select>
                        </div>
                        <div className="flex flex-col gap-1.5">
                            <label className="text-gray-400 text-xs font-semibold uppercase tracking-wider">Calculation Date</label>
                            <input
                                type="date"
                                value={date}
                                onChange={(e) => setDate(e.target.value)}
                                className="bg-[#1A1F3A] text-white border border-[#2D3748] rounded-lg p-2.5 focus:border-[#667EEA] outline-none transition-all [color-scheme:dark]"
                            />
                        </div>
                    </div>

                    {/* Levels & Time Options */}
                    <div className="space-y-4">
                        <div className="flex flex-col gap-1.5">
                            <label className="text-gray-400 text-xs font-semibold uppercase tracking-wider">Alert Levels</label>
                            <div className="flex flex-wrap gap-2">
                                {['High', 'Low', 'R1', 'R2', 'R3', 'R4', 'S1', 'S2', 'S3', 'S4'].map(level => (
                                    <button
                                        key={level}
                                        onClick={() => handleLevelToggle(level)}
                                        className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all border ${selectedLevels.includes(level)
                                            ? 'bg-[#667EEA] border-[#667EEA] text-white shadow-lg shadow-[#667EEA22]'
                                            : 'bg-transparent border-[#2D3748] text-gray-400 hover:border-gray-500'
                                            }`}
                                    >
                                        {level}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="pt-2">
                            <label className="flex items-center gap-2 cursor-pointer group">
                                <input
                                    type="checkbox"
                                    checked={isCustomRange}
                                    onChange={(e) => setIsCustomRange(e.target.checked)}
                                    className="w-4 h-4 rounded border-gray-300 text-[#667EEA] focus:ring-[#667EEA] bg-[#1A1F3A]"
                                />
                                <span className="text-gray-300 text-sm group-hover:text-white transition-colors">Custom Time Range</span>
                            </label>

                            {isCustomRange && (
                                <div className="flex gap-2 mt-2 animate-in fade-in slide-in-from-top-2 duration-300">
                                    <input
                                        type="time"
                                        value={startTime}
                                        onChange={(e) => setStartTime(e.target.value)}
                                        className="flex-1 bg-[#1A1F3A] text-white border border-[#2D3748] rounded-lg p-1.5 text-sm outline-none [color-scheme:dark]"
                                    />
                                    <input
                                        type="time"
                                        value={endTime}
                                        onChange={(e) => setEndTime(e.target.value)}
                                        className="flex-1 bg-[#1A1F3A] text-white border border-[#2D3748] rounded-lg p-1.5 text-sm outline-none [color-scheme:dark]"
                                    />
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-6">
                    <button
                        onClick={handleGenerateAlerts}
                        disabled={generating || bulkGenerating || !selectedSymbol}
                        className="py-3 bg-[#667EEA] hover:bg-[#5568D3] text-white font-bold rounded-lg shadow-lg hover:shadow-[#667EEA44] transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                        {generating ? (
                            <>
                                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                Calculating...
                            </>
                        ) : (
                            '⚡ Generate for Selected Stock'
                        )}
                    </button>

                    <button
                        onClick={handleGenerateBulkAlerts}
                        disabled={generating || bulkGenerating || safeWatchlist.length === 0}
                        className="py-3 bg-[#48BB78] hover:bg-[#38A169] text-white font-bold rounded-lg shadow-lg hover:shadow-[#48BB7844] transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                        {bulkGenerating ? (
                            <>
                                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                Processing {safeWatchlist.length} stocks...
                            </>
                        ) : (
                            `🚀 Generate for All Watchlist (${safeWatchlist.length})`
                        )}
                    </button>
                </div>
            </div>

            {/* Active Alerts List */}
            <div className="space-y-3">
                <div className="flex items-center justify-between">
                    <h3 className="text-white font-bold text-lg">Active Alerts ({alerts.length})</h3>
                    {alerts.length > 0 && (
                        <span className="text-xs text-gray-500">Live monitoring active</span>
                    )}
                </div>

                {alerts.length === 0 ? (
                    <div className="bg-[#222844] rounded-lg p-10 border border-[#2D3748] text-center border-dashed">
                        <div className="text-4xl mb-3">🔔</div>
                        <p className="text-gray-400">No active alerts.</p>
                        <p className="text-gray-500 text-sm mt-1">Select a stock and click generate above to get started.</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 gap-3">
                        {alerts.map((alert) => {
                            const isAbove = alert.condition === 'ABOVE';
                            const colorClass = isAbove ? 'text-[#48BB78]' : 'text-[#F56565]';
                            const bgColorClass = isAbove ? 'border-l-[#48BB78]' : 'border-l-[#F56565]';
                            const icon = isAbove ? '📈' : '📉';
                            const typeLabel = alert.type?.replace('AUTO_', '') || 'MANUAL';

                            return (
                                <div
                                    key={alert.id}
                                    className={`bg-[#222844] rounded-lg p-4 border border-[#2D3748] border-l-4 ${bgColorClass} hover:border-[#667EEA] transition-all duration-300 group shadow-sm`}
                                >
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-4">
                                            <span className="text-2xl bg-[#1A1F3A] p-2 rounded-lg">{icon}</span>
                                            <div>
                                                <div className="flex items-center gap-2">
                                                    <h4 className="text-white font-bold text-base">{alert.symbol}</h4>
                                                    <span className="text-[10px] bg-[#2D3748] text-gray-400 px-1.5 py-0.5 rounded font-mono uppercase">
                                                        {typeLabel}
                                                    </span>
                                                </div>
                                                <div className="flex items-center gap-2 mt-0.5">
                                                    <span className={`font-mono font-bold text-lg ${colorClass}`}>
                                                        ₹{alert.price?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                                    </span>
                                                    <span className="text-gray-500 text-xs font-medium uppercase tracking-tighter">
                                                        {alert.condition}
                                                    </span>
                                                </div>
                                            </div>
                                        </div>
                                        <button
                                            onClick={() => handleDeleteAlert(alert.id)}
                                            className="opacity-0 group-hover:opacity-100 p-2 text-gray-400 hover:text-white hover:bg-[#F56565] rounded-lg transition-all duration-200"
                                            title="Delete Alert"
                                        >
                                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                            </svg>
                                        </button>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
}

export default AlertsTab;
